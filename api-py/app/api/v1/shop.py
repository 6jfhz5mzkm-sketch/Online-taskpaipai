"""店铺数据 + AI 优化路由(对齐 NestJS shop/ai/image-optimize/title-optimize)。"""
import base64
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_merchant
from app.core.exceptions import ApiException
from app.core.response import success, success_response
from app.db.session import get_db
from app.services import ai, shop
from app.core.utils import get_client_ip
from app.services.shop import clear_merchant_data


router = APIRouter(prefix="/shop", tags=["店铺数据"], dependencies=[Depends(get_current_merchant)])

class StarBody(BaseModel):
    shopStar: float = Field(..., ge=1, le=5)
    serviceScore: Optional[float] = Field(default=None, ge=0, le=10)
    logisticsScore: Optional[float] = Field(default=None, ge=0, le=10)
    afterSaleScore: Optional[float] = Field(default=None, ge=0, le=10)
    productScore: Optional[float] = Field(default=None, ge=0, le=10)
    dataDate: str
# INT UNSIGNED 列上界(真源 project/scripts/schema.sql):表单整数值超出即 400,不让脏值打到 DB(避免 500)
UNSIGNED_INT_MAX = 4294967295

class ProductCountBody(BaseModel):
    totalCount: int = Field(..., ge=0, le=UNSIGNED_INT_MAX)
    onSaleCount: Optional[int] = Field(default=None, ge=0, le=UNSIGNED_INT_MAX)
    offSaleCount: Optional[int] = Field(default=None, ge=0, le=UNSIGNED_INT_MAX)
    auditCount: Optional[int] = Field(default=None, ge=0, le=UNSIGNED_INT_MAX)
    dataDate: str
class HealthScoreBody(BaseModel):
    avgScore: float = Field(..., ge=0, le=100)
    scoreGte90Count: Optional[int] = Field(default=None, ge=0, le=UNSIGNED_INT_MAX)
    score78_90Count: Optional[int] = Field(default=None, ge=0, le=UNSIGNED_INT_MAX)
    score60_77Count: Optional[int] = Field(default=None, ge=0, le=UNSIGNED_INT_MAX)
    scoreLt60Count: Optional[int] = Field(default=None, ge=0, le=UNSIGNED_INT_MAX)
    dataDate: str
class TitleOptBody(BaseModel):
    mode: str; category: str; brand: Optional[str] = None; model: Optional[str] = None
    features: Optional[str] = None; condition: Optional[str] = None; keyAttrs: Optional[str] = None; saleAttrs: Optional[str] = None; currentTitle: Optional[str] = None

@router.get("/summary", summary="数据看板聚合")
def summary(time_range: str = "7d", merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    # #PB-30:补枚举校验(真源 API-14)。time_range 可选(默认 7d,前端始终显式传),非法值 400 中文专句。
    shop.assert_time_range(time_range)
    return success(shop.get_summary(db, merchant["merchant_id"], time_range))

@router.post("/star", summary="上传店铺星级")
def star(body: StarBody, merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success_response(shop.upload_star(db, merchant["merchant_id"], body.model_dump()), status_code=201)
@router.post("/product-count", summary="上传商品数量")
def product_count(body: ProductCountBody, merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success_response(shop.upload_product_count(db, merchant["merchant_id"], body.model_dump()), status_code=201)
@router.post("/health-score", summary="上传商品信息健康分")
def health_score(body: HealthScoreBody, merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success_response(shop.upload_health_score(db, merchant["merchant_id"], body.model_dump()), status_code=201)

@router.post("/clear-data", summary="清除当前所有数据(shop_* + T2.5 完成态,保留AI日志/数据专区解锁)")
def clear_data(merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success_response(clear_merchant_data(db, merchant["merchant_id"]), status_code=201)


# Excel 导入不再接收 timeRange:上传时按**文件日期跨度**自动推导 time_range(单日->yesterday / 2-10 天->7d / 11-31 天->30d,
# 其它跨度 400)。前端 #F-30 已删除该死参数;旧客户端多传的 form 字段被 FastAPI 忽略(不报错)。
def _excel(typ: str, file: UploadFile, merchant: Dict[str, Any], db: Session):
    if file.size and file.size > 10 * 1024 * 1024:
        raise ApiException("文件过大", code=400, status_code=400)
    raw = file.file.read()
    result = shop.upload_excel(db, merchant["merchant_id"], typ, raw, file.content_type or "")
    # 有写入 -> 201(既有契约不变);**全部行皆坏 -> 200 + 清单**(有内容要展示但没写入,不再 400 丢清单)
    return success_response(result, status_code=201 if result.get("count") else 200)

@router.post("/trade", summary="上传交易数据 Excel")
def trade(file: UploadFile = File(...), merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return _excel("trade", file, merchant, db)
@router.post("/traffic", summary="上传流量数据 Excel")
def traffic(file: UploadFile = File(...), merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return _excel("traffic", file, merchant, db)
@router.post("/product", summary="上传商品数据 Excel")
def product(file: UploadFile = File(...), merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return _excel("product", file, merchant, db)

@router.post("/analysis", summary="AI 经营分析")
def analysis(request: Request, time_range: Optional[str] = None, merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    # time_range 必填且为枚举 yesterday/7d/30d,否则 400。
    # #PB-30:文案改为中文专句(与 /summary 共用 shop.TIME_RANGE_INVALID_MESSAGE),不再回显英文枚举原文。
    shop.assert_time_range(time_range)
    # 可信 IP(SEC-02):不再取客户端可控的 X-Forwarded-For,默认用 request.client.host(见 app/core/utils.py)
    ip = get_client_ip(request)
    return success(ai.analyze(db, merchant["merchant_id"], time_range, ip))
@router.post("/image-optimize", summary="商品主图 AI 优化")
def image_optimize(file: UploadFile = File(...), merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    # DoS:路由层先拒>5MB(不整读进内存做 base64),与 Excel 路由大小上限一致
    if file.size and file.size > 5 * 1024 * 1024:
        raise ApiException("图片过大，请上传 5MB 以内的图片", code=400, status_code=400)
    raw = file.file.read()
    data_url = f"data:{file.content_type};base64," + base64.b64encode(raw).decode()
    return success(ai.optimize_image(db, merchant["merchant_id"], file.content_type, data_url, len(raw)))
@router.post("/title-optimize", summary="商品标题 AI 优化")
def title_optimize(body: TitleOptBody, merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success(ai.optimize_title(db, merchant["merchant_id"], body.model_dump()))