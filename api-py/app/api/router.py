"""API 路由聚合(挂 /api 前缀,与 NestJS setGlobalPrefix('api') 一致,/health 除外)。

阶段1:已挂鉴权测试接口(app/api/v1/test);后续按模块 include 子路由。
"""
from fastapi import APIRouter

from app.api.v1.admin_account import router as admin_account_router
from app.api.v1.admin_ai_config import router as admin_ai_config_router
from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.admin_group import router as admin_group_router
from app.api.v1.admin_merchant import router as admin_merchant_router
from app.api.v1.admin_stage import router as admin_stage_router
from app.api.v1.admin_task import router as admin_task_router
from app.api.v1.auth import router as auth_router
from app.api.v1.category import router as category_router
from app.api.v1.event import router as event_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.fee import router as fee_router
from app.api.v1.feishu import router as feishu_router
from app.api.v1.merchant import router as merchant_router
from app.api.v1.shop import router as shop_router
from app.api.v1.static_assets import router as static_assets_router
from app.api.v1.task import router as task_router
from app.api.v1.test import router as test_router
from app.api.v1.tour import router as tour_router
from app.api.v1.trademark import router as trademark_router
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter(prefix=settings.API_PREFIX)

# 阶段1:鉴权测试
api_router.include_router(test_router)
# 阶段2:核心读接口 + 登录
api_router.include_router(category_router)
api_router.include_router(fee_router)
api_router.include_router(merchant_router)
api_router.include_router(trademark_router)
api_router.include_router(auth_router)
api_router.include_router(admin_auth_router)
# 阶段3:任务体系
api_router.include_router(task_router)
api_router.include_router(admin_merchant_router)
# 阶段3:管理端任务配置(阶段/一级任务/二级任务,对齐 admin 前端真实调用)
api_router.include_router(admin_stage_router)
api_router.include_router(admin_group_router)
api_router.include_router(admin_task_router)
# 阶段4:反馈/事件/管理账号
api_router.include_router(feedback_router)
api_router.include_router(event_router)
api_router.include_router(admin_account_router)
# 管理端 AI 分入口配置(仅 super_admin;掩码/指纹投影,见 services/ai_config.py)
api_router.include_router(admin_ai_config_router)
# 阶段5:tour(引导)/shop(AI+上传)/feishu(推送)
api_router.include_router(tour_router)
api_router.include_router(shop_router)
api_router.include_router(feishu_router)
# 静态资源(单文件,无需登录):商家顾问企微二维码(前端 <img src> 直接引用)
api_router.include_router(static_assets_router)
