"""统一错误文案回归(#PB-18 / #T-3 R6):中文友好 + 不泄露内部字段路径。

背景(生产验收 R6):校验错误返回 `body.password: String should have at least 6 characters`
(英文 + Pydantic 内部 Loc 前缀),404 返回英文 `Not Found`。
口径(已回写 后端技术方案 §4.3.1;#PB-24-1-R1 口语化):校验失败 400 + 固定中文「提交的内容有误，请检查后重试」
(**不回显英文字段名**、不含 body./query./path. 前缀、不暴露校验规则;完整 loc/type/msg 只进日志);
404「接口不存在」/405「请求方法不允许」;**响应信封 {code,message,data} 与状态码语义不变**;日志不含请求值。
"""

import logging

from app.core.error_handlers import VALIDATION_MESSAGE

SECRET = "PLAINTEXT_SECRET_VALUE"
LOGIN = "/api/admin/auth/login"


def _envelope(body):
    assert set(body) == {"code", "message", "data"}
    return body


def test_short_password_returns_chinese_message_without_internal_path(client):
    """① 口令过短 -> 400 口语化中文文案:不含 'String should have'/'body.',也不回显英文字段名。"""
    resp = client.post(LOGIN, json={"username": "ok_admin", "password": "short"})

    assert resp.status_code == 400, resp.text
    body = _envelope(resp.json())
    assert body["code"] == 400 and body["data"] is None
    assert body["message"] == VALIDATION_MESSAGE
    assert "String should have" not in body["message"]
    assert "body." not in body["message"]
    assert "password" not in body["message"]   # #PB-24-1-R1:英文字段名不再回显(排障看日志)


def test_missing_required_field_returns_chinese_message(client):
    """② 缺必填字段 -> 400 中文文案(不出现 'Field required'/'body.')。"""
    resp = client.post(LOGIN, json={})

    assert resp.status_code == 400, resp.text
    body = _envelope(resp.json())
    assert body["message"] == VALIDATION_MESSAGE
    assert "Field required" not in body["message"]
    assert "body." not in body["message"]


def test_validation_message_keeps_envelope_and_is_one_colloquial_sentence(client):
    """信封/状态码不变;多个字段同时非法也只给同一句固定文案(不逐字段回显)。"""
    resp = client.post(LOGIN, json={"username": "x", "password": "y"})

    assert resp.status_code == 400
    body = _envelope(resp.json())
    assert body["message"] == VALIDATION_MESSAGE
    assert "username" not in body["message"] and "password" not in body["message"]


def test_404_returns_chinese_message(client):
    """③ 404 -> 中文(信封与状态码不变)。"""
    resp = client.get("/api/__not_exist__")

    assert resp.status_code == 404
    assert resp.json() == {"code": 404, "message": "接口不存在", "data": None}


def test_405_returns_chinese_message(client):
    """③ 405 -> 中文(信封与状态码不变)。"""
    resp = client.delete(LOGIN)

    assert resp.status_code == 405
    assert resp.json() == {"code": 405, "message": "请求方法不允许", "data": None}


def test_business_error_message_unchanged(client):
    """重构错误出口后,业务异常(401)的文案与信封保持一致。"""
    resp = client.get("/api/merchant/info")

    assert resp.status_code == 401
    assert resp.json() == {"code": 401, "message": "未登录或 Token 已过期", "data": None}


def test_validation_log_keeps_detail_but_never_request_values(client, caplog):
    """④ 日志保留 loc/type/msg 以便排障,但**绝不包含请求体中的敏感值**。"""
    with caplog.at_level(logging.WARNING, logger="api"):
        resp = client.post(LOGIN, json={"username": [SECRET], "password": SECRET})

    assert resp.status_code == 400
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "参数校验失败" in logs
    assert "loc" in logs and "type" in logs and "msg" in logs   # 细节保留(可诊断性)
    assert SECRET not in logs                                   # Pydantic 的 input/ctx 不入日志
    assert resp.json()["message"].find(SECRET) == -1
