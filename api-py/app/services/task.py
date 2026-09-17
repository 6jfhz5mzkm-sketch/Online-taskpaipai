"""商家端任务服务(对齐 backend task.controller + 各 service)。

响应结构与 NestJS 逐字节一致:
- 字段顺序、bigint->string、int、bool、null、datetime(UTC ISO-8601 ms+Z)均对齐。
"""
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import to_iso_utc
from app.db.models.first_level_task import FirstLevelTask
from app.db.models.second_level_task import SecondLevelTask
from app.db.models.stage_config import StageConfig
from app.services.task_progress import (
    PHASE2_STAGE_IDS,
    get_data_center_unlock_state,
    get_group_progress,
    get_phase2_unlock_state,
)

UNLOCK_HINT = "完成阶段一全部任务后解锁"


def second_level_dict(t: SecondLevelTask) -> Dict[str, Any]:
    """二级任务投影(管理端任务配置接口复用同一投影,避免两份字段漂移)。"""
    return {
        "id": str(t.id),
        "taskId": t.taskId,
        "firstLevelTaskId": t.firstLevelTaskId,
        "stageId": t.stageId,
        "title": t.title,
        "description": t.description,
        "detail": t.detail,
        "type": t.type,
        "completionType": t.completionType,
        "actionText": t.actionText,
        "actionUrl": t.actionUrl,
        "actionType": t.actionType,       # #PB-39:行为语义(10 值枚举;商家端与管理端共用本投影)
        "actionParam": t.actionParam,     # #PB-39:行为参数(不透明标识;仅 data_form/data_upload 有值)
        "tag": t.tag,
        "defaultCompleted": t.defaultCompleted,
        "status": t.status,
        "sortOrder": t.sortOrder,
        "createdAt": to_iso_utc(t.createdAt),
        "updatedAt": to_iso_utc(t.updatedAt),
    }


def first_level_dict(g: FirstLevelTask) -> Dict[str, Any]:
    """一级任务投影(不含子任务);管理端任务配置接口复用同一投影,避免两份字段漂移。"""
    return {
        "id": str(g.id),
        "taskId": g.taskId,
        "stageId": g.stageId,
        "title": g.title,
        "description": g.description,
        "buttonText": g.buttonText,
        "status": g.status,
        "sortOrder": g.sortOrder,
        "createdAt": to_iso_utc(g.createdAt),
        "updatedAt": to_iso_utc(g.updatedAt),
    }


def _first_level_dict(g: FirstLevelTask, tasks: List[SecondLevelTask]) -> Dict[str, Any]:
    """商家端投影 = 一级任务 + 子任务列表(子任务保持在字段末尾,与 NestJS 字段顺序一致)。"""
    return {**first_level_dict(g), "secondLevelTasks": [second_level_dict(t) for t in tasks]}


def get_stages(db: Session, merchant_id: str) -> List[Dict[str, Any]]:
    stages = db.execute(
        select(StageConfig).order_by(StageConfig.sort_order.asc(), StageConfig.stage_num.asc())
    ).scalars().all()
    groups = db.execute(
        select(FirstLevelTask).order_by(FirstLevelTask.sortOrder.asc())
    ).scalars().all()
    all_tasks = db.execute(
        select(SecondLevelTask).order_by(SecondLevelTask.sortOrder.asc())
    ).scalars().all()

    unlocked = get_phase2_unlock_state(db, merchant_id)["unlocked"]

    result = []
    for stage in stages:
        is_phase2 = stage.stage_id in PHASE2_STAGE_IDS
        locked = is_phase2 and not unlocked

        first_level_tasks = []
        if not locked:
            stage_groups = [g for g in groups if g.stageId == stage.stage_id]
            stage_groups.sort(key=lambda g: g.sortOrder)
            for g in stage_groups:
                # 停用任务(status=0)不在商家端展示(对齐 NestJS t.status !== 0)
                t_list = [t for t in all_tasks if t.firstLevelTaskId == g.taskId and t.status != 0]
                t_list.sort(key=lambda t: t.sortOrder)
                first_level_tasks.append(_first_level_dict(g, t_list))

        d = {
            "id": str(stage.id),
            "stageId": stage.stage_id,
            "stageNum": stage.stage_num,
            "title": stage.title,
            "description": stage.description,
            "buttonText": stage.button_text or "开始",
            "status": stage.status,
            "sortOrder": stage.sort_order,
            "phaseNum": stage.phase_num,
            "createdAt": to_iso_utc(stage.created_at),
            "updatedAt": to_iso_utc(stage.updated_at),
            "phase": stage.phase_num,
            "locked": locked,
        }
        if locked:
            d["unlockHint"] = UNLOCK_HINT
        d["firstLevelTasks"] = first_level_tasks
        result.append(d)
    return result


def get_progress(db: Session, merchant_id: str) -> Dict[str, Any]:
    """商家端进度读(#PB-36):四个字段全部按**组内并集**口径;无绑定 = 只有自己(与改造前等价)。

    - `completedTasks` = 组内并集(按 taskId 去重);
    - `stage2_unlocked` / `phase1_remaining_task_ids` = 组内 OR + 并集派生;
    - `data_center_unlocked` = 本账号持久化标记 OR 组内 listing 并集派生(双层语义)。
    """
    group = get_group_progress(db, merchant_id)
    unlock = get_phase2_unlock_state(db, merchant_id)
    dc = get_data_center_unlock_state(db, merchant_id)
    return {
        "completedTasks": group["completed_task_ids"],
        "stage2_unlocked": unlock["unlocked"],
        "data_center_unlocked": dc["unlocked"],
        "phase1_remaining_task_ids": unlock["remainingTaskIds"],
    }
