"""阶段3字节级对比:task/stages + task/progress(已解锁/未解锁商家),对比 NestJS 原始响应体字节。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.security import create_merchant_token

NEST = "http://127.0.0.1:3000"
PY = "http://127.0.0.1:8000"

MERCHANTS = ["mock_merchant_001", "tester_r2_locked"]  # 已解锁 / 未解锁
fails = []


def cmp(label, path, merchant):
    t = create_merchant_token(merchant)
    H = {"Authorization": f"Bearer {t}"}
    n = httpx.get(NEST + path, headers=H, timeout=10)
    p = httpx.get(PY + path, headers=H, timeout=10)
    same = n.content == p.content
    print(f"[{'BYTES_IDENTICAL' if same else 'BYTES_DIFF'}] {label} | NestJS {len(n.content)}B / Python {len(p.content)}B")
    if not same:
        fails.append(label)
        # 找出第一个差异
        a, b = n.content, p.content
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                print(f"   first diff @ {i}: NestJS={a[i]:02x} Python={b[i]:02x}")
                print(f"   ...NestJS ctx: {a[max(0,i-40):i+40]!r}")
                print(f"   ...Python ctx: {b[max(0,i-40):i+40]!r}")
                break
        else:
            print(f"   len diff: NestJS={len(a)} Python={len(b)}")


for m in MERCHANTS:
    cmp(f"GET /api/task/stages ({m})", "/api/task/stages", m)
    cmp(f"GET /api/task/progress ({m})", "/api/task/progress", m)

print()
if fails:
    print("FAIL:", fails)
    sys.exit(1)
print("ALL_BYTES_IDENTICAL")
