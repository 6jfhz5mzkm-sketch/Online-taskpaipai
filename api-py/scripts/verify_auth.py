"""阶段1鉴权验证(自检)。

覆盖验收:
1. 商家 token:无/伪 token 401,合法 token 200
2. 管理员 token + 角色守卫:无 token 401,viewer 调 super_admin 接口 403,super_admin 200
3. 两个 secret 分开(商家 token 不能用于 admin,反之亦然)
4. 密码哈希对齐 NestJS(pbkdf2-sha512 10000,用种子 admin/admin123 交叉核对)

针对 get_current_admin 的"库中校验",会临时插入一个 viewer 管理员用于角色守卫测试,结束后删除。

用法: cd api-py && uv run python scripts/verify_auth.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import (
    PBKDF2_ITERATIONS,
    create_admin_token,
    create_merchant_token,
    hash_password,
    verify_password,
)
from app.db.engine import SessionLocal
from app.main import app

# 种子 admin 的已知值(来自 AddAdminSeed 迁移,密码 admin123)
SEED_HASH = "cb1e16be156ead9bb841237b249ede22cd86f4be5141ac3547afc3b10698aa0fdb0413ab644361a6d7793e35c7d4de7873abe847ee542e7da558f8202ea574a6"
SEED_SALT = "967ffc1ad5ac7b0f6c880c435b041b01"
SEED_PWD = "admin123"

VIEWER_USERNAME = "_stage1_viewer_"


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' :: ' + detail if detail else ''}")


def main() -> None:
    results = []

    # ---- 4) pbkdf2 交叉核对(对齐 NestJS) ----
    seed_ok = verify_password(SEED_PWD, SEED_HASH, SEED_SALT)
    results.append(("密码哈希对齐 NestJS(pbkdf2-sha512-10000-64,admin123)", seed_ok))
    # 反向:错误密码应失败
    wrong_ok = not verify_password("wrong_password", SEED_HASH, SEED_SALT)
    results.append(("密码哈希错误密码拒绝", wrong_ok))
    # 自生成往返
    h, s = hash_password("test_pass_123")
    results.append(("密码哈希自生成往返一致", verify_password("test_pass_123", h, s)))

    # ---- 准备管理员 ----
    client = TestClient(app)
    admin_id = None
    viewer_id = None
    db = SessionLocal()
    try:
        # 取种子 super_admin id
        row = db.execute(text("SELECT id, role FROM admin_account WHERE username = 'admin'")).mappings().first()
        if row is None:
            results.append(("种子管理员存在", False, "库中无 admin 账号"))
        else:
            admin_id = row["id"]
            results.append(("种子管理员存在", True, f"id={admin_id} role={row['role']}"))

            # 临时 viewer:存在则复用,否则插入
            v = db.execute(text("SELECT id, role FROM admin_account WHERE username = :u"), {"u": VIEWER_USERNAME}).mappings().first()
            if v is None:
                vh, vs = hash_password("viewer_pass")
                db.execute(
                    text("INSERT INTO admin_account (username, passwordHash, salt, realName, role, status) VALUES (:u, :h, :s, :n, 'viewer', 1)"),
                    {"u": VIEWER_USERNAME, "h": vh, "s": vs, "n": "阶段1测试viewer"},
                )
                db.commit()
                v = db.execute(text("SELECT id, role FROM admin_account WHERE username = :u"), {"u": VIEWER_USERNAME}).mappings().first()
            viewer_id = v["id"]

        # 签发 token
        merchant_token = create_merchant_token("mock_merchant_001")
        super_token = create_admin_token(admin_id, "admin", "super_admin")
        viewer_token = create_admin_token(viewer_id, VIEWER_USERNAME, "viewer")
        # 交叉 secret 测试 token:用商家 secret 伪造一个"含 sub 的 token"去访问 admin 接口
        from app.core.config import get_settings
        from app.core.security import create_token
        s = get_settings()
        fake_admin_with_merchant_secret = create_token({"sub": admin_id, "username": "admin", "role": "super_admin"}, s.JWT_SECRET, 3600)

        # ---- 1) 商家鉴权 ----
        r = client.get("/api/test/merchant/me")
        results.append(("商家:无 token -> 401", r.status_code == 401, f"status={r.status_code} body={r.json()}"))
        r = client.get("/api/test/merchant/me", headers={"Authorization": "Bearer not.a.valid.token"})
        results.append(("商家:伪 token -> 401", r.status_code == 401, f"status={r.status_code}"))
        r = client.get("/api/test/merchant/me", headers={"Authorization": f"Bearer {merchant_token}"})
        results.append(("商家:合法 token -> 200 且含 merchant_id", r.status_code == 200 and r.json()["data"]["merchant_id"] == "mock_merchant_001", f"status={r.status_code} body={r.json()}"))

        # ---- 2) 管理员鉴权 + 角色守卫 ----
        r = client.get("/api/test/admin/me")
        results.append(("admin:无 token -> 401", r.status_code == 401, f"status={r.status_code}"))
        r = client.get("/api/test/admin/me", headers={"Authorization": f"Bearer {super_token}"})
        results.append(("admin:super_admin token -> 200", r.status_code == 200 and r.json()["data"]["role"] == "super_admin", f"status={r.status_code} body={r.json()}"))
        # 角色守卫:viewer 调 super_admin 接口
        r = client.get("/api/test/admin/account-manage", headers={"Authorization": f"Bearer {viewer_token}"})
        results.append(("角色守卫:viewer 调 super_admin 接口 -> 403", r.status_code == 403, f"status={r.status_code} body={r.json()}"))
        r = client.get("/api/test/admin/account-manage", headers={"Authorization": f"Bearer {super_token}"})
        results.append(("角色守卫:super_admin -> 200", r.status_code == 200, f"status={r.status_code} body={r.json()}"))

        # ---- 3) 两个 secret 分开 ----
        r = client.get("/api/test/admin/me", headers={"Authorization": f"Bearer {fake_admin_with_merchant_secret}"})
        results.append(("secret 分离:商家 secret 伪签的 admin token -> 401", r.status_code == 401, f"status={r.status_code}"))
        # admin token 拿去商家接口
        r = client.get("/api/test/merchant/me", headers={"Authorization": f"Bearer {super_token}"})
        results.append(("secret 分离:admin token 访问商家接口 -> 401", r.status_code == 401, f"status={r.status_code}"))

    finally:
        # 清理临时 viewer
        try:
            if viewer_id is None:
                v = db.execute(text("SELECT id FROM admin_account WHERE username = :u"), {"u": VIEWER_USERNAME}).mappings().first()
                viewer_id = v["id"] if v else None
            if viewer_id is not None:
                db.execute(text("DELETE FROM admin_account WHERE id = :id"), {"id": viewer_id})
                db.commit()
        except Exception:
            db.rollback()
        db.close()

    for name, ok, *rest in results:
        check(name, ok, rest[0] if rest else "")
    failed = [name for name, ok, *_ in results if not ok]
    print()
    print("== 总结 ==")
    print(f"总项: {len(results)}, 通过: {len(results) - len(failed)}, 失败: {len(failed)}")
    if failed:
        print("失败项:", *failed, sep="\n - ")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
