"""阶段3解锁派生逻辑验证(方案A永久解锁):完成阶段一全部任务->解锁;回退一任务->不回锁。用临时商家,结束后清理。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import bindparam, text

from app.core.security import create_merchant_token
from app.db.engine import SessionLocal
from app.main import app
from app.services.task_progress import PHASE1_STAGE_IDS

MID = "_stage3_derive_test_"
client = TestClient(app)

db = SessionLocal()


def phase1_task_ids():
    """阶段一启用任务 ID(stageId 属于 PHASE1_STAGE_IDS 且 status=1)。

    修正:原首行是恒为 None 的死代码(if False else None),且把 IN 参数误绑成 bindparams(text(...));
    改为 SQLAlchemy 2.0 的 expanding 绑定写法,一条查询取回全部(= 原逐 stage 循环的等价结果)。
    """
    return list(db.execute(
        text("SELECT taskId FROM second_level_task WHERE stageId IN :s AND status = 1").bindparams(
            bindparam("s", expanding=True, value=PHASE1_STAGE_IDS)
        )
    ).scalars().all())


try:
    # 清理可能残留
    db.execute(text("DELETE FROM merchant WHERE merchant_id = :m"), {"m": MID})
    db.execute(text("DELETE FROM merchant_task_progress WHERE merchantId = :m"), {"m": MID})
    db.execute(text("DELETE FROM merchant_stage_progress WHERE merchant_id = :m"), {"m": MID})
    db.commit()

    # 插入临时商家(current_stage=onboarding)
    db.execute(text("INSERT INTO merchant (merchant_id, nickname, current_stage, status) VALUES (:m, '阶段3临时', 'onboarding', 1)"), {"m": MID})
    db.commit()

    token = create_merchant_token(MID)
    H = {"Authorization": f"Bearer {token}"}
    task_ids = phase1_task_ids()
    print("阶段一启用任务数:", len(task_ids))

    # 逐个完成
    last_unlocked = False
    for tid in task_ids:
        r = client.post("/api/task/progress", headers=H, json={"taskId": tid, "status": "completed"})
        body = r.json()["data"]
        last_unlocked = body["stage2_unlocked"]
    print("完成全部阶段一后 stage2_unlocked =", last_unlocked)

    # 进度
    p = client.get("/api/task/progress", headers=H).json()["data"]
    print("after_all stage2_unlocked =", p["stage2_unlocked"], "remaining =", len(p["phase1_remaining_task_ids"]))

    # 回退一个任务 -> 永久解锁不回锁
    rv = client.post("/api/task/progress", headers=H, json={"taskId": task_ids[0], "status": "pending"})
    p2 = client.get("/api/task/progress", headers=H).json()["data"]
    print("after_revert stage2_unlocked =", p2["stage2_unlocked"], "(应为 True,永久解锁)")

    ok = (last_unlocked is True) and (p["stage2_unlocked"] is True) and (p2["stage2_unlocked"] is True) and len(p["phase1_remaining_task_ids"]) == 0
    print("RESULT:", "PASS" if ok else "FAIL")
finally:
    # 清理临时数据
    db.execute(text("DELETE FROM merchant WHERE merchant_id = :m"), {"m": MID})
    db.execute(text("DELETE FROM merchant_task_progress WHERE merchantId = :m"), {"m": MID})
    db.execute(text("DELETE FROM merchant_stage_progress WHERE merchant_id = :m"), {"m": MID})
    db.commit()
    # 复核清理
    left = db.execute(text("SELECT COUNT(*) FROM merchant WHERE merchant_id = :m"), {"m": MID}).scalar()
    print("清理残留:", left)
    db.close()
