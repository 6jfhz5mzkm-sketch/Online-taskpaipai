"""核心接口契约测试。

隔离策略:打到本地 dev MySQL(merchant_task);只读接口零写入,写路径用临时实体并在 finally 清理(见 conftest)。
覆盖:商家登录(mock)、管理员登录(正确/错误密码)、类目列表、阶段列表、
店铺 Excel 上传(正常计数 + 脏值 _to_num 跳过)、超大图片 400、无 token 401、参数校验 400。
"""

import io

from app.core.security import create_merchant_token
from app.services.shop import _to_num

from tests.conftest import (
    MOCK_MERCHANT_ID,
    cleanup_temp_admin,
    cleanup_temp_merchant,
    make_temp_admin,
    make_temp_merchant,
)

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _merchant_token(merchant_id: str = MOCK_MERCHANT_ID) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _make_excel(rows) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.read()


# ---------- auth ----------

def test_merchant_login_mock(client):
    """商家登录(LOGIN_MODE=mock):POST /api/auth/feishu/callback -> 201 + token,固定 mock_merchant_001。"""
    resp = client.post("/api/auth/feishu/callback", json={"code": "test"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["merchant"]["merchant_id"] == MOCK_MERCHANT_ID


def test_admin_login_ok(client, session):
    """管理员登录(正确密码)-> 200 + token + admin 信息。用临时管理员,结束清理。"""
    username, password = make_temp_admin(session)
    try:
        resp = client.post(
            "/api/admin/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["token"]
        assert body["data"]["admin"]["username"] == username
    finally:
        cleanup_temp_admin(session, username)


def test_admin_login_wrong_password(client, session):
    """管理员登录(错误密码)-> 401 + code=401。用临时管理员,结束清理。"""
    username, password = make_temp_admin(session)
    try:
        resp = client.post(
            "/api/admin/auth/login",
            json={"username": username, "password": "wrong-pass-123"},
        )
        assert resp.status_code == 401, resp.text
        body = resp.json()
        assert body["code"] == 401
        assert body["data"] is None
    finally:
        cleanup_temp_admin(session, username)


# ---------- 读接口(零写入) ----------

def test_no_token_401(client):
    """无 token 访问商家端接口 -> 401 + code=401。"""
    resp = client.get("/api/category/list")
    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == 401


def test_category_list(client):
    """GET /api/category/list(带商家 token)-> 200,返回一级类目列表(数据为只读)。"""
    resp = client.get("/api/category/list", headers=_merchant_token())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert isinstance(data, list) and len(data) >= 1
    for item in data:
        assert "id" in item and "name" in item and "parent_id" in item


def test_task_stages(client):
    """GET /api/task/stages(带商家 token)-> 200,返回阶段列表(含 onboarding 阶段一)。"""
    resp = client.get("/api/task/stages", headers=_merchant_token())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert isinstance(data, list) and len(data) >= 1
    assert any(s["stageId"] == "onboarding" for s in data)


# ---------- 参数校验 ----------

def test_param_validation_400(client):
    """参数校验失败:管理员登录密码过短(min_length=6)-> 400 + code=400。"""
    resp = client.post(
        "/api/admin/auth/login",
        json={"username": "whatever", "password": "123"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == 400


# ---------- shop ----------

def test_to_num_dirty():
    """_to_num 脏值保护:解析失败返回 None(跳过),千分位/百分号被干净解析。"""
    assert _to_num(None) is None
    assert _to_num("") is None
    assert _to_num(5) == 5
    assert _to_num(5.5) == 5.5
    assert _to_num("1,234.56") == 1234.56          # ASCII 千分位
    assert _to_num("1，234") == 1234.0              # 全角逗号
    assert _to_num("10%") == 10.0                   # 百分号
    assert _to_num("约10万") is None                 # 脏值 -> 跳过
    assert _to_num("abc") is None


def test_excel_upload_count(client, session):
    """POST /api/shop/trade 上传合法 Excel -> 201 + count。正常行计数,脏值单元格被跳过不中断整批。"""
    merchant_id = make_temp_merchant(session)
    try:
        rows = [
            ["时间", "成交金额", "成交单量", "成交客户数"],
            ["2026-01-01", "1000.50", "5", "3"],          # 正常行
            ["2026-01-02", "N/A", "6", "4"],              # 成交金额脏值 -> _to_num 跳过,其余字段有效 -> 行仍入库
        ]
        resp = client.post(
            "/api/shop/trade",
            headers=_merchant_token(merchant_id),
            files={"file": ("trade.xlsx", _make_excel(rows), EXCEL_MIME)},
            data={"timeRange": "7d"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["count"] == 2
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_oversize_image_400(client):
    """POST /api/shop/image-optimize 超大图片(>5MB)-> 400,不进入 AI 处理。"""
    big = b"x" * (5 * 1024 * 1024 + 1)
    resp = client.post(
        "/api/shop/image-optimize",
        headers=_merchant_token(),
        files={"file": ("a.png", big, "image/png")},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == 400
