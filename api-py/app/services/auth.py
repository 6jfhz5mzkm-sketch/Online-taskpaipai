"""认证服务:商家飞书登录(简化/mock)+ 管理员登录/改密(对齐 backend auth/admin-auth)。

管理员登录失败锁定(任务管理后台开发标准 §5.2「连续5次失败锁定30分钟」)在**本服务层**实现,
路由层不散落任何 if;实现边界见 _LoginAttemptStore 的 docstring。
"""
import math
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiException
from app.core.security import create_admin_token, create_merchant_token, hash_password, needs_rehash, verify_password
from app.services.merchant import upsert_from_feishu

# ---- 管理员登录失败锁定(进程内内存态) ----

# 容量上限:防止随机用户名刷爆内存(AGENTS.md 第六节:运行面必须有上界)
MAX_TRACKED_LOGIN_KEYS = 1000


def _monotonic() -> float:
    """单调时钟(经模块级间接层调用,测试可 monkeypatch 以免真实等待 30 分钟)。"""
    return time.monotonic()


# 取整前把差值 round 到 1e-6 秒:**远低于时钟分辨率**(Windows 的 time.monotonic 粒度约 1ms),
# 因此不改变任何产品语义(所有对外口径都以「秒」为单位),只用于抹掉浮点尾差。
_SECONDS_ROUND_DIGITS = 6


def _lock_seconds_left(deadline: float, now: float) -> int:
    """剩余秒数(**向上取整,已抹掉浮点尾差**);已到期返回 0。

    为什么必须抹尾差(#PB-34):锁定时间由 `deadline = now + lock_seconds` 写入,事后用
    `ceil(deadline - now)` 取整。float64 在这个减法上会产生 **+1 ulp 的正尾差**——实测
    `base=130398.254`、1ms 步长下 24.8% 的时点得到 `1800.0000000000146`,`ceil` 会把它放大成
    `lock_seconds + 1`(1801),用户看到「请在 1801 秒后重试」,越过配置窗口 1800。
    先把差值 `round(..., 6)` 再 `ceil`,即可把这类 ±尾差归零;反向尾差(如 1799.9999999999985)
    经同一处理仍得 1800,不会提前解锁。

    两个调用点(`locked_seconds` 与 `record_failure`)**共用本函数**,禁止各写一套取整。
    """
    remaining = deadline - now
    if remaining <= 0:
        return 0
    return int(math.ceil(round(remaining, _SECONDS_ROUND_DIGITS)))


class _LoginAttemptStore:
    """管理员登录失败计数/锁定表(进程内内存态)。

    边界(务必知悉,勿据此认为生产级防护已完备):
    - **单进程内存态**:uvicorn 多 worker 或多实例部署时各进程各算一份,锁定不共享;
      进程重启后计数与锁定全部丢失;
    - 若未来需要跨进程/多实例一致,必须改为落库(或引入本项目当前未使用的 Redis)方案;
    - 有容量上限 max_entries 与过期清理(条目在「已解锁且最后失败早于 ttl」后清除),
      超限时淘汰最近失败时间最早的条目,禁止无界增长。
    """

    def __init__(self, max_entries: int, clock: Callable[[], float]) -> None:
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: Dict[str, Dict[str, float]] = {}

    def _prune(self, now: float, ttl: float) -> None:
        """清理过期项;仍超上限时淘汰最旧项(调用方须持锁)。"""
        for key in [k for k, e in self._entries.items()
                    if now - e["last"] > ttl and e["locked_until"] <= now]:
            self._entries.pop(key, None)
        overflow = len(self._entries) - self._max_entries
        if overflow > 0:
            oldest = sorted(self._entries.items(), key=lambda kv: kv[1]["last"])[:overflow]
            for key, _ in oldest:
                self._entries.pop(key, None)

    def locked_seconds(self, key: str, ttl: float) -> int:
        """剩余锁定秒数(向上取整,抹浮点尾差,见 `_lock_seconds_left`);未锁定返回 0。"""
        now = self._clock()
        with self._lock:
            self._prune(now, ttl)
            entry = self._entries.get(key)
            if entry is None or entry["locked_until"] <= now:
                return 0
            return _lock_seconds_left(entry["locked_until"], now)

    def record_failure(self, key: str, max_attempts: int, lock_seconds: float, ttl: float) -> int:
        """记一次失败;达到阈值即进入锁定并返回剩余锁定秒数,否则返回 0。"""
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or now - entry["last"] > ttl:
                entry = {"failures": 0.0, "last": now, "locked_until": 0.0}
                self._entries[key] = entry
            entry["failures"] += 1
            entry["last"] = now
            if entry["failures"] >= max_attempts:
                entry["locked_until"] = now + lock_seconds
                entry["failures"] = 0.0
            # 先写入再清理:保证「本次新增」也被计入上界,容量不会瞬时越界
            self._prune(now, ttl)
            return _lock_seconds_left(entry["locked_until"], now)

    def reset(self, key: str) -> None:
        """登录成功后清零该账号计数与锁定(只影响该账号)。"""
        with self._lock:
            self._entries.pop(key, None)

    def tracked_keys(self) -> int:
        """当前跟踪的账号数(用于容量上界回归)。"""
        with self._lock:
            return len(self._entries)

    def reset_all(self) -> None:
        """清空全部计数与锁定(测试隔离/运维排障;不改生产语义)。"""
        with self._lock:
            self._entries.clear()


_login_attempts = _LoginAttemptStore(max_entries=MAX_TRACKED_LOGIN_KEYS, clock=lambda: _monotonic())


def _lock_key(username: str) -> str:
    """锁定键:用户名去空白 + 转小写,避免大小写变体绕过计数。"""
    return (username or "").strip().lower()


def _lock_params() -> tuple:
    """从配置读取 (最大失败次数, 锁定秒数, 计数有效期秒数)。"""
    s = get_settings()
    lock_seconds = max(1, int(s.ADMIN_LOGIN_LOCK_MINUTES)) * 60
    return max(1, int(s.ADMIN_LOGIN_MAX_ATTEMPTS)), lock_seconds, lock_seconds


def _locked_message(remaining_seconds: int) -> str:
    return f"登录失败次数过多，账号已锁定，请在 {remaining_seconds} 秒后重试"


# ---- 管理员登录请求限流(窗口计数,进程内内存态) ----


class _LoginRateLimiter:
    """管理员登录请求限流(滑出窗口内的请求计数,进程内内存态)。

    维度(同一份配置,两把**独立**预算,任一超限即 429;取舍见 #PB-10 汇报):
    - `ip:<client_ip>`:对应真源「登录接口限制每分钟10次」,防单机高频尝试;
    - `user:<username>`:防轮换 IP 打同一账号。
    若合并为单一 (ip, username) 键,会同时放松上述两个维度,故不合并。

    与失败锁定(S2)语义独立:S2 只对**失败**按**用户名**连续计数并锁定;
    本限流对**全部请求**(含成功)按窗口计数,不锁定、只要求等窗口滑出;
    两者都挂在服务层,路由层无 if。

    边界:单进程内存态(多 worker/多实例各算一份、重启即失),需跨进程一致时须落库。
    上界:键数上限 max_entries(超出淘汰最旧键)+ 过期清理;单键时间戳数天然 ≤ max_requests
    (达上限后不再登记),内存有界。被拒请求不登记,避免持续攻击把窗口无限延后。
    """

    def __init__(self, max_entries: int, clock: Callable[[], float]) -> None:
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: Dict[str, list] = {}

    def _prune(self, now: float, window: float) -> None:
        """丢弃滑出窗口的时间戳并删除空键;仍超键数上限时淘汰最旧键(调用方须持锁)。"""
        for key in list(self._entries.keys()):
            stamps = [t for t in self._entries[key] if now - t < window]
            if stamps:
                self._entries[key] = stamps
            else:
                self._entries.pop(key, None)
        overflow = len(self._entries) - self._max_entries
        if overflow > 0:
            oldest = sorted(self._entries.items(), key=lambda kv: kv[1][-1])[:overflow]
            for key, _ in oldest:
                self._entries.pop(key, None)

    def record(self, keys: list, max_requests: int, window: float) -> int:
        """登记一次登录请求;任一键已达上限则**不登记**并返回需等待秒数,否则返回 0。"""
        now = self._clock()
        with self._lock:
            self._prune(now, window)
            for key in keys:
                stamps = self._entries.get(key)
                if stamps is not None and len(stamps) >= max_requests:
                    return max(1, math.ceil(window - (now - stamps[0])))
            for key in keys:
                self._entries.setdefault(key, []).append(now)
            # 登记后仍保证键数上界(本次新增键也计入)
            self._prune(now, window)
            return 0

    def tracked_keys(self) -> int:
        """当前跟踪的键数(用于容量上界回归)。"""
        with self._lock:
            return len(self._entries)

    def reset_all(self) -> None:
        """清空全部窗口计数(测试隔离/运维排障;不改生产语义)。"""
        with self._lock:
            self._entries.clear()


_login_rate_limiter = _LoginRateLimiter(max_entries=MAX_TRACKED_LOGIN_KEYS, clock=lambda: _monotonic())


def _rate_keys(ip: Optional[str], username: str) -> list:
    """登录限流键:每 IP 一份 + 每用户名一份(用户名小写归一,与失败锁定一致)。"""
    return [f"ip:{ip or 'unknown'}", f"user:{_lock_key(username)}"]


def _rate_params() -> tuple:
    """从配置读取 (窗口内最大请求次数, 窗口秒数)。"""
    s = get_settings()
    return max(1, int(s.ADMIN_LOGIN_RATE_MAX)), max(1, int(s.ADMIN_LOGIN_RATE_WINDOW_SECONDS))


def _rate_limited_message(retry_after_seconds: int) -> str:
    return f"登录请求过于频繁，请在 {retry_after_seconds} 秒后重试"


def reset_process_local_auth_state() -> None:
    """清空进程内认证状态(登录失败锁定 + 登录请求限流)。

    用途:① 测试夹具显式构造隔离边界(进程内状态会跨用例累计);
    ② 运维排障时手工清空(例如误锁测试账号)。不改生产语义(仅清空内存计数)。
    """
    _login_attempts.reset_all()
    _login_rate_limiter.reset_all()


# 开发/迁移期登录降级(对齐 NestJS LOGIN_MODE=mock,见 backend/.env.local)
MOCK_MERCHANT_ID = "mock_merchant_001"
MOCK_MERCHANT_NAME = "测试商家"
MOCK_OPEN_ID = "mock_open_id"


def merchant_login(db: Session, code: str) -> dict:
    """商家飞书登录:按 LOGIN_MODE 分支(SEC-01)。

    - LOGIN_MODE=mock(默认/本地):固定 mock_merchant_001 走 mock 降级(本地测试用);
    - LOGIN_MODE=real:走真实飞书 OAuth,失败绝不降级 mock(防未登录越权);
    - 其它取值已在 config 校验拒绝。
    """
    if not code or not code.strip():
        raise ApiException("授权码不能为空", code=400, status_code=400)

    mode = get_settings().LOGIN_MODE
    if mode == "real":
        return _merchant_login_real(db, code)
    # mock(默认)
    return _merchant_login_mock(db)


def _merchant_login_mock(db: Session) -> dict:
    """mock 登录(仅本地开发):固定 mock_merchant_001。"""
    merchant = upsert_from_feishu(db, MOCK_MERCHANT_ID, MOCK_MERCHANT_NAME, MOCK_OPEN_ID)
    token = create_merchant_token(MOCK_MERCHANT_ID)
    return {
        "token": token,
        "merchant": {
            "merchant_id": merchant.merchant_id,
            "nickname": merchant.nickname or MOCK_MERCHANT_NAME,
            "current_stage": merchant.current_stage,
            "feishu_open_id": merchant.feishu_open_id or MOCK_OPEN_ID,
        },
    }


def _merchant_login_real(db: Session, code: str) -> dict:
    """真实飞书登录:换 user_access_token + user_info,upsert 商家,返回 {token, merchant}。"""
    from app.services.feishu import login_feishu

    info = login_feishu(db, code)  # 失败在此抛错,不降级 mock
    open_id = info.get("open_id")
    if not open_id:
        raise ApiException("飞书登录失败，未获取到用户信息", code=502, status_code=502)
    merchant_id = "feishu_" + open_id  # 对齐 NestJS merchantId=feishu_${openId}
    nickname = info.get("name") or "飞书用户"
    merchant = upsert_from_feishu(db, merchant_id, nickname, open_id)
    token = create_merchant_token(merchant_id)
    return {
        "token": token,
        "merchant": {
            "merchant_id": merchant.merchant_id,
            "nickname": merchant.nickname or nickname,
            "current_stage": merchant.current_stage,
            "feishu_open_id": merchant.feishu_open_id or open_id,
        },
    }


def admin_login(db: Session, username: str, password: str, ip: Optional[str] = None) -> dict:
    """管理员登录:先过请求限流与失败锁定,再校验账号启用 + pbkdf2 密码,更新登录信息,返回 {token, admin}。

    两道进程内防护(均在服务层,路由层无 if;详见任务管理后台开发标准 §5.2/§7.1):
    - S1 请求限流:同一 IP、同一用户名在 ADMIN_LOGIN_RATE_WINDOW_SECONDS(默认 60 秒)内
      各最多 ADMIN_LOGIN_RATE_MAX(默认 10)次登录请求,超限 429 + 需等待秒数(不登记被拒请求);
    - S2 失败锁定:同一用户名连续失败达 ADMIN_LOGIN_MAX_ATTEMPTS(默认 5)即锁定
      ADMIN_LOGIN_LOCK_MINUTES(默认 30 分钟),锁定期内即使口令正确也拒绝(429 + 剩余锁定秒数),
      登录成功清零该账号失败计数。
    两者都实现为**单进程内存态**(多点部署/重启后失效,边界见两个存储类的 docstring)。
    """
    # S1:登录请求限流(先于失败锁定,高频请求直接挡在门外)
    rate_max, rate_window = _rate_params()
    retry_after = _login_rate_limiter.record(_rate_keys(ip, username), rate_max, rate_window)
    if retry_after > 0:
        raise ApiException(_rate_limited_message(retry_after), code=429, status_code=429)

    max_attempts, lock_seconds, ttl = _lock_params()
    key = _lock_key(username)

    remaining = _login_attempts.locked_seconds(key, ttl)
    if remaining > 0:
        raise ApiException(_locked_message(remaining), code=429, status_code=429)

    row = db.execute(
        text(
            "SELECT id, username, passwordHash, salt, realName, role "
            "FROM admin_account WHERE username = :u AND status = 1 AND deletedAt IS NULL"
        ),
        {"u": username},
    ).mappings().first()
    if row is None or not verify_password(password, row["passwordHash"], row["salt"]):
        remaining = _login_attempts.record_failure(key, max_attempts, lock_seconds, ttl)
        if remaining > 0:
            raise ApiException(_locked_message(remaining), code=429, status_code=429)
        raise ApiException("用户名或密码错误", code=401, status_code=401)

    # 登录成功:清零该账号失败计数与锁定
    _login_attempts.reset(key)

    # SEC-04 平滑迁移:旧格式(10000 迭代)账号验证通过后,顺手用 210000 重哈希升级(不失效)
    if needs_rehash(row["passwordHash"]):
        new_encoded, new_salt = hash_password(password)
        db.execute(
            text("UPDATE admin_account SET passwordHash = :h, salt = :s WHERE id = :id"),
            {"h": new_encoded, "s": new_salt, "id": row["id"]},
        )
        db.commit()

    # 更新最后登录(反映实际库 camelCase 列)
    db.execute(
        text("UPDATE admin_account SET lastLoginAt = :t, lastLoginIp = :ip WHERE id = :id"),
        {"t": datetime.now(), "ip": ip, "id": row["id"]},
    )
    db.commit()

    token = create_admin_token(row["id"], row["username"], row["role"])
    return {
        "token": token,
        "admin": {
            "id": str(row["id"]),
            "username": row["username"],
            "realName": row["realName"],
            "role": row["role"],
        },
    }


def admin_profile(admin: Dict[str, Any]) -> Dict[str, Any]:
    """当前管理员信息投影(对齐 NestJS admin-auth.controller getProfile)。

    admin 为 app.api.deps.get_current_admin 的返回(已按库校验存在且启用)。
    """
    return {
        "id": str(admin["sub"]),
        "username": admin["username"],
        "realName": admin["realName"],
        "role": admin["role"],
    }


def admin_change_password(db: Session, admin_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
    """管理员修改密码:校验旧密码 -> 写入新 pbkdf2 哈希(对齐 NestJS admin-auth.service.changePassword)。

    错误码沿用既有分段:旧密码错误 401;账号不可用 400(守卫已在校验期拦掉,此处兜底)。
    """
    row = db.execute(
        text("SELECT id, passwordHash, salt FROM admin_account WHERE id = :id AND status = 1"),
        {"id": admin_id},
    ).mappings().first()
    if row is None:
        raise ApiException("管理员不存在", code=400, status_code=400)
    if not verify_password(old_password, row["passwordHash"], row["salt"]):
        raise ApiException("旧密码错误", code=401, status_code=401)

    encoded, salt = hash_password(new_password)
    db.execute(
        text("UPDATE admin_account SET passwordHash = :h, salt = :s WHERE id = :id"),
        {"h": encoded, "s": salt, "id": admin_id},
    )
    db.commit()
    return {"success": True}
