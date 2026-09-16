"""阶段3补充验证:锁定标志 + admin 进度端点字节对比。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.security import create_admin_token, create_merchant_token

NEST = "http://127.0.0.1:3000"
PY = "http://127.0.0.1:8000"
fails = []

# 1) 锁定标志(tester_r2_locked: phase2 阶段应 locked & 无任务;shopdata 不锁)
t = create_merchant_token("tester_r2_locked")
st = httpx.get(PY + "/api/task/stages", headers={"Authorization": f"Bearer {t}"}, timeout=10).json()["data"]
for s in st:
    if s["stageId"] in ("brand", "listing", "optimize", "activity"):
        print(f" {s['stageId']}: locked={s['locked']} tasks={len(s['firstLevelTasks'])} unlockHint={s.get('unlockHint')}")
    if s["stageId"] == "shopdata":
        print(f" shopdata: locked={s['locked']} tasks={len(s['firstLevelTasks'])} (应 False/有任务,不参与阶段二进度)")
# 断言
brand = next(s for s in st if s["stageId"] == "brand")
shop = next(s for s in st if s["stageId"] == "shopdata")
pass1 = brand["locked"] is True and len(brand["firstLevelTasks"]) == 0 and brand.get("unlockHint") == "完成阶段一全部任务后解锁"
pass1 = pass1 and shop["locked"] is False and len(shop["firstLevelTasks"]) > 0
print("锁定标志断言:", "PASS" if pass1 else "FAIL")
if not pass1:
    fails.append("locked-flags")

# 2) admin 进度端点字节对比
at = create_admin_token(1, "admin", "super_admin")
AH = {"Authorization": f"Bearer {at}"}
def cmp(label, path):
    n = httpx.get(NEST + path, headers=AH, timeout=10)
    p = httpx.get(PY + path, headers=AH, timeout=10)
    same = n.content == p.content
    print(f"[{'BYTES_IDENTICAL' if same else 'BYTES_DIFF'}] {label} | {len(n.content)}B/{len(p.content)}B")
    if not same:
        fails.append(label)

cmp("GET /api/admin/merchant/progress?merchantId=mock_merchant_001", "/api/admin/merchant/progress?merchantId=mock_merchant_001")
cmp("GET /api/admin/merchant/progress/mock_merchant_001", "/api/admin/merchant/progress/mock_merchant_001")

print()
print("FAIL:", fails) if fails else print("ALL_PASS")
sys.exit(1 if fails else 0)
