"""字符集字节级验证:对比 Python(8000)与 NestJS(3000)同字段的 UTF-8 原始字节(hex)。

读接口对比原始响应 body 字节;中文字段(name/nickname/brand_name/realName)单独 hex 对比。
二手 = e4ba8ce6898b。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.security import create_merchant_token

NEST = "http://127.0.0.1:3000"
PY = "http://127.0.0.1:8000"
T = create_merchant_token("mock_merchant_001")
H = {"Authorization": f"Bearer {T}"}

fails = []


def _get(data, keypath):
    """按 keypath 逐层取值(list 下标与 dict key 在取值语法上同为 cur[k])。"""
    cur = data
    for k in keypath:
        cur = cur[k]
    return cur


def get(url, path, qs=""):
    return httpx.get(url + path + qs, headers=H, timeout=8)


def cmp(name, label, path, qs="", keypath=None):
    n, p = get(name, path, qs), get(PY, path, qs)
    body_same = n.content == p.content
    msg = f"[{'BODY_SAME' if body_same else 'BODY_DIFF'}] {label} (NestJS {len(n.content)}B / Python {len(p.content)}B)"
    if keypath:
        nb = _get(n.json()["data"], keypath).encode("utf-8")
        pb = _get(p.json()["data"], keypath).encode("utf-8")
        field_same = nb == pb
        msg += f" || hex NEST={nb.hex()} PY={pb.hex()} {'FIELD_OK' if field_same else 'FIELD_DIFF'}"
        if not field_same:
            fails.append(label + "|field")
    if not body_same:
        fails.append(label + "|body")
    print(msg)


cmp(NEST, "GET /api/category/list", "/api/category/list", "", [0, "name"])
cmp(NEST, "GET /api/category/list?parent_id=1", "/api/category/list", "?parent_id=1", [0, "name"])
cmp(NEST, "GET /api/category/1", "/api/category/1", "", ["name"])
cmp(NEST, "GET /api/fee/detail?category_id=25", "/api/fee/detail", "?category_id=25", None)
cmp(NEST, "GET /api/merchant/info", "/api/merchant/info", "", ["nickname"])
cmp(NEST, "GET /api/trademark/search?keyword=BOSE", "/api/trademark/search", "?keyword=BOSE", [0, "brand_name"])

# 登录字段字节
def login(label, path, body, keypath):
    n = httpx.post(NEST + path, json=body, timeout=8).json()
    p = httpx.post(PY + path, json=body, timeout=8).json()
    nb = _get(n["data"], keypath).encode("utf-8")
    pb = _get(p["data"], keypath).encode("utf-8")
    ok = nb == pb
    print(f"[{'BYTES_OK' if ok else 'BYTES_DIFF'}] {label} hex NEST={nb.hex()} PY={pb.hex()}")
    if not ok:
        fails.append(label)


login("admin 登录 realName", "/api/admin/auth/login", {"username": "admin", "password": "Admin@123456"}, ["admin", "realName"])
login("商家登录 nickname", "/api/auth/feishu/callback", {"code": "x"}, ["merchant", "nickname"])

print()
if fails:
    print("FAIL:", fails)
    sys.exit(1)
print("ALL_BYTES_IDENTICAL")
