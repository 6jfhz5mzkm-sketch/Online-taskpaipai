"""账号绑定服务(1 个京麦商家ID ↔ N 个商家账号;只共享进度)。

真源:project/docs/后端技术方案.md §5.2 API-22 / §6.2;方案 dev-docs/任务单/merchant-account-binding-design.md;
表:merchant_binding_group / merchant_binding_member(schema v1.10 / #DB-19,已落地)。

**唯一接缝**(方案 §6.3):组解析、活跃唯一性校验、组关闭规则全在本层;路由只做参数提取与投影。
**组/并集 SQL 只允许出现在本文件与 services/task_progress.py**(方案 §3.3 改造纪律)。

硬口径(方案 §3.2 / §4.3):
- 绑定与解绑**一律不回写** merchant.jd_merchant_id / current_stage / status;
- 解绑只把成员行 active_key 置 NULL(行即审计,留 bound_by/released_by/时间),**不动任何进度行**;
- 活跃成员 < 2 时**同事务关闭组**(active_key=NULL + closed_at/by);
- 「一个账号只能在一个活跃组」「一个 jd_merchant_id 只能一个活跃组」由复合唯一键
  (`uk_member_active` / `uk_group_active`,active_key 1/NULL)保证,读取期并集,无需加锁。
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.core.timeutil import to_iso_utc
from app.db.models.merchant import Merchant
from app.db.models.merchant_binding_group import MerchantBindingGroup
from app.db.models.merchant_binding_member import MerchantBindingMember

logger = logging.getLogger("api")

# active_key:1 = 活跃 / NULL = 已退役(组关闭、成员解绑);MySQL 唯一索引允许多个 NULL → 保留历史行
ACTIVE_KEY = 1
# 活跃成员少于该数时,组在**同一事务内**关闭(1 人活跃组语义上等于未绑定)
MIN_ACTIVE_MEMBERS = 2

# 用户可见文案(单一真源 = 本模块;真源 §5.2 API-22 + §4.3 文案表逐条登记)
MERCHANT_NOT_FOUND_MESSAGE = "商家不存在"
NOT_REGISTERED_MESSAGE = "该商家尚未登记京麦商家ID，无法绑定"
TARGET_IN_OTHER_GROUP_MESSAGE = "该账号已绑定到其它商家"
BIND_SELF_MESSAGE = "不能绑定自身"
BINDING_NOT_FOUND_MESSAGE = "绑定关系不存在"
# 并发唯一键冲突专用文案(#PB-37 D):该京麦ID 已被别的活跃组占用(uk_group_active 报 1062)
JD_MERCHANT_ID_BOUND_MESSAGE = "该京麦商家ID已有绑定组，请刷新后重试"
# 成功响应文案(中文专句,前端直接用作成功 toast;**不是**通用 `success`;真源 §4.3 + §5.2 API-22)
BIND_SUCCESS_MESSAGE = "绑定成功"
RELEASE_SUCCESS_MESSAGE = "已解绑"

# 组解析(方案 §3.3):m1 = 本账号的活跃成员行,m2 = 同组全部活跃成员(含自己),g = 活跃组
_RESOLVE_GROUP_SQL = (
    "SELECT m2.merchant_id "
    "FROM merchant_binding_member m1 "
    "JOIN merchant_binding_member m2 ON m2.group_id = m1.group_id AND m2.active_key = 1 "
    "JOIN merchant_binding_group  g  ON g.id = m1.group_id AND g.active_key = 1 "
    "WHERE m1.merchant_id = :mid AND m1.active_key = 1"
)


def _require_merchant(db: Session, merchant_id: str) -> Merchant:
    """取未软删商家;不存在 -> 404「商家不存在」(与既有口径同句)。"""
    m = db.execute(
        select(Merchant).where(Merchant.merchant_id == merchant_id, Merchant.deleted_at.is_(None))
    ).scalar_one_or_none()
    if m is None:
        raise ApiException(MERCHANT_NOT_FOUND_MESSAGE, code=404, status_code=404)
    return m


def resolve_group_merchant_ids(db: Session, merchant_id: str) -> List[str]:
    """「当前账号 + 同组其它活跃成员」的 merchant_id 列表;**无绑定 → [merchant_id]**。

    无绑定时返回值与改造前逐字段等价(调用方只把单账号换成 1 元素列表),这是「未绑定账号行为不变」的根基。
    """
    rows = db.execute(text(_RESOLVE_GROUP_SQL), {"mid": merchant_id}).scalars().all()
    ids = sorted({mid for mid in rows if mid})
    return ids or [merchant_id]


def _active_group_of_merchant(db: Session, merchant_id: str) -> Optional[MerchantBindingGroup]:
    """本账号所在的**活跃组**(uk_member_active 保证至多一条活跃成员行,故无歧义)。"""
    return db.execute(
        select(MerchantBindingGroup)
        .join(MerchantBindingMember, MerchantBindingMember.group_id == MerchantBindingGroup.id)
        .where(
            MerchantBindingMember.merchant_id == merchant_id,
            MerchantBindingMember.active_key == ACTIVE_KEY,
            MerchantBindingGroup.active_key == ACTIVE_KEY,
        )
        .order_by(MerchantBindingMember.id.desc())
    ).scalars().first()


def _member_projection(member: MerchantBindingMember, merchant: Merchant, self_merchant_id: str) -> Dict[str, Any]:
    """成员行投影(管理端「同店账号」表;**不展示手机号**)。"""
    return {
        "merchant_id": member.merchant_id,
        "nickname": merchant.nickname,
        "status": merchant.status,
        "current_stage": merchant.current_stage,
        "bound_at": to_iso_utc(member.bound_at),
        "bound_by": member.bound_by,
        "is_self": member.merchant_id == self_merchant_id,
    }


def _self_only_projection(merchant: Merchant) -> Dict[str, Any]:
    """未绑定时的成员列表 = 仅自身(bound_at/bound_by 为 null:不存在绑定事实)。"""
    return {
        "merchant_id": merchant.merchant_id,
        "nickname": merchant.nickname,
        "status": merchant.status,
        "current_stage": merchant.current_stage,
        "bound_at": None,
        "bound_by": None,
        "is_self": True,
    }


def _active_members(db: Session, group_id: int, self_merchant_id: str) -> List[Dict[str, Any]]:
    """组内活跃成员(绑定时间升序,可复现);JOIN merchant 取昵称/状态/当前阶段。"""
    rows = db.execute(
        select(MerchantBindingMember, Merchant)
        .join(Merchant, Merchant.merchant_id == MerchantBindingMember.merchant_id)
        .where(
            MerchantBindingMember.group_id == group_id,
            MerchantBindingMember.active_key == ACTIVE_KEY,
        )
        .order_by(MerchantBindingMember.bound_at.asc(), MerchantBindingMember.id.asc())
    ).all()
    return [_member_projection(member, merchant, self_merchant_id) for member, merchant in rows]


def get_bindings(db: Session, merchant_id: str) -> Dict[str, Any]:
    """绑定详情(API-22 读):`{jd_merchant_id, group_id, members[]}`;**未绑定 → group_id=null 且仅自身**。"""
    m = _require_merchant(db, merchant_id)
    group = _active_group_of_merchant(db, merchant_id)
    if group is None:
        return {
            "jd_merchant_id": m.jd_merchant_id,
            "group_id": None,
            "members": [_self_only_projection(m)],
        }
    return {
        "jd_merchant_id": group.jd_merchant_id,
        "group_id": str(group.id),
        "members": _active_members(db, group.id, merchant_id),
    }


def _bind_conflict_error(db: Session, merchant_id: str, member_merchant_id: str) -> ApiException:
    """并发唯一键冲突(1062)之后的**结构化 400**:重读当前真实绑定状态判定原因。

    判定顺序(与 `bind_member` 的预检查同序):目标账号已(被并发)进入别的组 → 复用「该账号已绑定到其它商家」;
    否则视为该京麦ID 已被别的活跃组占用 → 「该京麦商家ID已有绑定组，请刷新后重试」。
    只记日志(不含敏感值),**不加锁、不重试**(设计 §3.2:唯一键即串行化点)。
    """
    own_group = _active_group_of_merchant(db, merchant_id)
    target_group = _active_group_of_merchant(db, member_merchant_id)
    if target_group is not None and (own_group is None or target_group.id != own_group.id):
        logger.warning(f"绑定并发冲突: 目标账号已被并发绑到其它组 target={member_merchant_id}")
        return ApiException(TARGET_IN_OTHER_GROUP_MESSAGE, code=400, status_code=400)
    logger.warning(f"绑定并发冲突: 京麦商家ID 已被并发建立活跃组 merchant_id={merchant_id}")
    return ApiException(JD_MERCHANT_ID_BOUND_MESSAGE, code=400, status_code=400)


def bind_member(db: Session, merchant_id: str, member_merchant_id: str, admin_username: str) -> Dict[str, Any]:
    """绑定成员(API-22 写,幂等):目标已在同组 → 返回现状且**不写行**。

    校验顺序:自身 → 双方商家存在 → 发起方已登记京麦ID → 目标是否已在其它组。
    组键 = **发起绑定的那个商家的 merchant.jd_merchant_id**(方案 §4.3);本函数不回写任何 merchant 字段。
    """
    if member_merchant_id == merchant_id:
        raise ApiException(BIND_SELF_MESSAGE, code=400, status_code=400)
    self_m = _require_merchant(db, merchant_id)
    _require_merchant(db, member_merchant_id)
    jd_merchant_id = (self_m.jd_merchant_id or "").strip()
    if not jd_merchant_id:
        raise ApiException(NOT_REGISTERED_MESSAGE, code=400, status_code=400)

    group = _active_group_of_merchant(db, merchant_id)
    target_group = _active_group_of_merchant(db, member_merchant_id)
    if target_group is not None:
        if group is not None and target_group.id == group.id:
            # 幂等:目标已在同组 → 返回现状,不重复写行
            return {"success": True, "group_id": str(group.id),
                    "members": _active_members(db, group.id, merchant_id)}
        raise ApiException(TARGET_IN_OTHER_GROUP_MESSAGE, code=400, status_code=400)

    try:
        if group is None:
            group = MerchantBindingGroup(jd_merchant_id=jd_merchant_id, active_key=ACTIVE_KEY,
                                         created_by=admin_username)
            db.add(group)
            db.flush()  # 取 group.id
            db.add(MerchantBindingMember(group_id=group.id, merchant_id=merchant_id,
                                         active_key=ACTIVE_KEY, bound_by=admin_username))
        db.add(MerchantBindingMember(group_id=group.id, merchant_id=member_merchant_id,
                                     active_key=ACTIVE_KEY, bound_by=admin_username))
        db.commit()
    except IntegrityError:
        # 并发唯一键冲突(#PB-37 D):两名运营同时对同一京麦ID 建组(uk_group_active),        # 或同时把同一账号绑进不同组(uk_member_active)→ 1062。处理链 = 回滚(**不留半写行**)→
        # 重读真实状态 → 结构化 400;**不加锁、不重试**(设计 §3.2:唯一键即串行化点)。
        db.rollback()
        raise _bind_conflict_error(db, merchant_id, member_merchant_id)
    return {"success": True, "group_id": str(group.id),
            "members": _active_members(db, group.id, merchant_id)}


def release_member(db: Session, merchant_id: str, member_merchant_id: str, admin_username: str) -> Dict[str, Any]:
    """解绑成员(API-22 写):成员行 active_key→NULL + released_at/by 留痕;剩 < 2 名活跃成员则**同事务关组**。

    关组时**同时退役该组剩余的活跃成员行**(#PB-37 E):否则库内会留下「组已关闭 + 成员行仍 active_key=1」的
    自相矛盾状态,该账号会永久占用 `uk_member_active` 槽位而**再也无法被重新绑定**。
    用户可见后果:店内只有 2 个账号时,解绑其中任何一个 ⇒ **绑定关系整体解除**,另一个账号也不再共享本店进度
    (随即回到「1 人组 = 未绑定」);**进度行不删不清零**,各自回落。

    **不删任何进度行**(方案 §3.2 / 用例 14):解绑只改绑定关系,进度回落由读取口径自然产生。
    """
    _require_merchant(db, merchant_id)
    _require_merchant(db, member_merchant_id)
    group = _active_group_of_merchant(db, merchant_id)
    member = None
    if group is not None:
        member = db.execute(
            select(MerchantBindingMember).where(
                MerchantBindingMember.group_id == group.id,
                MerchantBindingMember.merchant_id == member_merchant_id,
                MerchantBindingMember.active_key == ACTIVE_KEY,
            )
        ).scalar_one_or_none()
    if member is None:
        raise ApiException(BINDING_NOT_FOUND_MESSAGE, code=404, status_code=404)

    now = datetime.now()
    member.active_key = None
    member.released_at = now
    member.released_by = admin_username
    # 同步 flush 后再计数(否则统计到本次已解绑的行)
    db.flush()
    remaining = db.execute(
        select(func.count()).select_from(MerchantBindingMember).where(
            MerchantBindingMember.group_id == group.id,
            MerchantBindingMember.active_key == ACTIVE_KEY,
        )
    ).scalar() or 0
    if remaining < MIN_ACTIVE_MEMBERS:
        group.active_key = None
        group.closed_at = now
        group.closed_by = admin_username
        # #PB-37 E(阻断级缺陷修复):**关组必须同事务退役最后一名活跃成员行**。
        # 只关组不退役成员行会留下「组已关闭 + 该行仍 active_key=1」的自相矛盾状态,
        # 而该行仍占着 `uk_member_active(merchant_id, active_key)` 的活跃槽位 ⇒
        # 该账号此后**再也无法被绑定**(重新绑定必然撞 1062,运营侧表现为 500/误报 400)。
        # 语义依据:1 人组 = 未绑定(方案 §4.3;schema.sql 段 31「活跃组必须 ≥ 2 名活跃成员」)。
        # 只改 active_key/released_*,**不删任何行**(成员行即审计,bound_at/bound_by 永久保留)。
        stragglers = db.execute(
            select(MerchantBindingMember).where(
                MerchantBindingMember.group_id == group.id,
                MerchantBindingMember.active_key == ACTIVE_KEY,
            )
        ).scalars().all()
        for straggler in stragglers:
            straggler.active_key = None
            straggler.released_at = now
            straggler.released_by = admin_username
    db.commit()
    return {"success": True}


def jd_merchant_id_is_taken(db: Session, jd_merchant_id: str, self_merchant_id: str) -> bool:
    """重复登记判据(方案 §5.1,任一命中即「已被登记」):

    ① 别的**不在本账号所在组内**的未软删账号已登记同值;
    ② 该值已有活跃绑定组,但**排除自己所在的组**。

    ① 之所以也要排除同组账号:组键取自「发起绑定的那个商家的登记值」,若同组账号已登记该值就一律拒绝,
    则**组内非发起方永远无法登记自己店铺的 ID**(与用例 18「本人在该组内登记同值 → 允许」直接冲突)。
    """
    group_ids = set(resolve_group_merchant_ids(db, self_merchant_id))
    other = db.execute(
        select(Merchant.merchant_id).where(
            Merchant.jd_merchant_id == jd_merchant_id,
            Merchant.merchant_id != self_merchant_id,
            Merchant.deleted_at.is_(None),
        )
    ).scalars().all()
    if any(mid not in group_ids for mid in other):
        return True

    own_group = _active_group_of_merchant(db, self_merchant_id)
    groups = db.execute(
        select(MerchantBindingGroup.id).where(
            MerchantBindingGroup.jd_merchant_id == jd_merchant_id,
            MerchantBindingGroup.active_key == ACTIVE_KEY,
        )
    ).scalars().all()
    return any(own_group is None or gid != own_group.id for gid in groups)
