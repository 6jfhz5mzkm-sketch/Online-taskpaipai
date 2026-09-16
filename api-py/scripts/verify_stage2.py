"""阶段2核心读接口 + 登录验证(自检)。

覆盖验收:
1. 各 GET 接口返回 {code,message,data} 且字段与 NestJS 对齐
2. 登录:admin 登录返回 token;商家登录(简化)返回商家 token
3. 只读接口无 token -> 401;商标对未解锁商家 -> 403
4. 与 NestJS 契约形状对照(field names)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.core.security import create_merchant_token
from app.main import app

client = TestClient(app)


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' :: ' + str(detail) if detail else ''}")
    return ok


results = []

# 商家 token(mock_merchant_001: shop_setup,已解锁)
merchant_token = create_merchant_token("mock_merchant_001")
# 未解锁商家 token(tester_r2_locked: onboarding)
locked_token = create_merchant_token("tester_r2_locked")
MH = {"Authorization": f"Bearer {merchant_token}"}
LH = {"Authorization": f"Bearer {locked_token}"}

# ---- 登录 ----
r = client.post("/api/admin/auth/login", json={"username": "admin", "password": "Admin@123456"})
results.append(("admin 登录(admin/Admin@123456) 200 + token", r.status_code == 200 and "token" in r.json().get("data", {}), r.json() if r.status_code != 200 else "role=" + r.json()["data"]["admin"]["role"]))
results.append(("admin 登录返回 admin 字段对齐 NestJS", "admin" in r.json().get("data", {}) and set(r.json()["data"]["admin"].keys()) == {"id","username","realName","role"}, r.json().get("data", {})))
r2 = client.post("/api/admin/auth/login", json={"username": "admin", "password": "wrongpass"})
results.append(("admin 登录错误密码 -> 401", r2.status_code == 401, r2.json()))
r3 = client.post("/api/auth/feishu/callback", json={"code": "test_code"})
d3 = r3.json().get("data", {})
results.append(("商家登录(feishu 简化) 201 + token", r3.status_code == 201 and "token" in d3 and d3.get("merchant", {}).get("merchant_id") == "mock_merchant_001", d3))
r3b = client.post("/api/auth/feishu/callback", json={"code": ""})
results.append(("商家登录 code 为空 -> 400", r3b.status_code == 400, r3b.json()))

# 商家 token 登录后直接可用
mi = client.get("/api/merchant/info", headers=MH)
results.append(("商家信息字段对齐 NestJS(merchant_id/nickname/avatar/merchant_name/current_stage/status)", mi.status_code == 200 and set(mi.json()["data"].keys()) == {"merchant_id","nickname","avatar","merchant_name","current_stage","status"}, mi.json()))

# ---- 读接口 ----
cat = client.get("/api/category/list", headers=MH)
cdata = cat.json().get("data", [])
results.append(("类目列表(一级) 200 且字段对齐", cat.status_code == 200 and cdata and set(cdata[0].keys()) == {"id","name","parent_id","sort_order"}, {"status": cat.status_code, "n": len(cdata), "first": cdata[0] if cdata else None}))
cat2 = client.get("/api/category/list?parent_id=1", headers=MH)
results.append(("类目列表(二级) 200", cat2.status_code == 200 and len(cat2.json().get("data", [])) > 0, {"n": len(cat2.json().get("data", []))}))
catd = client.get("/api/category/1", headers=MH)
results.append(("类目详情 200", catd.status_code == 200, catd.json()))
catnf = client.get("/api/category/999999", headers=MH)
results.append(("类目详情不存在 -> 404", catnf.status_code == 404, catnf.json()))
fee = client.get("/api/fee/detail?category_id=25", headers=MH)
fdata = fee.json().get("data", {})
results.append(("资费详情 200 且字段对齐", fee.status_code == 200 and set(fdata.keys()) == {"category_id","brand_name","operation_rate","transaction_rate","deposit_gmv_lt_5w","deposit_gmv_5w_10w","deposit_gmv_10w_30w","deposit_gmv_gte_30w","is_brand_override"}, fdata))
fees = client.get("/api/fee/detail?category_id=999999", headers=MH)
results.append(("资费不存在 -> 404", fees.status_code == 404, fees.json()))
tr = client.get("/api/trademark/search?keyword=BOSE", headers=MH)
tdata = tr.json().get("data", [])
results.append(("商标搜索(已解锁商家) 200 且字段对齐", tr.status_code == 200 and tdata and set(tdata[0].keys()) == {"brand_name","registration_number"}, {"status": tr.status_code, "n": len(tdata), "first": tdata[0] if tdata else None}))
trl = client.get("/api/trademark/search?keyword=BOSE", headers=LH)
results.append(("商标搜索(未解锁商家) -> 403", trl.status_code == 403, trl.json()))

# ---- 无 token -> 401 ----
for ep in ["/api/category/list", "/api/fee/detail?category_id=25", "/api/merchant/info", "/api/trademark/search?keyword=BOSE"]:
    rr = client.get(ep)
    results.append((f"无 token {ep} -> 401", rr.status_code == 401, rr.json()))

for name, ok, *rest in results:
    check(name, ok, rest[0] if rest else "")
failed = [n for n, ok, *_ in results if not ok]
print()
print("== 总结 ==")
print(f"总项: {len(results)}, 通过: {len(results) - len(failed)}, 失败: {len(failed)}")
if failed:
    print("失败项:")
    for x in failed:
        print(" -", x)
    sys.exit(1)
print("ALL PASS")
