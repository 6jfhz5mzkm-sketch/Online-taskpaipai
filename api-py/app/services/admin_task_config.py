"""管理端任务配置服务(阶段 / 一级任务 / 二级任务 CRUD)。

契约基准(AGENTS.md 真源优先级第 1 条:当前源码/消费者优先于文档,总控 #PB-7 已裁决):
- 前端真实调用:admin/src/api/stage.ts、first-level-task.ts、second-level-task.ts
  (GET /list、GET /{id}、POST /create、PUT /{id}、DELETE /{id})
- 既有实现参考(只读):backend/src/modules/{stage,first-level-task,second-level-task}
  (已作废的 NestJS;路径与方法与前端一致)
- 阶段管理映射表为 stage_config(NestJS stage.entity.ts @Entity('stage_config')),
  api-py 已有对应 ORM 模型,不新增表、不做 DDL。

响应为 camelCase 投影,bigint -> str,datetime -> ISO8601 毫秒 + Z(与既有管理端接口口径一致);
一级/二级任务投影复用 app.services.task 的同一份实现,避免两份字段漂移。
"""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.core.timeutil import to_iso_utc
from app.db.models.first_level_task import FirstLevelTask
from app.db.models.merchant_task_progress import MerchantTaskProgress
from app.db.models.second_level_task import SecondLevelTask
from app.db.models.stage_config import StageConfig
from app.services.task import first_level_dict, second_level_dict

# 可显式置 null 的字段(其余字段为实库/ORM 的 NOT NULL 列,收到 null 直接 400,避免 500)
_STAGE_NULLABLE = ("description",)
_GROUP_NULLABLE = ("description",)
_TASK_NULLABLE = ("description", "detail", "actionText", "actionUrl", "tag")

# 可更新字段 -> ORM 属性(与 NestJS 的 Partial<CreateXxxDto> 语义一致:只更新请求中出现的键)
_STAGE_UPDATE_FIELDS = {
    "stageId": "stage_id",
    "stageNum": "stage_num",
    "title": "title",
    "description": "description",
    "buttonText": "button_text",
    "sortOrder": "sort_order",
    "phaseNum": "phase_num",
}
_GROUP_UPDATE_FIELDS = {
    "taskId": "taskId",
    "stageId": "stageId",
    "title": "title",
    "description": "description",
    "buttonText": "button_text",
    "sortOrder": "sortOrder",
}
_TASK_UPDATE_FIELDS = {
    "taskId": "taskId",
    "firstLevelTaskId": "firstLevelTaskId",
    "stageId": "stageId",
    "title": "title",
    "description": "description",
    "detail": "detail",
    "type": "type",
    "completionType": "completionType",
    "actionText": "actionText",
    "actionUrl": "actionUrl",
    "tag": "tag",
    "defaultCompleted": "defaultCompleted",
    "sortOrder": "sortOrder",
}


def _reject_nulls(data: Dict[str, Any], nullable_keys: Tuple[str, ...], label: str) -> None:
    """拒绝把 NOT NULL 列显式置 null(否则会以 IntegrityError 500 形式爆出)。"""
    for key, value in data.items():
        if value is None and key not in nullable_keys:
            raise ApiException(f"{label}字段 {key} 不能为 null", code=400, status_code=400)


def _apply(row: Any, data: Dict[str, Any], fields: Dict[str, str]) -> None:
    for key, attr in fields.items():
        if key in data:
            setattr(row, attr, data[key])


# ---------- 阶段(stage_config) ----------

def _stage_row(s: StageConfig) -> Dict[str, Any]:
    """阶段投影(字段与 admin/src/api/stage.ts 的 Stage 接口一致)。"""
    return {
        "id": str(s.id),
        "stageId": s.stage_id,
        "stageNum": s.stage_num,
        "title": s.title,
        "description": s.description,
        "buttonText": s.button_text,
        "status": s.status,
        "sortOrder": s.sort_order,
        "phaseNum": s.phase_num,
        "createdAt": to_iso_utc(s.created_at),
        "updatedAt": to_iso_utc(s.updated_at),
    }


def _get_stage(db: Session, id: int) -> StageConfig:
    s = db.get(StageConfig, id)
    if s is None:
        raise ApiException(f"阶段 {id} 不存在", code=404, status_code=404)
    return s


def _assert_stage_id_free(db: Session, stage_id: str, exclude_id: Optional[int] = None) -> None:
    stmt = select(StageConfig.id).where(StageConfig.stage_id == stage_id)
    if exclude_id is not None:
        stmt = stmt.where(StageConfig.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise ApiException(f"阶段标识 {stage_id} 已存在", code=400, status_code=400)


def list_stages(db: Session) -> List[Dict[str, Any]]:
    """阶段列表:sort_order ASC, stage_num ASC(对齐 NestJS stage.service.findAll)。"""
    rows = db.execute(
        select(StageConfig).order_by(StageConfig.sort_order.asc(), StageConfig.stage_num.asc())
    ).scalars().all()
    return [_stage_row(s) for s in rows]


def get_stage(db: Session, id: int) -> Dict[str, Any]:
    return _stage_row(_get_stage(db, id))


def create_stage(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    _reject_nulls(data, _STAGE_NULLABLE, "阶段")
    _assert_stage_id_free(db, data["stageId"])
    s = StageConfig(
        stage_id=data["stageId"],
        stage_num=data["stageNum"],
        title=data["title"],
        description=data.get("description"),
        button_text=data.get("buttonText") or "",
        sort_order=0 if data.get("sortOrder") is None else data["sortOrder"],
        phase_num=1 if data.get("phaseNum") is None else data["phaseNum"],
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _stage_row(s)


def update_stage(db: Session, id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    _reject_nulls(data, _STAGE_NULLABLE, "阶段")
    s = _get_stage(db, id)
    if data.get("stageId") is not None and data["stageId"] != s.stage_id:
        _assert_stage_id_free(db, data["stageId"], exclude_id=id)
    _apply(s, data, _STAGE_UPDATE_FIELDS)
    if s.button_text is None:
        s.button_text = ""
    db.commit()
    db.refresh(s)
    return _stage_row(s)


def delete_stage(db: Session, id: int) -> Dict[str, Any]:
    """删除阶段;存在关联一级任务时拒绝(对齐 NestJS stage.service.remove)。"""
    s = _get_stage(db, id)
    children = db.execute(
        select(func.count()).select_from(FirstLevelTask).where(FirstLevelTask.stageId == s.stage_id)
    ).scalar_one()
    if children:
        raise ApiException(
            f"阶段「{s.title}」下有 {children} 个一级任务，无法删除。请先删除关联任务。",
            code=400,
            status_code=400,
        )
    db.delete(s)
    db.commit()
    return {"success": True}


# ---------- 一级任务(first_level_task) ----------

def _get_group(db: Session, id: int) -> FirstLevelTask:
    g = db.get(FirstLevelTask, id)
    if g is None:
        raise ApiException(f"一级任务 {id} 不存在", code=404, status_code=404)
    return g


def _assert_group_task_id_free(db: Session, task_id: str, exclude_id: Optional[int] = None) -> None:
    stmt = select(FirstLevelTask.id).where(FirstLevelTask.taskId == task_id)
    if exclude_id is not None:
        stmt = stmt.where(FirstLevelTask.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise ApiException(f"一级任务标识 {task_id} 已存在", code=400, status_code=400)


def list_groups(db: Session, stage_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """一级任务列表:可选按 stageId 过滤;sortOrder ASC(对齐 NestJS)。"""
    stmt = select(FirstLevelTask)
    if stage_id:
        stmt = stmt.where(FirstLevelTask.stageId == stage_id)
    rows = db.execute(stmt.order_by(FirstLevelTask.sortOrder.asc())).scalars().all()
    return [first_level_dict(g) for g in rows]


def get_group(db: Session, id: int) -> Dict[str, Any]:
    return first_level_dict(_get_group(db, id))


def create_group(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    _reject_nulls(data, _GROUP_NULLABLE, "一级任务")
    _assert_group_task_id_free(db, data["taskId"])
    g = FirstLevelTask(
        taskId=data["taskId"],
        stageId=data["stageId"],
        title=data["title"],
        description=data.get("description"),
        buttonText=data.get("buttonText") or "",
        sortOrder=0 if data.get("sortOrder") is None else data["sortOrder"],
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return first_level_dict(g)


def update_group(db: Session, id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    _reject_nulls(data, _GROUP_NULLABLE, "一级任务")
    g = _get_group(db, id)
    if data.get("taskId") is not None and data["taskId"] != g.taskId:
        _assert_group_task_id_free(db, data["taskId"], exclude_id=id)
    _apply(g, data, _GROUP_UPDATE_FIELDS)
    if g.buttonText is None:
        g.buttonText = ""
    db.commit()
    db.refresh(g)
    return first_level_dict(g)


def delete_group(db: Session, id: int) -> Dict[str, Any]:
    """删除一级任务;存在关联二级任务(firstLevelTaskId=taskId)时拒绝(对齐 NestJS)。"""
    g = _get_group(db, id)
    children = db.execute(
        select(func.count()).select_from(SecondLevelTask).where(SecondLevelTask.firstLevelTaskId == g.taskId)
    ).scalar_one()
    if children:
        raise ApiException(
            f"任务「{g.title}」下有 {children} 个二级任务，无法删除。请先删除关联任务。",
            code=400,
            status_code=400,
        )
    db.delete(g)
    db.commit()
    return {"success": True}


# ---------- 二级任务(second_level_task) ----------

def _get_task(db: Session, id: int) -> SecondLevelTask:
    t = db.get(SecondLevelTask, id)
    if t is None:
        raise ApiException(f"二级任务 {id} 不存在", code=404, status_code=404)
    return t


def _assert_task_id_free(db: Session, task_id: str, exclude_id: Optional[int] = None) -> None:
    stmt = select(SecondLevelTask.id).where(SecondLevelTask.taskId == task_id)
    if exclude_id is not None:
        stmt = stmt.where(SecondLevelTask.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise ApiException(f"二级任务标识 {task_id} 已存在", code=400, status_code=400)


def list_tasks(
    db: Session,
    first_level_task_id: Optional[str] = None,
    stage_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """二级任务列表:可选按 firstLevelTaskId / stageId 过滤;sortOrder ASC(对齐 NestJS)。"""
    stmt = select(SecondLevelTask)
    if first_level_task_id:
        stmt = stmt.where(SecondLevelTask.firstLevelTaskId == first_level_task_id)
    if stage_id:
        stmt = stmt.where(SecondLevelTask.stageId == stage_id)
    rows = db.execute(stmt.order_by(SecondLevelTask.sortOrder.asc())).scalars().all()
    return [second_level_dict(t) for t in rows]


def get_task(db: Session, id: int) -> Dict[str, Any]:
    return second_level_dict(_get_task(db, id))


def create_task(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    _reject_nulls(data, _TASK_NULLABLE, "二级任务")
    _assert_task_id_free(db, data["taskId"])
    t = SecondLevelTask(
        taskId=data["taskId"],
        firstLevelTaskId=data["firstLevelTaskId"],
        stageId=data["stageId"],
        title=data["title"],
        description=data.get("description"),
        detail=data.get("detail"),
        type=data["type"],
        completionType=data["completionType"],
        actionText=data.get("actionText"),
        actionUrl=data.get("actionUrl"),
        tag=data.get("tag"),
        defaultCompleted=0 if data.get("defaultCompleted") is None else data["defaultCompleted"],
        sortOrder=0 if data.get("sortOrder") is None else data["sortOrder"],
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return second_level_dict(t)


def update_task(db: Session, id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    _reject_nulls(data, _TASK_NULLABLE, "二级任务")
    t = _get_task(db, id)
    if data.get("taskId") is not None and data["taskId"] != t.taskId:
        _assert_task_id_free(db, data["taskId"], exclude_id=id)
    _apply(t, data, _TASK_UPDATE_FIELDS)
    db.commit()
    db.refresh(t)
    return second_level_dict(t)


def delete_task(db: Session, id: int) -> Dict[str, Any]:
    """删除二级任务;存在商家进度记录(merchant_task_progress.taskId)时拒绝(对齐 NestJS)。"""
    t = _get_task(db, id)
    records = db.execute(
        select(func.count()).select_from(MerchantTaskProgress).where(MerchantTaskProgress.taskId == t.taskId)
    ).scalar_one()
    if records:
        raise ApiException(
            f"任务「{t.title}」已有 {records} 条商家进度记录，无法删除。",
            code=400,
            status_code=400,
        )
    db.delete(t)
    db.commit()
    return {"success": True}
