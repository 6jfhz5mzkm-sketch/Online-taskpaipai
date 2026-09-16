"""用 httpx 干净地对比 NestJS(3000)与 Python(8000)的登录接口响应(规避 shell 转义)。"""
import json

import httpx

NEST = "http://127.0.0.1:3000"
PY = "http://127.0.0.1:8000"


def post(url, path, body):
    try:
        r = httpx.post(url + path, json=body, timeout=8)
        return r.status_code, r.json()
    except Exception as e:
        return None, {"error": str(e)}


def show(label, path, body):
    ns, nd = post(NEST, path, body)
    ps, pd = post(PY, path, body)
    print(f"### {label}")
    print("NestJS:", ns, json.dumps(nd, ensure_ascii=True))
    print("Python:", ps, json.dumps(pd, ensure_ascii=True))
    print()


show("admin 登录", "/api/admin/auth/login", {"username": "admin", "password": "Admin@123456"})
show("admin 登录(错误密码)", "/api/admin/auth/login", {"username": "admin", "password": "wrongpass"})
show("商家登录", "/api/auth/feishu/callback", {"code": "test_code"})
show("商家登录(code空)", "/api/auth/feishu/callback", {"code": ""})
