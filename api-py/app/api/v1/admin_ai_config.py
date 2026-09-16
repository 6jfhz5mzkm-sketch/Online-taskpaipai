"""管理端 AI 分入口配置路由(P7 v1.1 §5)。

权限:**仅 super_admin**(非 super_admin 完全不可见:前端菜单/路由由 #AF-14 承接,后端 403 是唯一可信边界)。
凭据纪律:任何响应都不返回密钥原文、密文、长度或 ENC key 任何形态(只回掩码 + 指纹 + 状态)。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.exceptions import ApiException
from app.core.response import success
from app.core.utils import get_client_ip
from app.db.session import get_db
from app.services import ai
from app.services.ai_config import list_entry_configs, resolve_config, update_entry_config

router = APIRouter(prefix="/admin/ai-config", tags=["管理端 AI 配置"])


class AiConfigPatchBody(BaseModel):
    """部分更新:字段省略 = 不修改;显式 null = 清除并回落 env(空串由服务层判 400)。"""

    api_key: Optional[str] = Field(default=None, max_length=256)
    base_url: Optional[str] = Field(default=None, max_length=255, pattern=r"^https?://")
    model: Optional[str] = Field(default=None, max_length=128)
    timeout_ms: Optional[int] = Field(default=None, ge=1000, le=600000)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000)
    daily_limit: Optional[int] = Field(default=None, ge=0, le=100)
    enabled: Optional[bool] = None


@router.get("/list", summary="AI 分入口配置总览(仅 super_admin)")
def ai_config_list(
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin")),
) -> dict:
    return success(list_entry_configs(db))


@router.put("/{entry}", summary="更新某个入口的 AI 配置(仅 super_admin)")
def ai_config_update(
    entry: str,
    body: AiConfigPatchBody,
    request: Request,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin")),
) -> dict:
    patch = body.model_dump(exclude_unset=True)
    return success(update_entry_config(db, entry, patch, admin, get_client_ip(request)))


@router.post("/{entry}/verify", summary="用当前生效配置做连通性自检(仅 super_admin,不落库)")
def ai_config_verify(
    entry: str,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin")),
) -> dict:
    cfg = resolve_config(db, entry)          # 入口枚举非法 -> 404
    result = ai.verify_connection(cfg)
    if not result["ok"]:
        # 失败统一 502(P7 §5.2「502 AI 调用失败(verify)」),附错误码便于排障(不泄漏密钥材料)
        raise ApiException(f"{result['message']}（错误码 {result['code']}）", code=502, status_code=502)
    return success({
        "entry": entry,
        "model": cfg.model,
        "baseUrl": cfg.base_url,
        "message": result["message"],
        "effectiveSource": {"apiKey": cfg.sources["api_key"], "baseUrl": cfg.sources["base_url"]},
    })
