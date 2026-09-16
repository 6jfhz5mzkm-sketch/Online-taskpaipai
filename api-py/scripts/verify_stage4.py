"""阶段4字节对比:NestJS(3000)/Python(8000) 反馈/商家管理/统计/账号,含角色守卫与写接口。临时数据用后清理。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import text

from app.core.security import create_admin_token, create_merchant_token
from app.db.engine import SessionLocal

NEST = "http://127.0.0.1:3000"
PY = "http://127.0.0.1:8000"

AT = create_admin_token(1, "admin", "super_admin")
MT = create_merchant_token("mock_merchant_001")
AH = {"Authorization": f"Bearer {AT}"}
MH = {"Authorization": f"Bearer {MT}"}

db = SessionLocal()
fails = []


def cmp(label, method, path, headers=None, json=None):
    def do(base):
        return httpx.request(method, base + path, headers=headers or {}, json=json, timeout=12)
    n = do(NEST)
    p = do(PY)
    same = (n.status_code == p.status_code) and (n.content == p.content)
    print(f"[{'IDENTICAL' if same else 'DIFF'}] {label} | {n.status_code}/{p.status_code} {len(n.content)}B/{len(p.content)}B")
    if not same:
        fails.append(label)
        a, b = n.content, p.content
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                print(f"   diff@ {i}: N={a[i]:02x} P={b[i]:02x} | N={a[max(0,i-30):i+30]!r} P={b[max(0,i-30):i+30]!r}")
                break
    return n, p


try:
    # --- 种反馈数据(供列表对比) ---
    db.execute(text("INSERT INTO feedback (merchant_id, content, category, status) VALUES ('mock_merchant_001', '__stage4_seed_a__', '功能建议', 'pending')"))
    db.execute(text("INSERT INTO feedback (merchant_id, content, category, status) VALUES (NULL, '__stage4_seed_b__', '使用问题', 'processing')"))
    db.commit()

    cmp("GET /api/admin/feedback", "GET", "/api/admin/feedback", AH)
    cmp("GET /api/admin/feedback?category=功能建议", "GET", "/api/admin/feedback?category=" + "%E5%8A%9F%E8%83%BD%E5%BB%BA%E8%AE%AE", AH)

    # --- 管理员商家/统计/账号 读接口 ---
    cmp("GET /api/admin/merchant", "GET", "/api/admin/merchant", AH)
    cmp("GET /api/admin/merchant?keyword=mock", "GET", "/api/admin/merchant?keyword=mock", AH)
    cmp("GET /api/admin/merchant/progress?merchantId=mock_merchant_001", "GET", "/api/admin/merchant/progress?merchantId=mock_merchant_001", AH)
    cmp("GET /api/admin/account/list", "GET", "/api/admin/account/list", AH)
    cmp("GET /api/event/stats?start_date=2026-06-10&end_date=2026-09-07", "GET", "/api/event/stats?start_date=2026-06-10&end_date=2026-09-07", AH)
    cmp("GET /api/event/stats?start_date=2026-06-10&end_date=2026-09-07&group_by=week", "GET", "/api/event/stats?start_date=2026-06-10&end_date=2026-09-07&group_by=week", AH)

    # --- 商家写接口 ---
    # 反馈 create(静默写)
    cmp("POST /api/feedback(create)", "POST", "/api/feedback", MH, {"content": "__stage4_create__", "category": "其他"})
    # 商家登记(临时商家)
    db.execute(text("INSERT INTO merchant (merchant_id, nickname, current_stage, status) VALUES ('__stage4_m__', '阶段4临时', 'onboarding', 1)"))
    db.commit()
    MT2 = create_merchant_token("__stage4_m__")
    cmp("PUT /api/merchant/registration", "PUT", "/api/merchant/registration", {"Authorization": f"Bearer {MT2}"}, {"jd_merchant_id": "JDM4", "shop_name": "店铺4"})
    # 一键解锁(super_admin)(临时商家)
    cmp("POST /api/admin/merchant/__stage4_m__/unlock-phase1", "POST", "/api/admin/merchant/__stage4_m__/unlock-phase1", AH)

    # --- 角色守卫 viewer 403 ---
    vview = db.execute(text("SELECT id FROM admin_account WHERE username='_stage4_viewer_'")).mappings().first()
    if vview is None:
        vh, vs = ("x", "x")
        from app.core.security import hash_password
        vh, vs = hash_password("Viewer@123")
        db.execute(text("INSERT INTO admin_account (username, passwordHash, salt, realName, role, status) VALUES ('_stage4_viewer_', :h, :s, '阶段4viewer', 'viewer', 1)"), {"h": vh, "s": vs})
        db.commit()
        vview = db.execute(text("SELECT id FROM admin_account WHERE username='_stage4_viewer_'")).mappings().first()
    VT = create_admin_token(vview["id"], "_stage4_viewer_", "viewer")
    r = httpx.post(NEST + "/api/admin/account/generate", headers={"Authorization": f"Bearer {VT}"}, json={"username": "zzz_viewer_try"}, timeout=12)
    print("[role] viewer->generate NestJS:", r.status_code)
    r2 = httpx.post(PY + "/api/admin/account/generate", headers={"Authorization": f"Bearer {VT}"}, json={"username": "zzz_viewer_try"}, timeout=12)
    print("[role] viewer->generate Python:", r2.status_code)
    if not (r.status_code == 403 and r2.status_code == 403):
        fails.append("role-viewer-403")
    # super_admin generate(结构校验;密码随机故不比字节,只验200与字段)
    # 不同用户名(避免"用户名已存在"): 两者都应 200 且结构一致(密码随机不比字节)
    gn = httpx.post(NEST + "/api/admin/account/generate", headers=AH, json={"username": "_stage4_gen_n_"}, timeout=12)
    gp = httpx.post(PY + "/api/admin/account/generate", headers=AH, json={"username": "_stage4_gen_p_"}, timeout=12)
    dn = gn.json()["data"]
    dp = gp.json()["data"]
    keys = {"id","username","realName","role","password","note"}
    ok_gen = gn.status_code == 201 and gp.status_code == 201 and set(dn.keys()) == keys and set(dp.keys()) == keys and len(dp["password"]) >= 12
    print("[role] super_admin->generate: NEST", gn.status_code, "PY", gp.status_code, "keys_ok", ok_gen, "py_pwd_len", len(dp["password"]) if dp.get("password") else None)
    # 重复用户名 -> 400 一致
    rd = httpx.post(PY + "/api/admin/account/generate", headers=AH, json={"username": "_stage4_gen_p_"}, timeout=12)
    print("[dup] same username -> Python Status", rd.status_code, "(应为400)")
    if not (ok_gen and rd.status_code == 400):
        fails.append("role-super-generate")

finally:
    # 清理
    db.execute(text("DELETE FROM feedback WHERE content LIKE '__stage4%'"))
    db.execute(text("DELETE FROM merchant WHERE merchant_id='__stage4_m__'"))
    db.execute(text("DELETE FROM merchant_stage_progress WHERE merchant_id='__stage4_m__'"))
    db.execute(text("DELETE FROM admin_account WHERE username='_stage4_viewer_' OR username='_stage4_gen_n_' OR username='_stage4_gen_p_' OR username='zzz_viewer_try'"))
    db.commit()
    left = db.execute(text("SELECT (SELECT COUNT(*) FROM feedback WHERE content LIKE '__stage4%') f, (SELECT COUNT(*) FROM merchant WHERE merchant_id='__stage4_m__') m, (SELECT COUNT(*) FROM admin_account WHERE username LIKE '_stage4%' OR username IN ('zzz_viewer_try')) a")).mappings().first()
    print("cleanup残留:", dict(left))
    db.close()

print()
print("FAIL:", fails) if fails else print("ALL_PASS")
sys.exit(1 if fails else 0)
