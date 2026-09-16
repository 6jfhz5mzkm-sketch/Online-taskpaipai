"""管理员登录请求限流(S1)回归(#PB-10)。

真源:project/docs/任务管理后台开发标准.md L716「Rate Limiting | 登录接口限制每分钟10次」。
实现位置:app/services/auth.py 的 _LoginRateLimiter(服务层单一真源);配置:
ADMIN_LOGIN_RATE_MAX(默认 10)/ ADMIN_LOGIN_RATE_WINDOW_SECONDS(默认 60);
维度:每 IP 一份 + 每用户名一份独立预算,任一超限返回 429 + 需等待秒数。

隔离:临时管理员(conftest.make_temp_admin)+ finally 删除;进程内计数由 conftest 的
autouse 夹具在每个用例前后清空(用例内部的状态累积照常生效)。
ip 预算同样在进程内:本文件涉及请求次数的用例一律用 conftest 的 login_client
(每用例独占一个 client IP),避免与其它用例共用 "testclient" 的 ip 预算而互相影响。
"""
import re

import app.services.auth as auth_service
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.main import app
from tests.conftest import cleanup_temp_admin, make_temp_admin

PASSWORD = "Test@12345"
_RETRY_AFTER = re.compile(r"(\d+) 秒后重试")
RATE_MESSAGE_PREFIX = "登录请求过于频繁"


def _login(client, username: str, password: str):
    return client.post("/api/admin/auth/login", json={"username": username, "password": password})


def _retry_after(resp) -> int:
    body = resp.json()
    assert body["code"] == 429, body
    assert body["data"] is None, body
    assert RATE_MESSAGE_PREFIX in body["message"], body
    matched = _RETRY_AFTER.search(body["message"])
    assert matched, body
    return int(matched.group(1))


def test_rate_limit_config_defaults():
    """限流默认值与真源一致(每分钟 10 次),且可经 env 覆盖(config 字段)。"""
    s = get_settings()
    assert s.ADMIN_LOGIN_RATE_MAX == 10
    assert s.ADMIN_LOGIN_RATE_WINDOW_SECONDS == 60


def test_within_limit_allows_login(login_client, session):
    """窗口内未超限(第 1..10 次)全部放行:成功登录会清零失败计数,故不会误触 S2 锁定。"""
    username, password = make_temp_admin(session)
    try:
        for i in range(1, 11):
            resp = _login(login_client, username, password)
            assert resp.status_code == 200, (i, resp.status_code, resp.text)
            assert resp.json()["data"]["token"]
    finally:
        cleanup_temp_admin(session, username)


def test_exceeding_limit_returns_429_with_retry_after(login_client, session):
    """第 11 次请求(即使口令正确)返回 429 且带需等待秒数(≤ 窗口长度)。"""
    username, password = make_temp_admin(session)
    try:
        for _ in range(10):
            assert _login(login_client, username, password).status_code == 200

        eleventh = _login(login_client, username, password)
        assert eleventh.status_code == 429, eleventh.text
        wait = _retry_after(eleventh)
        assert 0 < wait <= 60, wait

        # 被拒请求不登记:连续再打仍为 429,且等待时间不增加(窗口不被无限延后)
        twelfth = _login(login_client, username, password)
        assert twelfth.status_code == 429, twelfth.text
        assert _retry_after(twelfth) <= wait
    finally:
        cleanup_temp_admin(session, username)


def test_window_rollover_recovers(login_client, session, monkeypatch):
    """窗口滑出后恢复:时钟前进 61 秒即可再次登录。"""
    username, password = make_temp_admin(session)
    try:
        for _ in range(10):
            assert _login(login_client, username, password).status_code == 200
        assert _login(login_client, username, password).status_code == 429

        frozen = auth_service._monotonic()
        monkeypatch.setattr(auth_service, "_monotonic", lambda: frozen + 61)

        recovered = _login(login_client, username, password)
        assert recovered.status_code == 200, recovered.text
    finally:
        cleanup_temp_admin(session, username)


def test_username_budget_is_enforced_across_ips(session):
    """每用户名独立预算:换 IP 也不能绕过(轮换 IP 打同一账号同样被限)。"""
    username, password = make_temp_admin(session)
    try:
        first_ip_client = TestClient(app, client=("10.0.0.1", 50000))
        second_ip_client = TestClient(app, client=("10.0.0.2", 50000))
        with first_ip_client, second_ip_client:
            for i in range(10):
                assert _login(first_ip_client, username, password).status_code == 200, i
            # 新 IP 的 ip 预算未用,但 user 预算已满 -> 仍 429
            blocked = _login(second_ip_client, username, password)
            assert blocked.status_code == 429, blocked.text
            assert _retry_after(blocked) > 0
    finally:
        cleanup_temp_admin(session, username)


def test_ip_budget_is_enforced_across_usernames(login_client, session):
    """每 IP 独立预算:同 IP 轮换用户名也不能绕过(第 11 个用户名的请求被限)。"""
    names = [make_temp_admin(session) for _ in range(11)]
    try:
        for username, password in names[:10]:
            assert _login(login_client, username, password).status_code == 200
        last_username, last_password = names[10]
        blocked = _login(login_client, last_username, last_password)
        assert blocked.status_code == 429, blocked.text
        assert _retry_after(blocked) > 0
    finally:
        for username, _ in names:
            cleanup_temp_admin(session, username)


def test_rate_limiter_store_is_bounded_and_pruned():
    """限流存储上界与过期清理:键数不超上限、滑出窗口的键被清除、单键时间戳不超过阈值。"""
    clock = {"now": 1000.0}
    limiter = auth_service._LoginRateLimiter(max_entries=3, clock=lambda: clock["now"])
    for i in range(10):
        clock["now"] += 1
        limiter.record([f"user:u{i}", f"ip:10.0.0.{i}"], max_requests=2, window=60)
    assert limiter.tracked_keys() <= 3, limiter.tracked_keys()

    clock["now"] += 61
    limiter.record(["user:fresh"], max_requests=2, window=60)
    assert limiter.tracked_keys() == 1, limiter.tracked_keys()

    # 单键时间戳有界:达到阈值(第 2 次)后不再登记,后续调用只返回等待时间
    assert limiter.record(["user:fresh"], max_requests=2, window=60) == 0   # 第 2 次,达上限
    assert limiter.record(["user:fresh"], max_requests=2, window=60) > 0    # 第 3 次:被拒且不登记
    assert limiter.record(["user:fresh"], max_requests=2, window=60) > 0
    assert limiter.tracked_keys() == 1
