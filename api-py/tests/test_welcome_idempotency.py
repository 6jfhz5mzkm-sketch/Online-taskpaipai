"""欢迎卡片幂等标志语义回归(#PB-19)。

口径:`merchant.welcome_sent = 1` 表示**已成功发送**;发送失败**不置位**(保持 0)以便后续重试;
已为 1 时跳过且不调用发送。
修正前无论成败都置 1 -> 一次发送失败后该商家永远不会再收到欢迎卡片(生产 2026-09-14 实证)。

纪律:全程打桩,零真实外呼;open_id 用占位符,不打印任何真实凭据。
"""

import logging

import pytest

from app.services import feishu as feishu_service

OPEN_ID_PLACEHOLDER = "<OPEN_ID>_value"


class _Mappings:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row

    def all(self):
        return [self._row] if self._row else []


class _Result:
    """execute() 的返回对象:提供 .mappings()(与 SQLAlchemy Result 一致)。"""

    def __init__(self, row):
        self._row = row

    def mappings(self):
        return _Mappings(self._row)


class _FakeSession:
    """最小会话替身:记录 SQL 与提交次数,不连库。"""

    def __init__(self, welcome_sent=0):
        self.welcome_sent = welcome_sent
        self.statements = []
        self.commits = 0

    def execute(self, stmt, params=None):
        sql = str(stmt)
        self.statements.append(sql)
        if sql.strip().upper().startswith("UPDATE") and "welcome_sent" in sql:
            self.welcome_sent = 1
        row = {"welcome_sent": self.welcome_sent} if "SELECT" in sql.upper() else None
        return _Result(row)

    def commit(self):
        self.commits += 1

    def updates(self):
        return [s for s in self.statements if s.strip().upper().startswith("UPDATE")]


def test_success_sets_welcome_sent_and_returns_sent_true(monkeypatch):
    """① 发送成功 -> 置 welcome_sent=1 且返回 sent=True/first=True。"""
    monkeypatch.setattr(feishu_service, "_send_card", lambda open_id, content: True)
    db = _FakeSession(welcome_sent=0)

    result = feishu_service.welcome_on_first(db, "m1", OPEN_ID_PLACEHOLDER, "名字占位符")

    assert result == {"sent": True, "first": True}
    assert db.welcome_sent == 1
    assert len(db.updates()) == 1 and "welcome_sent = 1" in db.updates()[0]
    assert db.commits == 1


def test_failure_keeps_flag_zero_and_allows_retry(monkeypatch, caplog):
    """② 发送失败 -> welcome_sent 仍为 0(不置位)、返回 sent=False,且下次登录可重试成功。"""
    monkeypatch.setattr(feishu_service, "_send_card", lambda open_id, content: False)
    db = _FakeSession(welcome_sent=0)

    with caplog.at_level(logging.WARNING, logger="api"):
        result = feishu_service.welcome_on_first(db, "m1", OPEN_ID_PLACEHOLDER, "名字占位符")

    assert result == {"sent": False, "first": True}
    assert db.welcome_sent == 0                 # 关键:失败不置位
    assert db.updates() == []                   # 不执行任何 UPDATE
    assert db.commits == 0
    assert any("保留 welcome_sent=0" in record.getMessage() for record in caplog.records)

    # 允许重试:下一次登录发送成功 -> 此时才置位
    monkeypatch.setattr(feishu_service, "_send_card", lambda open_id, content: True)
    retry = feishu_service.welcome_on_first(db, "m1", OPEN_ID_PLACEHOLDER, "名字占位符")

    assert retry == {"sent": True, "first": True}
    assert db.welcome_sent == 1


def test_already_sent_skips_without_calling_send(monkeypatch):
    """③ 已置位 -> 跳过、不调用发送、不执行 UPDATE(幂等语义保持不变)。"""
    def _boom(open_id, content):
        raise AssertionError("已发送过的商家不应再调用发送")

    monkeypatch.setattr(feishu_service, "_send_card", _boom)
    db = _FakeSession(welcome_sent=1)

    result = feishu_service.welcome_on_first(db, "m1", OPEN_ID_PLACEHOLDER, "名字占位符")

    assert result == {"sent": False, "first": False}
    assert db.updates() == []
    assert db.commits == 0


@pytest.mark.parametrize("stored_value", [1, "1", True])
def test_truthy_flag_variants_are_treated_as_already_sent(monkeypatch, stored_value):
    """存量值形态兼容:TINYINT 可能以 1/"1"/True 读回,均视为已发送(不重复发)。"""
    monkeypatch.setattr(feishu_service, "_send_card", lambda open_id, content: (_ for _ in ()).throw(AssertionError("不应发送")))
    db = _FakeSession()
    db.welcome_sent = stored_value

    assert feishu_service.welcome_on_first(db, "m1", OPEN_ID_PLACEHOLDER, "名字占位符") == {"sent": False, "first": False}
    assert db.updates() == []
