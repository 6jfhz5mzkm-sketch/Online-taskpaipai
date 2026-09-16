"""顾问企微二维码静态端点回归(#PB-20)。

真源 §5.2:`GET /api/static/advisor-qr.jpg` —— 单文件、**无需登录**、路径**只来自配置**;
文件缺失 -> 结构化 404;配置越界/非普通文件/不可读 -> 结构化 500(不回显绝对路径)。
`/api/feishu/advisor-qr` 的 `qr_url` 即该路径。

纪律:测试只在 `api-py/static/` 下建临时假图片并在 finally 删除;**不提交真实图片**、不真实外呼。
"""

import pytest
from fastapi.testclient import TestClient

from app.api.v1.static_assets import (
    ADVISOR_QR_ROUTE,
    CACHE_CONTROL,
    MISSING_MESSAGE,
    UNAVAILABLE_MESSAGE,
    resolve_advisor_qr_path,
)
from app.core.config import BASE_DIR, get_settings
from app.core.security import create_merchant_token
from app.main import app
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

ROUTE = "/api/static" + ADVISOR_QR_ROUTE
TEST_REL = "static/_test_advisor_qr.jpg"
MISSING_REL = "static/_test_missing_advisor_qr.jpg"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"placeholder-image-payload"


@pytest.fixture()
def advisor_qr_file(monkeypatch):
    """建临时图片并把 ADVISOR_QR_FILE 指向它;结束后删除文件与恢复配置(monkeypatch 自动恢复)。"""
    path = BASE_DIR / TEST_REL
    path.write_bytes(JPEG_BYTES)
    monkeypatch.setattr(get_settings(), "ADVISOR_QR_FILE", TEST_REL)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def test_serves_configured_file_with_image_type_and_cache_header(client, advisor_qr_file):
    """① 配置的文件存在 -> 200 + image/jpeg + Cache-Control,内容与文件字节一致。"""
    resp = client.get(ROUTE)

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/")
    assert resp.headers["cache-control"] == CACHE_CONTROL
    assert resp.content == JPEG_BYTES


def test_missing_file_returns_structured_404(client, monkeypatch):
    """② 文件不存在 -> 结构化 404(统一信封),不是 500、不是空图。"""
    monkeypatch.setattr(get_settings(), "ADVISOR_QR_FILE", MISSING_REL)

    resp = client.get(ROUTE)

    assert resp.status_code == 404
    assert resp.json() == {"code": 404, "message": MISSING_MESSAGE, "data": None}


def test_endpoint_does_not_require_auth(client, advisor_qr_file, monkeypatch):
    """④ 无需鉴权:带不带 Authorization 结果一致,且绝不返回 401。"""
    ok = client.get(ROUTE)
    assert ok.status_code == 200
    assert "www-authenticate" not in {k.lower() for k in ok.headers}

    monkeypatch.setattr(get_settings(), "ADVISOR_QR_FILE", MISSING_REL)
    missing = client.get(ROUTE)
    assert missing.status_code == 404        # 未登录也应拿到 404,而不是 401
    assert "authorization" not in missing.request.headers


def test_configured_path_cannot_escape_base_dir():
    """③ 路径只来自配置,且被约束在 api-py 目录内:越界配置直接抛错(无拼接入口)。"""
    assert resolve_advisor_qr_path(TEST_REL) == (BASE_DIR / TEST_REL).resolve()

    for illegal in ("../pyproject.toml", "static/../../pyproject.toml", "", "   "):
        with pytest.raises(ValueError):
            resolve_advisor_qr_path(illegal)


def test_traversal_requests_are_not_served(client, advisor_qr_file):
    """③' 带 ../ 的请求不会读到其它文件(固定路由 + 无路径参数)。"""
    for target in ("/api/static/../app/core/config.py",
                   "/api/static/%2e%2e/app/core/config.py",
                   "/api/static/advisor-qr.jpg/../../app/core/config.py"):
        resp = client.get(target)
        assert resp.status_code == 404, (target, resp.status_code)
        assert b"ADVISOR_QR_FILE" not in resp.content      # 不能把 config.py 源码吐出来


def test_static_route_has_no_path_parameters(client):
    """③'' 结构上不存在拼接入口:/api/static 下只有一个固定路径,且没有 {param} 段。"""
    static_paths = [p for p in app.openapi()["paths"] if p.startswith("/api/static")]

    assert static_paths == [ROUTE]
    assert all("{" not in p for p in static_paths)


def test_directory_or_escaping_config_returns_500_without_leaking_path(client, monkeypatch):
    """文件存在但非普通文件 / 配置越界 -> 结构化 500,响应不回显绝对路径。"""
    for bad_config in ("static", "../pyproject.toml"):
        monkeypatch.setattr(get_settings(), "ADVISOR_QR_FILE", bad_config)
        resp = client.get(ROUTE)

        assert resp.status_code == 500, (bad_config, resp.status_code)
        assert resp.json()["message"] == UNAVAILABLE_MESSAGE
        assert str(BASE_DIR) not in resp.text        # 不泄露绝对路径


def test_feishu_advisor_qr_points_to_static_route(client, session):
    """文档口径一致性:/api/feishu/advisor-qr 返回的 qr_url 就是该静态路径。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.get("/api/feishu/advisor-qr",
                          headers={"Authorization": f"Bearer {create_merchant_token(merchant_id)}"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["qr_url"] == ROUTE
    finally:
        cleanup_temp_merchant(session, merchant_id)
