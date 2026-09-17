"""API-10 飞书通知服务层回归(#PB-11)。

真源:project/docs/后端技术方案.md §5.2 API-10(查 merchant 飞书 id -> 频控 -> 发送 -> 落库)。
频控仅对 task_reminder 生效、窗口 48h;发送失败落 failed 记录且不抛异常(通知降级面)。
外部飞书调用通过注入 sender 打桩,测试绝不真实外呼。
隔离:临时商家 + finally 清理 feishu_notification 临时行。
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app.core.exceptions import ApiException
from app.services import feishu
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

OPEN_ID = "<OPEN_ID>_notify_001"


class _Sender:
    """可注入的发送桩:记录调用并按预设成功/失败返回。"""

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls = []

    def __call__(self, open_id: str, content: str) -> bool:
        self.calls.append((open_id, content))
        return self.ok


def _merchant(session, *, with_binding: bool = True) -> str:
    merchant_id = make_temp_merchant(session)
    if with_binding:
        session.execute(
            text("UPDATE merchant SET feishu_open_id = :o WHERE merchant_id = :m"), {"o": OPEN_ID, "m": merchant_id}
        )
        session.commit()
    return merchant_id


def _insert_notification(session, merchant_id: str, sent_at: datetime, template_type: str = "task_reminder") -> int:
    session.execute(
        text(
            "INSERT INTO feishu_notification (merchant_id, template_type, title, content, status, sent_at) "
            "VALUES (:m, :t, '_test 标题', '_test 内容', 'sent', :s)"
        ),
        {"m": merchant_id, "t": template_type, "s": sent_at},
    )
    session.commit()
    return int(
        session.execute(
            text("SELECT id FROM feishu_notification WHERE merchant_id = :m ORDER BY id DESC LIMIT 1"), {"m": merchant_id}
        ).scalar()
    )


def _notification_count(session, merchant_id: str) -> int:
    return int(
        session.execute(
            text("SELECT COUNT(*) FROM feishu_notification WHERE merchant_id = :m"), {"m": merchant_id}
        ).scalar()
    )


def _last_notification(session, merchant_id: str):
    return session.execute(
        text(
            "SELECT id, template_type, title, content, status, error_msg, h5_url FROM feishu_notification "
            "WHERE merchant_id = :m ORDER BY id DESC LIMIT 1"
        ),
        {"m": merchant_id},
    ).mappings().first()


def _cleanup(session, merchant_id: str) -> None:
    session.execute(text("DELETE FROM feishu_notification WHERE merchant_id = :m"), {"m": merchant_id})
    session.commit()
    cleanup_temp_merchant(session, merchant_id)


def test_send_notification_success_records_row(session):
    """首次发送:调用 sender + 落库 status='sent',返回 notification_id。"""
    merchant_id = _merchant(session)
    try:
        sender = _Sender(ok=True)
        result = feishu.send_notification(
            session, merchant_id, "task_reminder", {"content": "_test 正文", "h5_url": "https://example.com/x"}, sender
        )
        assert result["success"] is True and result["skipped"] is False and result["reason"] is None
        assert result["notification_id"] is not None
        assert sender.calls == [(OPEN_ID, "_test 正文")]

        row = _last_notification(session, merchant_id)
        assert row["template_type"] == "task_reminder"
        assert row["title"] == feishu.NOTIFICATION_TEMPLATES["task_reminder"]
        assert row["content"] == "_test 正文"
        assert row["status"] == "sent" and row["error_msg"] is None
        assert row["h5_url"] == "https://example.com/x"
    finally:
        _cleanup(session, merchant_id)


def test_skips_within_48h_window(session):
    """48h 内已推送过 -> 跳过:不发送、不落库、不报错。"""
    merchant_id = _merchant(session)
    try:
        _insert_notification(session, merchant_id, datetime.now() - timedelta(hours=1))
        sender = _Sender(ok=True)
        result = feishu.send_notification(session, merchant_id, "task_reminder", None, sender)
        assert result == {"success": True, "notification_id": None, "skipped": True, "reason": "frequency_limited"}
        assert sender.calls == []
        assert _notification_count(session, merchant_id) == 1
    finally:
        _cleanup(session, merchant_id)


def test_sends_when_last_sent_over_48h(session):
    """超过 48h(49h 前)-> 正常发送并新增一条记录。"""
    merchant_id = _merchant(session)
    try:
        _insert_notification(session, merchant_id, datetime.now() - timedelta(hours=49))
        sender = _Sender(ok=True)
        result = feishu.send_notification(session, merchant_id, "task_reminder", None, sender)
        assert result["success"] is True and result["skipped"] is False
        assert len(sender.calls) == 1
        assert _notification_count(session, merchant_id) == 2
    finally:
        _cleanup(session, merchant_id)


def test_non_controlled_template_not_rate_limited(session):
    """频控仅覆盖 task_reminder:其他模板连续两次都发送(不误伤)。"""
    merchant_id = _merchant(session)
    try:
        sender = _Sender(ok=True)
        for _ in range(2):
            result = feishu.send_notification(session, merchant_id, "welcome", None, sender)
            assert result["skipped"] is False
        assert len(sender.calls) == 2
        assert _notification_count(session, merchant_id) == 2
    finally:
        _cleanup(session, merchant_id)


def test_requires_feishu_binding(session):
    """商家未绑定飞书(feishu_open_id 为空)-> ApiException 400「商家未绑定飞书」。"""
    merchant_id = _merchant(session, with_binding=False)
    try:
        with pytest.raises(ApiException) as excinfo:
            feishu.send_notification(session, merchant_id, "task_reminder", None, _Sender())
        assert excinfo.value.code == 400
        assert excinfo.value.message == "商家未绑定飞书"
        assert _notification_count(session, merchant_id) == 0
    finally:
        _cleanup(session, merchant_id)


def test_rejects_unknown_template_type(session):
    """template_type 不在枚举范围 -> 400。"""
    merchant_id = _merchant(session)
    try:
        with pytest.raises(ApiException) as excinfo:
            feishu.send_notification(session, merchant_id, "not_a_template", None, _Sender())
        assert excinfo.value.code == 400
        assert excinfo.value.message == "template_type 不在枚举范围"
    finally:
        _cleanup(session, merchant_id)


def test_send_failure_records_failed_row_without_raising(session):
    """发送失败:落库 status='failed' + error_msg,返回 success=False 且不抛异常。"""
    merchant_id = _merchant(session)
    try:
        result = feishu.send_notification(session, merchant_id, "task_reminder", None, _Sender(ok=False))
        assert result["success"] is False
        assert result["reason"] == "send_failed"
        assert result["skipped"] is False
        row = _last_notification(session, merchant_id)
        assert row["status"] == "failed"
        assert row["error_msg"] == "飞书消息发送失败"
    finally:
        _cleanup(session, merchant_id)
