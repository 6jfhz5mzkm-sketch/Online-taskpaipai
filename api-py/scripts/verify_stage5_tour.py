"""阶段5部分对比:tour + event/track(字节级)。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from app.core.security import create_merchant_token
NEST = "http://127.0.0.1:3000"; PY = "http://127.0.0.1:8000"
MT = create_merchant_token("mock_merchant_001"); MH = {"Authorization": f"Bearer {MT}"}
fails = []
def cmp(label, method, path, headers, json=None):
    n = httpx.request(method, NEST + path, headers=headers, json=json, timeout=12)
    p = httpx.request(method, PY + path, headers=headers, json=json, timeout=12)
    same = n.status_code == p.status_code and n.content == p.content
    print(f"[{'IDENTICAL' if same else 'DIFF'}] {label} | {n.status_code}/{p.status_code} {len(n.content)}B/{len(p.content)}B")
    if not same:
        fails.append(label)
        a,b=n.content,p.content
        for i in range(min(len(a),len(b))):
            if a[i]!=b[i]:
                print("   diff@",i,"N=",a[i:i+40],"P=",b[i:i+40]); break
cmp("GET /api/tour/seen(mock)", "GET", "/api/tour/seen", MH)
cmp("POST /api/tour/seen", "POST", "/api/tour/seen", MH)
cmp("POST /api/tour/seen/reset", "POST", "/api/tour/seen/reset", MH)
# event/track(需要时间范围内有数据; track 返回 received)
cmp("POST /api/event/track(page_view)", "POST", "/api/event/track", {}, {"event_type": "page_view", "page_name": "__stage5__"})
print()
print("FAIL:", fails) if fails else print("ALL_PASS")
sys.exit(1 if fails else 0)
