"""请求工具(SEC-02 可信 IP / PII 脱敏)。"""
from fastapi import Request

from app.core.config import get_settings


def mask_phone(phone: str | None) -> str:
    """手机号脱敏(日志 / 内部通知统一入口):保留前 3 后 4,如 `138****8000`。

    口径(#PB-23 G-5):手机号**明文存储**(参与唯一键与检索),但**任何日志与通知都不得出现完整号码**。
    长度不足以脱敏时一律返回 `***`,绝不原样回显。
    """
    value = (phone or "").strip()
    if len(value) < 7:
        return "***"
    return value[:3] + "****" + value[-4:]


def mask_jd_merchant_id(jd_merchant_id: str | None) -> str:
    """京麦商家ID 部分脱敏(内部通知用):保留前 4 后 4,中间 `****`;长度 < 8 时一律 `****`。

    口径(#PB-36 / 方案 §5.3):IM 通道有第三方可见风险,不外泄完整 ID;但运营需要能对上号,
    故保留首尾便于人工比对——完整值可在管理后台按 `keyword` 搜索定位(不需要写进通知)。
    """
    value = (jd_merchant_id or "").strip()
    if len(value) < 8:
        return "****"
    return value[:4] + "****" + value[-4:]


def get_client_ip(request: Request) -> str:
    """取客户端真实 IP,用于限流/审计(不信任客户端可控的 X-Forwarded-For)。

    策略:
    - 默认(request.client.host):直接取 TCP 对端(客户端/反向代理),绝不信任客户端填的 XFF(可伪造);
    - 若配置且确认部署在可信反向代理后:
        settings.TRUST_PROXY=True 且 TCP 对端在 TRUSTED_PROXIES 内,才解析 X-Forwarded-For;
        从右向左跳过可信代理,取第一个非可信代理 = 真实客户端(对齐 nginx 追加式 XFF);
    - 非法/全为可信代理 -> 回退 TCP 对端。
    """
    peer = request.client.host if request.client else "unknown"
    settings = get_settings()
    if settings.TRUST_PROXY and peer in settings.TRUSTED_PROXIES:
        xff = request.headers.get("X-Forwarded-For") or ""
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        for ip_part in reversed(parts):
            if ip_part not in settings.TRUSTED_PROXIES:
                return ip_part
        return peer
    return peer
