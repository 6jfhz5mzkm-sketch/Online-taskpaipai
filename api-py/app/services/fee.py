"""资费服务(对齐 backend fee.service:fee_config + fee_brand_override)。"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.db.models.fee_brand_override import FeeBrandOverride
from app.db.models.fee_config import FeeConfig


def get_fee_detail(db: Session, category_id: int, brand_name: Optional[str] = None) -> dict:
    """资费详情:查基础资费;若传 brand_name 且存在品牌覆盖则用覆盖费率。"""
    fc = db.execute(
        select(FeeConfig).where(FeeConfig.category_id == category_id, FeeConfig.is_active == 1)
    ).scalar_one_or_none()
    if fc is None:
        raise ApiException("该类目暂无资费信息", code=404, status_code=404)

    operation_rate = f"{fc.operation_rate:.2f}"
    transaction_rate = f"{fc.transaction_rate:.2f}"
    is_brand_override = False

    if brand_name:
        bo = db.execute(
            select(FeeBrandOverride).where(
                FeeBrandOverride.category_id == category_id,
                FeeBrandOverride.brand_name == brand_name,
                FeeBrandOverride.is_active == 1,
            )
        ).scalar_one_or_none()
        if bo is not None:
            operation_rate = f"{bo.operation_rate:.2f}"
            transaction_rate = f"{bo.transaction_rate:.2f}"
            is_brand_override = True

    return {
        "category_id": category_id,
        "brand_name": brand_name or None,
        "operation_rate": operation_rate,
        "transaction_rate": transaction_rate,
        "deposit_gmv_lt_5w": fc.deposit_gmv_lt_5w,
        "deposit_gmv_5w_10w": fc.deposit_gmv_5w_10w,
        "deposit_gmv_10w_30w": fc.deposit_gmv_10w_30w,
        "deposit_gmv_gte_30w": fc.deposit_gmv_gte_30w,
        "is_brand_override": is_brand_override,
    }
