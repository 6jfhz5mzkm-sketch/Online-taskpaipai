"""反馈处理 status 合法值校验回归(B2)。

背景:修复前 handle() 直接把入参 status 写库(FEEDBACK_STATUSES 常量已定义却未使用),
管理端可写入 "closed"/"done" 等任意状态,NestJS 侧由 UpdateFeedbackDto 的 @IsIn(FEEDBACK_STATUSES)
在进入 service 前拦截(ValidationPipe -> 400)。
修复后:service 用 FEEDBACK_STATUSES 校验,非法值返回既有 400 契约(不新造错误码),合法值行为不变。

隔离:临时管理员(make_temp_admin)+ 临时反馈记录(finally 删除)。
"""

from sqlalchemy import text

from tests.conftest import cleanup_temp_admin, make_temp_admin

TEST_ADMIN_PASSWORD = "Test@12345"


def _make_feedback(session) -> int:
    session.execute(
        text("INSERT INTO feedback (merchant_id, content, category, status) VALUES (NULL, '_test_feedback', '其他', 'pending')")
    )
    session.commit()
    return int(session.execute(text("SELECT id FROM feedback WHERE content = '_test_feedback' ORDER BY id DESC LIMIT 1")).scalar())


def _cleanup_feedback(session) -> None:
    session.execute(text("DELETE FROM feedback WHERE content = '_test_feedback'"))
    session.commit()


def _admin_token(client, session, username: str, password: str) -> str:
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["token"]


def test_handle_rejects_status_outside_contract(client, session):
    """非法 status -> 400,且不写库(状态保持 pending)。"""
    username, password = make_temp_admin(session)
    feedback_id = _make_feedback(session)
    try:
        token = _admin_token(client, session, username, password)
        for illegal in ("closed", "done", "PENDING", ""):
            resp = client.patch(
                f"/api/admin/feedback/{feedback_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": illegal},
            )
            assert resp.status_code == 400, (illegal, resp.text)
            assert resp.json()["code"] == 400
        current = session.execute(text("SELECT status FROM feedback WHERE id = :i"), {"i": feedback_id}).scalar()
        assert current == "pending"
    finally:
        _cleanup_feedback(session)
        cleanup_temp_admin(session, username)


def test_handle_accepts_contract_statuses(client, session):
    """合法 status(pending/processing/resolved)仍正常更新,handler_id 记录不变。"""
    username, password = make_temp_admin(session)
    feedback_id = _make_feedback(session)
    try:
        token = _admin_token(client, session, username, password)
        for legal in ("processing", "resolved", "pending"):
            resp = client.patch(
                f"/api/admin/feedback/{feedback_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": legal, "adminReply": "已处理"},
            )
            assert resp.status_code == 200, (legal, resp.text)
            body = resp.json()["data"]
            assert body["status"] == legal
            assert body["adminReply"] == "已处理"
            assert body["handlerId"] is not None
    finally:
        _cleanup_feedback(session)
        cleanup_temp_admin(session, username)
