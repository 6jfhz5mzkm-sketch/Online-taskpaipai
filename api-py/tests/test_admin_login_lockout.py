"""管理员登录失败锁定回归(#PB-9)。

真源:project/docs/任务管理后台开发标准.md L574「登录失败锁定:连续5次失败锁定30分钟」。
实现位置:app/services/auth.py(服务层单一真源;路由层无 if);阈值/时长走配置:
ADMIN_LOGIN_MAX_ATTEMPTS(默认 5)/ ADMIN_LOGIN_LOCK_MINUTES(默认 30)。

隔离:临时管理员(conftest.make_temp_admin,用户名带 _test_ 前缀且唯一)+ finally 删除。
锁定状态是进程内内存态,按唯一用户名隔离,不跨用例污染。
限流状态同样在进程内,按 ip:<client> 与 user:<name> 各记一份预算:本文件的用例一律使用
conftest 的 login_client(每用例独占一个 client IP),避免与其它用例共用 ip 预算而使
「第 N 次请求」的语义随全局调用次数漂移。
"""
import re

import app.services.auth as auth_service
from app.core.config import get_settings
from tests.conftest import cleanup_temp_admin, make_temp_admin

_REMAINING = re.compile(r"(\d+) 秒后重试")
LOCKED_MESSAGE_PREFIX = "登录失败次数过多"


def _login(client, username: str, password: str):
    return client.post("/api/admin/auth/login", json={"username": username, "password": password})


def _remaining_seconds(resp) -> int:
    """从 429 响应 message 中解析剩余锁定秒数(响应契约:{code,message,data:null})。"""
    body = resp.json()
    assert body["code"] == 429, body
    assert body["data"] is None, body
    assert LOCKED_MESSAGE_PREFIX in body["message"], body
    matched = _REMAINING.search(body["message"])
    assert matched, body
    return int(matched.group(1))


def test_lockout_config_defaults():
    """阈值/时长默认值与真源一致,且可经 env 覆盖(config 字段)。"""
    s = get_settings()
    assert s.ADMIN_LOGIN_MAX_ATTEMPTS == 5
    assert s.ADMIN_LOGIN_LOCK_MINUTES == 30


def test_below_threshold_still_allows_login(login_client, session):
    """未达阈值(4 次)只返回 401,正确口令仍可登录。"""
    username, password = make_temp_admin(session)
    try:
        for _ in range(4):
            resp = _login(login_client, username, "WrongPass@1")
            assert resp.status_code == 401, resp.text
            assert resp.json()["message"] == "用户名或密码错误"

        ok = _login(login_client, username, password)
        assert ok.status_code == 200, ok.text
        assert ok.json()["data"]["token"]
    finally:
        cleanup_temp_admin(session, username)


def test_reaching_threshold_locks_even_with_correct_password(login_client, session):
    """第 5 次失败即锁定(429 + 剩余秒数);锁定期内正确口令同样被拒。"""
    username, password = make_temp_admin(session)
    try:
        for i in range(4):
            resp = _login(login_client, username, "WrongPass@1")
            assert resp.status_code == 401, (i, resp.text)

        fifth = _login(login_client, username, "WrongPass@1")
        assert fifth.status_code == 429, fifth.text
        remaining = _remaining_seconds(fifth)
        assert 0 < remaining <= 30 * 60, remaining

        # 第 6 次(即使口令正确)仍被拒,且剩余时间递减
        sixth = _login(login_client, username, password)
        assert sixth.status_code == 429, sixth.text
        assert _remaining_seconds(sixth) <= remaining
    finally:
        cleanup_temp_admin(session, username)


def test_unknown_username_failures_also_lock(login_client, session):
    """未知用户名的连续 5 次失败同样触发锁定(不泄露账号是否存在)。

    独立用例 + 独占 client IP:该分支原先与锁定主用例共用同一个 IP,两段合计 11 次请求
    已越过 ip 预算(10 次/60 秒),第 11 次拿到的是**限流** 429,而断言只看 status_code=429
    → 是假通过(实际从未验证到锁定)。拆出后按锁定文案断言,真正覆盖该语义。
    """
    username, password = make_temp_admin(session)
    try:
        unknown = f"_test_ghost_{username}"
        for i in range(4):
            resp = _login(login_client, unknown, "WrongPass@1")
            assert resp.status_code == 401, (i, resp.text)

        fifth = _login(login_client, unknown, "WrongPass@1")
        assert fifth.status_code == 429, fifth.text
        assert _remaining_seconds(fifth) > 0
    finally:
        cleanup_temp_admin(session, username)


def test_lock_expires_and_login_recovers(login_client, session, monkeypatch):
    """锁定期结束后(单调时钟前进 31 分钟)正确口令可正常登录。"""
    username, password = make_temp_admin(session)
    try:
        for i in range(4):
            resp = _login(login_client, username, "WrongPass@1")
            assert resp.status_code == 401, (i, resp.status_code, resp.text)  # 显式断言,避免瞬时异常被吞
        fifth = _login(login_client, username, "WrongPass@1")
        assert fifth.status_code == 429, (fifth.status_code, fifth.text)
        assert _login(login_client, username, password).status_code == 429

        frozen = auth_service._monotonic()
        monkeypatch.setattr(auth_service, "_monotonic", lambda: frozen + 31 * 60)

        recovered = _login(login_client, username, password)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["data"]["token"]
    finally:
        cleanup_temp_admin(session, username)


def test_success_resets_failure_counter(login_client, session):
    """成功登录清零计数:4 次失败 + 成功 + 4 次失败,不得被锁。"""
    username, password = make_temp_admin(session)
    try:
        for _ in range(4):
            assert _login(login_client, username, "WrongPass@1").status_code == 401
        assert _login(login_client, username, password).status_code == 200

        for _ in range(4):
            resp = _login(login_client, username, "WrongPass@1")
            assert resp.status_code == 401, resp.text
    finally:
        cleanup_temp_admin(session, username)


def test_attempt_store_is_bounded_and_pruned():
    """存储上界与过期清理:超过容量上限时淘汰最旧项,过期项被清除(禁止无界增长)。"""
    clock = {"now": 1000.0}
    store = auth_service._LoginAttemptStore(max_entries=3, clock=lambda: clock["now"])
    for i in range(10):
        clock["now"] += 1
        store.record_failure(f"user{i}", max_attempts=5, lock_seconds=1800, ttl=1800)
    assert store.tracked_keys() <= 3, store.tracked_keys()

    clock["now"] += 1801
    assert store.locked_seconds("user9", 1800) == 0
    assert store.tracked_keys() == 0, store.tracked_keys()
