"""断言 Python(8000) 与 NestJS(3000) 各阶段2接口 JSON 是否相等(证据用)。"""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import create_merchant_token

NEST = "http://127.0.0.1:3000"
PY = "http://127.0.0.1:8000"
mt = create_merchant_token("mock_merchant_001")
H = {"Authorization": f"Bearer {mt}"}


def get(url, path, headers=None):
    r = httpx.get(url + path, headers=headers or H, timeout=8)
    return r.status_code, r.json()


def assert_eq(label, path, qs="", body=None):
    ns, nd = get(NEST, path + qs)
    ps, pd = get(PY, path + qs)
    same = (ns == ps) and (nd == pd)
    print(f"[{'IDENTICAL' if same else 'DIFF'}] {label}  (HTTP {ns}/{ps})")
    if not same:
        print("   NestJS:", json.dumps(nd, ensure_ascii=True)[:300])
        print("   Python:", json.dumps(pd, ensure_ascii=True)[:300])
    return same


results = []
results.append(assert_eq("GET /api/category/list", "/api/category/list"))
results.append(assert_eq("GET /api/category/list?parent_id=1", "/api/category/list", "?parent_id=1"))
results.append(assert_eq("GET /api/category/1", "/api/category/1"))
results.append(assert_eq("GET /api/fee/detail?category_id=25", "/api/fee/detail", "?category_id=25"))
results.append(assert_eq("GET /api/merchant/info", "/api/merchant/info"))
results.append(assert_eq("GET /api/trademark/search?keyword=BOSE", "/api/trademark/search", "?keyword=BOSE"))

# 404 一致性
ns, nd = get(NEST, "/api/category/999999")
ps, pd = get(PY, "/api/category/999999")
results.append(f"404 category 999999: NestJS {ns} {nd['message']} | Python {ps} {pd['message']} -> {'MATCH' if (ns==ps and nd['code']==pd['code']) else 'DIFF'}")

print()
print("IDENTICAL count:", sum(1 for r in results if r is True or 'MATCH' in str(r)), "/", len(results))
