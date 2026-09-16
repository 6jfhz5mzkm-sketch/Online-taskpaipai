"""商家服务(对齐 backend merchant.service 只读/登录 upsert/管理列表)。"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTasks

from app.core.error_handlers import VALIDATION_MESSAGE
from app.core.exceptions import ApiException
from app.core.timeutil import to_iso_utc
from app.db.models.merchant import Merchant
from app.services.internal_notify import notify_duplicate_registration
from app.services.merchant_binding import jd_merchant_id_is_taken

logger = logging.getLogger("api")

# 管理端列表筛选的**已登记取值**(#PB-24;真源 project/docs/后端技术方案.md §5.2 API-17):
# - `current_stage`:onboarding(入驻准备 / 大阶段 phase-1)与 shop_setup(开店搭建 / 大阶段 phase-2 解锁);
# - `status`:0 禁用 / 1 正常 / 2 已退出。
# 取值集合是**业务语义**,故 owner 在本层(路由只透传,不重复校验);非法值 -> 400,
# 文案复用统一校验出口的 VALIDATION_MESSAGE(不另造句子)。
REGISTERED_STAGES: frozenset = frozenset({"onboarding", "shop_setup"})
REGISTERED_STATUSES: frozenset = frozenset({0, 1, 2})
# 线上是查询串,按**原文严格匹配**收(不走 int(),避免 "1_0"/全角数字等被 Python 隐式接受)
_REGISTERED_STATUS_TEXT: frozenset = frozenset(str(s) for s in REGISTERED_STATUSES)


def _blank_to_none(raw: Any) -> Optional[str]:
    """筛选入参缺省归一:None / 空串 / 纯空白 = 不筛选(前端「全部」选项常提交空串)。"""
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _reject_filter_value(field_name: str, raw: Any, registered: frozenset) -> None:
    """非法筛选值 -> 400(文案复用统一校验出口,不新造句子)。

    排障细节(取值 + 已登记集合)**只进日志**,不随响应回显——与 error_handlers「校验明细只进日志」同一口径。
    """
    logger.warning(f"商家列表筛选参数非法: {field_name}={raw!r}, 已登记取值={sorted(registered)}")
    raise ApiException(VALIDATION_MESSAGE, code=400, status_code=400)


def _validated_stage(raw: Any) -> Optional[str]:
    """归一 + 校验 current_stage 筛选值;未登记 -> 400。"""
    value = _blank_to_none(raw)
    if value is not None and value not in REGISTERED_STAGES:
        _reject_filter_value("stage", value, REGISTERED_STAGES)
    return value


def _validated_status(raw: Any) -> Optional[int]:
    """归一 + 校验 status 筛选值(严格原文匹配);未登记 -> 400。"""
    value = _blank_to_none(raw)
    if value is None:
        return None
    if value not in _REGISTERED_STATUS_TEXT:
        _reject_filter_value("status", value, REGISTERED_STATUSES)
    return int(value)


def _find_by_merchant_id(db: Session, merchant_id: str) -> Optional[Merchant]:
    return db.execute(
        select(Merchant).where(Merchant.merchant_id == merchant_id, Merchant.deleted_at.is_(None))
    ).scalar_one_or_none()


def get_merchant_info(db: Session, merchant_id: str) -> dict:
    """商家信息(真源 API-02);不存在抛 404。"""
    m = _find_by_merchant_id(db, merchant_id)
    if m is None:
        raise ApiException("商家不存在", code=404, status_code=404)
    return {
        "merchant_id": m.merchant_id,
        "nickname": m.nickname,
        "avatar": m.avatar,
        "merchant_name": m.merchant_name,
        "current_stage": m.current_stage,
        "status": m.status,
    }


def get_current_stage(db: Session, merchant_id: str) -> str:
    m = _find_by_merchant_id(db, merchant_id)
    return m.current_stage if m else "onboarding"


def set_current_stage(db: Session, merchant_id: str, stage: str) -> None:
    """设置当前阶段;商家不存在则 upsert(对齐 NestJS setCurrentStage)。"""
    m = _find_by_merchant_id(db, merchant_id)
    if m is None:
        m = upsert_from_feishu(db, merchant_id, "飞书用户")
    if m.current_stage == stage:
        return
    m.current_stage = stage
    db.commit()


def upsert_from_feishu(db: Session, merchant_id: str, nickname: str, feishu_open_id: Optional[str] = None) -> Merchant:
    """飞书登录 upsert(真源 API-01)。"""
    m = _find_by_merchant_id(db, merchant_id)
    if m is None and feishu_open_id:
        m = db.execute(
            select(Merchant).where(Merchant.feishu_open_id == feishu_open_id, Merchant.deleted_at.is_(None))
        ).scalar_one_or_none()

    if m is not None:
        m.nickname = nickname or m.nickname
        m.feishu_open_id = feishu_open_id or m.feishu_open_id
        m.last_active_at = datetime.now()
        db.commit()
        return m

    m = Merchant(
        merchant_id=merchant_id,
        nickname=nickname or "飞书用户",
        feishu_open_id=feishu_open_id,
        current_stage="onboarding",
        status=1,
        registered_at=datetime.now(),
        last_active_at=datetime.now(),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def merchant_exists(db: Session, merchant_id: str) -> bool:
    return _find_by_merchant_id(db, merchant_id) is not None


def list_all(db: Session, query: Dict[str, Any]) -> Dict[str, Any]:
    """商家主表列表(一商家一条,created_at 倒序 + 分页 + 关键词检索)。

    关键词检索(#PB-29)对 **4 个字段做 OR 模糊包含匹配**:`merchant_id`(商家ID)/ `nickname`(昵称)/
    `jd_merchant_id`(京麦商家ID,可 NULL)/ `shop_name`(店铺名,可 NULL)。范围限于已登记字段,
    保持既有行为(包含匹配、分页、page_size 上界 100、deleted_at IS NULL、created_at 倒序)。

    阶段/状态筛选(#PB-24):`stage` 精确匹配 `current_stage`、`status` 精确匹配 `merchant.status`,
    两者**只接受已登记取值**(见 REGISTERED_STAGES / REGISTERED_STATUSES),未登记 -> 400;
    与 keyword / 分页 / deleted_at IS NULL / created_at 倒序 **全部 AND 组合**。
    响应结构与 **9 字段投影**(#PB-25 起含 `status`)不变,`total` 为**筛选后**的行数。
    """
    page = max(1, int(query.get("page") or 1))
    page_size = min(100, max(1, int(query.get("page_size") or 20)))
    # 筛选值校验先于取数:非法值 -> 400,不返回任何行(避免「传错值」被显示成「没有数据」)
    stage = _validated_stage(query.get("stage"))
    status = _validated_status(query.get("status"))
    stmt = select(Merchant).where(Merchant.deleted_at.is_(None))
    if stage is not None:
        stmt = stmt.where(Merchant.current_stage == stage)
    if status is not None:
        stmt = stmt.where(Merchant.status == status)
    kw = query.get("keyword") or ""
    if kw:
        # 4 字段 OR 模糊匹配:用户诉求「只要输入完整的商家ID，能搜出来对应的商家就可以」(#PB-29);
        # jd_merchant_id / shop_name 可为 NULL —— SQL 的 LIKE 对 NULL 求值为 NULL(非真),不会出错也不会误命中。
        pattern = f"%{kw}%"
        stmt = stmt.where(or_(
            Merchant.merchant_id.like(pattern),
            Merchant.nickname.like(pattern),
            Merchant.jd_merchant_id.like(pattern),
            Merchant.shop_name.like(pattern),
        ))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(Merchant.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    lst = [{
        "merchant_id": m.merchant_id,
        "nickname": m.nickname,
        "merchant_name": m.merchant_name,
        "current_stage": m.current_stage,
        "status": m.status,  # 0 禁用 / 1 正常 / 2 已退出(#PB-25;管理端「商家清单」状态列)
        "jd_merchant_id": m.jd_merchant_id,
        "shop_name": m.shop_name,
        "last_login_at": to_iso_utc(m.last_active_at),
        "created_at": to_iso_utc(m.created_at),
    } for m in rows]
    return {"list": lst, "total": total, "page": page, "page_size": page_size}


# 登记字段格式规则(真源 project/docs/后端技术方案.md §5.2 API-20;用户 2026-09-14 裁决):
# 京麦商家ID 仅数字、店铺名称 仅汉字。长度上界由 DTO 承载(jd_merchant_id ≤64 / shop_name ≤128,与列一致),
# 本层只做字符集校验,避免同一规则两处实现。
# 空串与 null 同义(未登记/清空):表单未填时前端提交的就是空串,不能因此 400。
_JD_MERCHANT_ID_PATTERN = re.compile(r"^[0-9]+$")
_SHOP_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fa5]+$")
_REGISTRATION_RULES = (
    ("jd_merchant_id", _JD_MERCHANT_ID_PATTERN, "京麦商家ID仅支持数字"),
    ("shop_name", _SHOP_NAME_PATTERN, "店铺名称仅支持汉字"),
)
# 重复登记拒绝文案(用户原话,接口级**单一真源**;真源 §5.2 API-20 扩展 + §4.3 文案表;
# #PB-36 方案 §5.1:**不回显占用方账号**,防枚举/隐私)
JD_MERCHANT_ID_TAKEN_MESSAGE = "该商家已被登记"


def _normalize_registration(patch: Dict[str, Any]) -> Dict[str, Any]:
    """登记字段的格式校验 + 归一化(**唯一 owner**,路由不重复校验)。

    - 缺省字段(未出现在 patch)不处理;
    - `null` 与空串 -> `None`(= 清空,回落「未登记」);
    - 非空串必须整体匹配字符集规则,否则 400(**文案不回显用户输入原文**);
    - 返回新字典,不改调用方入参。
    """
    normalized: Dict[str, Any] = {}
    for field_name, pattern, message in _REGISTRATION_RULES:
        if field_name not in patch:
            continue
        value = patch[field_name]
        if value is None or value == "":
            normalized[field_name] = None
            continue
        if not isinstance(value, str) or not pattern.match(value):
            raise ApiException(message, code=400, status_code=400)
        normalized[field_name] = value
    return normalized


def _duplicate_registration_error(merchant_id: str, phone: Optional[str], jd_merchant_id: str) -> ApiException:
    """重复登记 -> 400「该商家已被登记」,**并捎带异步内部通知**(#PB-36 方案 §5.1/§5.3)。

    通知挂在异常上、由统一错误出口附到失败响应:FastAPI 注入的 `BackgroundTasks` 只在正常返回时执行
(实测异常路径不执行),而契约要求**先返回 400、再异步发送**,故必须由异常携带(见 core/exceptions.py)。
    通知内部的任何异常都只落 `internal_notify_log.failed`,绝不改变 400 的返回。
    """
    tasks = BackgroundTasks()
    tasks.add_task(notify_duplicate_registration, merchant_id=merchant_id, phone=phone,
                   jd_merchant_id=jd_merchant_id)
    return ApiException(JD_MERCHANT_ID_TAKEN_MESSAGE, code=400, status_code=400, background=tasks)


def save_registration(db: Session, merchant_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """登记 jd_merchant_id/shop_name(幂等覆盖 + 格式校验 + 唯一性校验)。patch 仅含请求体中出现的字段。

    语义:字段缺省(未传)不更新;传 null / 空串清空;传字符串先校验格式再覆盖
    (商家ID 仅数字 / 店铺名称 仅汉字,真源 API-20;非法 -> 400 且不回显原文)。

    唯一性(#PB-36 方案 §5.1):**显式带** `jd_merchant_id` 且非空、且与本账号当前值不同时,
    若该值已被别的(非本组)活跃账号登记、或已有活跃绑定组(排除自己所在的组)-> 400「该商家已被登记」,
    **写入不发生**(本账号原值保持不变)+ 异步内部通知;同值重提交 = 幂等,不触发。(判据见 merchant_binding)
    """
    patch = _normalize_registration(patch)
    m = _find_by_merchant_id(db, merchant_id)
    if m is None:
        raise ApiException("商家不存在", code=404, status_code=404)
    new_jd = patch.get("jd_merchant_id")
    if new_jd and new_jd != m.jd_merchant_id and jd_merchant_id_is_taken(db, new_jd, merchant_id):
        raise _duplicate_registration_error(merchant_id, m.phone, new_jd)
    if patch:
        for k in ("jd_merchant_id", "shop_name"):
            if k in patch:
                setattr(m, k, patch[k])
        db.commit()
    return {"success": True}


def get_registration(db: Session, merchant_id: str) -> Dict[str, Any]:
    m = _find_by_merchant_id(db, merchant_id)
    if m is None:
        raise ApiException("商家不存在", code=404, status_code=404)
    return {"jd_merchant_id": m.jd_merchant_id, "shop_name": m.shop_name}
