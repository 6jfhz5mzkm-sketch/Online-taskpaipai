"""任务进度/解锁服务(对齐 backend task-progress.service)。

业务规则(真源:project/docs/阶段隔离规则与阶段二任务清单.md):
- 阶段一完成 = 阶段一(PHASE1_STAGE_IDS 且 status=1)所有启用二级任务 completed(含 default_completed=1);
- 阶段二解锁 = 阶段一完成(任务派生) 或 merchant.current_stage='shop_setup'(运营一键解锁,永久不回滚);
- 数据专区独立解锁 = 完成 T2.2(listing)全部启用任务;
- 停用任务(status=0)自动剔除;shopdata 已剥离,不计入阶段二进度。
"""
from datetime import datetime
from typing import Any, Dict, List, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.db.models.merchant_task_progress import MerchantTaskProgress
from app.db.models.second_level_task import SecondLevelTask
from app.services.merchant import get_current_stage
from app.services.merchant_binding import resolve_group_merchant_ids

PHASE1_STAGE_IDS = ["onboarding", "application", "review", "opening"]
PHASE2_STAGE_IDS = ["brand", "listing", "optimize", "activity"]
DATA_CENTER_STAGE_ID = "shopdata"
DATA_CENTER_UNLOCK_STAGE_ID = "listing"
STAGE2_UNLOCK_STAGE_ID = "shop_setup"


def _find_enabled_by_stage_ids(db: Session, stage_ids: List[str]) -> List[SecondLevelTask]:
    if not stage_ids:
        return []
    rows = db.execute(
        select(SecondLevelTask).where(
            SecondLevelTask.stageId.in_(stage_ids), SecondLevelTask.status == 1
        ).order_by(SecondLevelTask.sortOrder.asc())
    ).scalars().all()
    return list(rows)


def _completed_rows(db: Session, merchant_ids: Sequence[str]) -> List[Tuple[str, Any]]:
    """组内完成行的 `(taskId, completedAt)` 原始投影 —— **并集取数的唯一入口**。"""
    return db.execute(
        select(MerchantTaskProgress.taskId, MerchantTaskProgress.completedAt).where(
            MerchantTaskProgress.merchantId.in_(list(merchant_ids)),
            MerchantTaskProgress.status == "completed",
        )
    ).all()


def get_group_progress(db: Session, merchant_id: str) -> Dict[str, Any]:
    """账号绑定后的**组内进度并集**(店铺级事实;方案 §3.1,无绑定 = 只有自己 → 与改造前等价)。

    - `merchant_ids`:参与并集的账号(组解析见 `services/merchant_binding.py`);
    - `completed_task_ids`:**按 taskId 去重**的完成集合(排序稳定,可复现对账);
    - `completed_at`:同一 taskId 取组内**最早**完成时间 —— 完成时间是店铺级事实且**单调**,
      后续成员补做/重做不会把时间往后推。
    """
    merchant_ids = resolve_group_merchant_ids(db, merchant_id)
    earliest: Dict[str, datetime] = {}
    for task_id, completed_at in _completed_rows(db, merchant_ids):
        if task_id not in earliest:
            earliest[task_id] = completed_at
        elif completed_at is not None and (earliest[task_id] is None or completed_at < earliest[task_id]):
            earliest[task_id] = completed_at
    return {
        "merchant_ids": merchant_ids,
        "completed_task_ids": sorted(earliest),
        "completed_at": earliest,
    }


def _get_completed_task_ids(db: Session, merchant_ids: Sequence[str]) -> set:
    """组内完成的 taskId 集合(**仍按 taskId 去重**;#PB-36 方案 §3.3 改造点 1)。"""
    return {row[0] for row in _completed_rows(db, merchant_ids)}


def _any_member_in_stage(db: Session, merchant_ids: Sequence[str], stage_id: str) -> bool:
    """组内是否有任一未软删账号处于该阶段(**组内 OR**,方案 §3.1)。"""
    from app.db.models.merchant import Merchant as MerchantModel

    row = db.execute(
        select(MerchantModel.merchant_id).where(
            MerchantModel.merchant_id.in_(list(merchant_ids)),
            MerchantModel.deleted_at.is_(None),
            MerchantModel.current_stage == stage_id,
        ).limit(1)
    ).first()
    return row is not None


def get_task_derived_state(db: Session, merchant_id: str) -> Tuple[bool, List[str]]:
    """(taskDerivedUnlocked, remainingTaskIds)。**按组内并集判定**(方案 §3.3 改造点 2)。"""
    tasks = _find_enabled_by_stage_ids(db, PHASE1_STAGE_IDS)
    if len(tasks) == 0:
        return False, []
    completed_ids = _get_completed_task_ids(db, resolve_group_merchant_ids(db, merchant_id))
    remaining = [
        t.taskId for t in tasks
        if t.defaultCompleted != 1 and t.taskId not in completed_ids
    ]
    return len(remaining) == 0, remaining


def get_phase2_unlock_state(db: Session, merchant_id: str) -> dict:
    """阶段二解锁态:**组内 OR**(任一成员 current_stage=shop_setup 或任务派生即整组解锁)。

    与既有「解锁永久不回滚」口径一致(#PB-36 方案 §3.1):否则会出现「A 已解锁阶段二、
    同组 B 仍看到锁定壳」的荒谬状态。
    """
    task_derived, remaining = get_task_derived_state(db, merchant_id)
    merchant_ids = resolve_group_merchant_ids(db, merchant_id)
    current = _any_member_in_stage(db, merchant_ids, STAGE2_UNLOCK_STAGE_ID)
    unlocked = current or task_derived
    return {"unlocked": unlocked, "remainingTaskIds": remaining}


def get_data_center_unlock_state(db: Session, merchant_id: str) -> dict:
    """数据专区解锁(**双层语义**,#PB-36 方案 §3.1 第 4 行):

    ① `merchant.data_center_unlocked` 持久化标记 = **账号级、不共享**(用户口径);
    ② listing 任务完成派生的部分 = **进度,按组内并集共享**。
    最终 `unlocked = 本账号 persisted OR 组内 listing 并集派生`;取消商品发布不回退,幂等。
    """
    from app.db.models.merchant import Merchant as MerchantModel

    m = db.execute(
        select(MerchantModel).where(
            MerchantModel.merchant_id == merchant_id, MerchantModel.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    persisted = (m is not None and m.data_center_unlocked == 1)

    tasks = _find_enabled_by_stage_ids(db, [DATA_CENTER_UNLOCK_STAGE_ID])
    if len(tasks) == 0:
        return {"unlocked": persisted, "remainingTaskIds": []}
    completed_ids = _get_completed_task_ids(db, resolve_group_merchant_ids(db, merchant_id))
    remaining = [
        t.taskId for t in tasks
        if t.defaultCompleted != 1 and t.taskId not in completed_ids
    ]
    derived = len(remaining) == 0
    unlocked = persisted or derived
    # 纯读:不在此写库(写库已移 persist_data_center_unlock,由 update_progress 在写路径调用),避免 GET 读路径副作用
    return {"unlocked": unlocked, "remainingTaskIds": remaining}


def persist_data_center_unlock(db: Session, merchant_id: str) -> None:
    """写入时落库:数据专区由 listing 全部完成派生为 true 且未持久化时,写 merchant.data_center_unlocked=1(永久)。幂等。

    派生判据为**组内并集**(#PB-36):仅持久化「本账号」的标记,不写组内其它账号(账号级标记不共享)。
    """
    from app.db.models.merchant import Merchant as MerchantModel

    m = db.execute(
        select(MerchantModel).where(
            MerchantModel.merchant_id == merchant_id, MerchantModel.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    if m is None or m.data_center_unlocked == 1:
        return
    tasks = _find_enabled_by_stage_ids(db, [DATA_CENTER_UNLOCK_STAGE_ID])
    if len(tasks) == 0:
        return
    completed_ids = _get_completed_task_ids(db, resolve_group_merchant_ids(db, merchant_id))
    remaining = [
        t.taskId for t in tasks
        if t.defaultCompleted != 1 and t.taskId not in completed_ids
    ]
    if len(remaining) == 0:
        m.data_center_unlocked = 1
        db.commit()


# 「全部商家进度」响应上界(管理端「商家管理」页取全部行后按 merchantId 聚合,见 #PB-22)。
# 依据:当前开发库 126 行 / 5 商家(单商家最多 43 行)、启用二级任务 49 个 → 单商家最坏约 50 行;
# 5000 行 ≈ 100 个满量商家(或约 200 个当前均量 25 行的商家),对当前规模有约 40× 余量;
# 行体积约 200B → 上限响应约 1MB,在管理端 PC Web 聚合的承受范围内。
MAX_PROGRESS_ROWS = 5000


def list_all(db: Session) -> List[MerchantTaskProgress]:
    """全部商家的任务进度行(管理端按 merchantId 聚合商家列表用)。

    排序 `merchantId, taskId` 固定(前端按 merchantId 聚合,顺序稳定才可复现、可对账);
    取到 `MAX_PROGRESS_ROWS + 1` 行即判超限,抛 400「结果过多，请按商家查询」——
    **不静默截断**(截断会让管理端列表少商家且无从察觉,AGENTS §六 禁止无界/静默响应)。
    """
    rows = db.execute(
        select(MerchantTaskProgress)
        .order_by(MerchantTaskProgress.merchantId.asc(), MerchantTaskProgress.taskId.asc())
        .limit(MAX_PROGRESS_ROWS + 1)
    ).scalars().all()
    if len(rows) > MAX_PROGRESS_ROWS:
        raise ApiException("结果过多，请按商家查询", code=400, status_code=400)
    return list(rows)


def find_by_merchant(db: Session, merchant_id: str) -> List[MerchantTaskProgress]:
    rows = db.execute(
        select(MerchantTaskProgress).where(MerchantTaskProgress.merchantId == merchant_id)
        .order_by(MerchantTaskProgress.createdAt.desc())
    ).scalars().all()
    return list(rows)


def _set_progress(db: Session, merchant_id: str, task_id: str, status: str) -> None:
    existing = db.execute(
        select(MerchantTaskProgress).where(
            MerchantTaskProgress.merchantId == merchant_id,
            MerchantTaskProgress.taskId == task_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(MerchantTaskProgress(merchantId=merchant_id, taskId=task_id, status=status,
                                    completedAt=datetime.now() if status == "completed" else None))
    else:
        # D4(#PB-27):completedAt **只在「未完成 -> 完成」跃迁时写**;对已经是 completed 的重复上报不得改写。
        # 原因:前端 saveProgress() 会把每一个已完成任务重新 POST 一次,原实现无条件刷新 → 「任务何时完成」失真
        # (实测 21 行被从 17:21 改写为 17:41)。completed -> pending -> completed 属一次**新的完成**,重新置时间
        # (pending 时清空,不保留旧值 —— 避免出现「已取消但仍带完成时间」的第三种状态)。
        # 注:`updatedAt` 由数据库 ON UPDATE CURRENT_TIMESTAMP 维护,随写入变化,不属本单范围。
        if status == "completed" and existing.status != "completed":
            existing.completedAt = datetime.now()
        elif status != "completed":
            existing.completedAt = None
        existing.status = status
    db.commit()


def _upsert_stage_progress(db: Session, merchant_id: str, stage_id: str, status: str,
                           unlocked_at, completed_at) -> None:
    from app.db.models.merchant_stage_progress import MerchantStageProgress
    row = db.execute(
        select(MerchantStageProgress).where(
            MerchantStageProgress.merchant_id == merchant_id,
            MerchantStageProgress.stage_id == stage_id,
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(MerchantStageProgress(merchant_id=merchant_id, stage_id=stage_id, status=status,
                                     unlocked_at=unlocked_at, completed_at=completed_at))
    else:
        row.status = status
        row.unlocked_at = unlocked_at
        row.completed_at = completed_at
    db.commit()


def derive_phase2_unlock(db: Session, merchant_id: str) -> bool:
    """方案 A(永久解锁):任务完成 -> current_stage=shop_setup(幂等,解锁后不回滚)+ stage_progress 落库。"""
    from app.services.merchant import set_current_stage

    task_derived, _ = get_task_derived_state(db, merchant_id)
    current = get_current_stage(db, merchant_id)
    if task_derived and current != STAGE2_UNLOCK_STAGE_ID:
        set_current_stage(db, merchant_id, STAGE2_UNLOCK_STAGE_ID)
    # 解锁口径与**读路径一致**= 组内 OR(#PB-36 方案 §3.3 改造点 5):否则「A 已解锁阶段二、
    # 同组 B 提交成功但响应里 stage2_unlocked=false」自相矛盾。无绑定 = 只有自己 → 与改造前等价。
    effective_unlocked = get_phase2_unlock_state(db, merchant_id)["unlocked"]
    now = datetime.now()

    _upsert_stage_progress(db, merchant_id, "onboarding",
                           "completed" if task_derived else "locked",
                           None, now if task_derived else None)
    _upsert_stage_progress(db, merchant_id, STAGE2_UNLOCK_STAGE_ID,
                           "unlocked" if effective_unlocked else "locked",
                           now if effective_unlocked else None, None)
    return effective_unlocked


def update_progress(db: Session, merchant_id: str, task_id: str, status: str) -> dict:
    task = db.execute(
        select(SecondLevelTask).where(SecondLevelTask.taskId == task_id)
    ).scalar_one_or_none()
    if task is None:
        raise ApiException("任务不存在", code=400, status_code=400)
    # 停用任务(status=0)不参与进度派生(真源 §1.3 停用任务自动剔除),提交会写入与派生口径不一致的垃圾记录
    if task.status != 1:
        raise ApiException("任务已停用，不可提交进度", code=400, status_code=400)
    # default_completed=1 的完成态由系统派生:可幂等提交 completed(前端"完成整个阶段"会包含它们),不可改为未完成
    if task.defaultCompleted == 1 and status == "pending":
        raise ApiException("该任务默认已完成，不可置为未完成", code=400, status_code=400)

    # 门禁按**组内并集**判定(#PB-36 方案 §3.3 改造点 5):绑定的产品语义是「同一个店」,
    # 否则「A 已解锁阶段二、同组 B 提交阶段二任务仍 403」。写入仍只写本账号(_set_progress 不变)。
    is_phase2 = task.stageId in PHASE2_STAGE_IDS
    is_data_center = task.stageId == DATA_CENTER_STAGE_ID
    if is_phase2:
        if not get_phase2_unlock_state(db, merchant_id)["unlocked"]:
            raise ApiException("阶段二未解锁", code=403, status_code=403)
    elif is_data_center:
        if not get_data_center_unlock_state(db, merchant_id)["unlocked"]:
            raise ApiException("数据专区未解锁", code=403, status_code=403)

    _set_progress(db, merchant_id, task_id, status)
    # 写路径:完成任务时若数据专区解锁派生为 true,落库持久化(不在 GET 读路径写)
    if status == "completed":
        persist_data_center_unlock(db, merchant_id)
    stage2_unlocked = derive_phase2_unlock(db, merchant_id)
    data_center_unlocked = get_data_center_unlock_state(db, merchant_id)["unlocked"]
    return {"success": True, "stage2_unlocked": stage2_unlocked, "data_center_unlocked": data_center_unlocked}

def unlock_phase1(db: Session, merchant_id: str) -> Dict[str, Any]:
    """管理端运营一键解锁(M4:幂等,永久解锁不回滚)。商家不存在抛 404。"""
    from app.services.merchant import merchant_exists, set_current_stage

    if not merchant_exists(db, merchant_id):
        raise ApiException("该商家不存在", code=404, status_code=404)
    now = datetime.now()
    if get_current_stage(db, merchant_id) != STAGE2_UNLOCK_STAGE_ID:
        set_current_stage(db, merchant_id, STAGE2_UNLOCK_STAGE_ID)
    _upsert_stage_progress(db, merchant_id, "onboarding", "completed", None, now)
    _upsert_stage_progress(db, merchant_id, STAGE2_UNLOCK_STAGE_ID, "unlocked", now, None)
    return {"success": True, "stage2_unlocked": True}

