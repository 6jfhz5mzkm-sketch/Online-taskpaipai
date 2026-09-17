"""管理端认证与账号 CRUD 回归(#PB-7 追加范围 A/B)。

契约基准(总控裁决:前端真实调用 + NestJS 既有实现优先):
- admin/src/api/auth.ts:GET /admin/auth/profile、POST /admin/auth/change-password
- admin/src/api/account.ts:POST /admin/account/create、PUT /admin/account/{id}、
  DELETE /admin/account/{id}、POST /admin/account/{id}/reset-password
权限口径(§6.3 / #AF-4):列表与详情 = 需登录;写操作(create/update/delete/reset-password/generate)= super_admin。

隔离:临时管理员(_test_ 前缀,finally 删除),不触碰真实管理员账号。
"""
import uuid

from app.core.security import hash_password
from app.db.models.admin_account import AdminAccount
from tests.conftest import cleanup_temp_admin

PASSWORD = "Test@12345"
NEW_PASSWORD = "NewPass@12345"
MISSING_ID = 999999999


def _make_admin(session, role: str = "super_admin"):
    """建临时管理员并返回 (username, password)(conftest 的 make_temp_admin 固定 role=admin)。"""
    username = f"_test_admin_{uuid.uuid4().hex[:8]}"
    enc, salt = hash_password(PASSWORD)
    session.add(AdminAccount(username=username, passwordHash=enc, salt=salt,
                             realName="测试管理员", role=role, status=1))
    session.commit()
    return username, PASSWORD


def _login(client, username: str, password: str):
    return client.post("/api/admin/auth/login", json={"username": username, "password": password})


def _token(client, username: str, password: str) -> str:
    resp = _login(client, username, password)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_new_admin_endpoints_require_token(client):
    """6 个新增接口无 token 一律 401。"""
    cases = [
        ("GET", "/api/admin/auth/profile", None),
        ("POST", "/api/admin/auth/change-password", {"oldPassword": PASSWORD, "newPassword": NEW_PASSWORD}),
        ("POST", "/api/admin/account/create", {"username": "_test_x", "password": NEW_PASSWORD}),
        ("PUT", f"/api/admin/account/{MISSING_ID}", {"realName": "_test"}),
        ("DELETE", f"/api/admin/account/{MISSING_ID}", None),
        ("POST", f"/api/admin/account/{MISSING_ID}/reset-password", {"password": NEW_PASSWORD}),
    ]
    for method, path, payload in cases:
        resp = client.request(method, path, json=payload)
        assert resp.status_code == 401, (method, path, resp.status_code, resp.text)
        assert resp.json()["code"] == 401


def test_profile_returns_current_admin(client, session):
    username, password = _make_admin(session)
    try:
        token = _token(client, username, password)
        resp = client.get("/api/admin/auth/profile", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["username"] == username
        assert data["role"] == "super_admin" and data["realName"] == "测试管理员"
        assert isinstance(data["id"], str)
    finally:
        cleanup_temp_admin(session, username)


def test_change_password_flow(client, session):
    username, password = _make_admin(session)
    try:
        token = _token(client, username, password)

        wrong = client.post("/api/admin/auth/change-password", headers=_headers(token),
                            json={"oldPassword": "WrongPass@1", "newPassword": NEW_PASSWORD})
        assert wrong.status_code == 401, wrong.text
        assert wrong.json()["message"] == "旧密码错误"

        short = client.post("/api/admin/auth/change-password", headers=_headers(token),
                            json={"oldPassword": password, "newPassword": "short"})
        assert short.status_code == 400

        ok = client.post("/api/admin/auth/change-password", headers=_headers(token),
                         json={"oldPassword": password, "newPassword": NEW_PASSWORD})
        assert ok.status_code == 201, ok.text
        assert ok.json()["data"] == {"success": True}

        assert _login(client, username, NEW_PASSWORD).status_code == 200
        assert _login(client, username, password).status_code == 401
    finally:
        cleanup_temp_admin(session, username)


def test_account_crud_and_super_admin_guard(client, session):
    """账号 create/update/reset-password/delete 主路径 + 唯一冲突 + 角色门槛 + 软删除语义。"""
    root, root_pwd = _make_admin(session, role="super_admin")
    plain, plain_pwd = _make_admin(session, role="admin")
    target_username = f"_test_account_{uuid.uuid4().hex[:8]}"
    try:
        root_token = _token(client, root, root_pwd)
        plain_token = _token(client, plain, plain_pwd)

        # 读:普通 admin 也可访问(需登录,无角色门槛)
        assert client.get("/api/admin/account/list", headers=_headers(plain_token)).status_code == 200
        assert client.get(f"/api/admin/account/{MISSING_ID}", headers=_headers(plain_token)).status_code == 404

        # 写:普通 admin 一律 403(super_admin 专属)
        for method, path, payload in [
            ("POST", "/api/admin/account/create", {"username": f"_test_denied_{uuid.uuid4().hex[:6]}", "password": NEW_PASSWORD}),
            ("PUT", f"/api/admin/account/{MISSING_ID}", {"realName": "_test"}),
            ("DELETE", f"/api/admin/account/{MISSING_ID}", None),
            ("POST", f"/api/admin/account/{MISSING_ID}/reset-password", {"password": NEW_PASSWORD}),
        ]:
            resp = client.request(method, path, headers=_headers(plain_token), json=payload)
            assert resp.status_code == 403, (method, path, resp.status_code, resp.text)
            assert resp.json()["code"] == 403

        created = client.post("/api/admin/account/create", headers=_headers(root_token), json={
            "username": target_username, "password": PASSWORD, "realName": "被创建管理员",
            "phone": "<PHONE>", "email": "_test@example.com", "role": "viewer",
        })
        assert created.status_code == 201, created.text
        body = created.json()["data"]
        assert body["username"] == target_username and body["role"] == "viewer"
        assert body["realName"] == "被创建管理员"
        assert "password" not in body and "passwordHash" not in body
        account_id = body["id"]

        dup = client.post("/api/admin/account/create", headers=_headers(root_token),
                          json={"username": target_username, "password": PASSWORD})
        assert dup.status_code == 400 and "已存在" in dup.json()["message"]

        bad_role = client.post("/api/admin/account/create", headers=_headers(root_token),
                               json={"username": f"_test_bad_{uuid.uuid4().hex[:6]}", "password": PASSWORD, "role": "root"})
        assert bad_role.status_code == 400

        detail = client.get(f"/api/admin/account/{account_id}", headers=_headers(root_token))
        assert detail.status_code == 200
        assert detail.json()["data"]["role"] == "viewer" and detail.json()["data"]["email"] == "_test@example.com"

        updated = client.put(f"/api/admin/account/{account_id}", headers=_headers(root_token),
                             json={"realName": "被改管理员", "role": "admin", "status": 0})
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["realName"] == "被改管理员"
        assert updated.json()["data"]["role"] == "admin"
        assert updated.json()["data"]["status"] == 0
        assert updated.json()["data"]["username"] == target_username  # 未提供的键不被清空

        null_title = client.put(f"/api/admin/account/{account_id}", headers=_headers(root_token), json={"realName": None})
        assert null_title.status_code == 400 and "不能为 null" in null_title.json()["message"]

        # 停用(status=0)后不可登录
        assert _login(client, target_username, PASSWORD).status_code == 401

        reset = client.post(f"/api/admin/account/{account_id}/reset-password", headers=_headers(root_token),
                            json={"password": NEW_PASSWORD})
        assert reset.status_code == 201, reset.text
        assert reset.json()["data"] == {"success": True}

        # 重新启用后可用新密码登录
        client.put(f"/api/admin/account/{account_id}", headers=_headers(root_token), json={"status": 1})
        assert _login(client, target_username, NEW_PASSWORD).status_code == 200
        assert _login(client, target_username, PASSWORD).status_code == 401

        # 软删除:详情 404、不能登录、旧 token 立即失效
        before_delete_token = _token(client, target_username, NEW_PASSWORD)
        assert client.get("/api/admin/auth/profile", headers=_headers(before_delete_token)).status_code == 200
        removed = client.delete(f"/api/admin/account/{account_id}", headers=_headers(root_token))
        assert removed.status_code == 200 and removed.json()["data"] == {"success": True}
        assert client.get(f"/api/admin/account/{account_id}", headers=_headers(root_token)).status_code == 404
        assert _login(client, target_username, NEW_PASSWORD).status_code == 401
        assert client.get("/api/admin/auth/profile", headers=_headers(before_delete_token)).status_code == 401
    finally:
        import sqlalchemy as _sa

        for name in (target_username,):
            session.execute(_sa.text("DELETE FROM admin_account WHERE username = :u"), {"u": name})
        session.commit()
        cleanup_temp_admin(session, root)
        cleanup_temp_admin(session, plain)
