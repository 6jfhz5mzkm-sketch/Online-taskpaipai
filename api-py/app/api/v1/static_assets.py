"""静态资源单文件端点(商家顾问企微二维码)。

真源:project/docs/后端技术方案.md §5.2 `GET /api/static/advisor-qr.jpg`(前端 `<img src>` 直接引用;
`/api/feishu/advisor-qr` 的 `qr_url` 即该路径)。

设计约束:
- **只服务配置指定的单个文件**(`ADVISOR_QR_FILE`,默认 `static/advisor-qr.jpg`,相对 api-py 根目录);
  **不挂目录静态服务、路由不接受任何路径/查询参数** → 结构上不存在目录穿越入口;
- **无需鉴权**:前端把它当 `<img src>` 用,无法携带 Authorization;缺文件时返回 404 而非 401;
- 文件缺失 -> **结构化 404**「顾问二维码未配置」;配置越界/非普通文件/不可读 -> **结构化 500**,
  **响应不回显绝对路径**(细节只记日志)。
"""
import logging
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import BASE_DIR, get_settings
from app.core.response import error

logger = logging.getLogger("api")

router = APIRouter(prefix="/static", tags=["静态资源"])

# 唯一被服务的静态文件路径(固定常量;任何请求参数都不参与路径拼接)
ADVISOR_QR_ROUTE = "/advisor-qr.jpg"
MISSING_MESSAGE = "顾问二维码未配置"
UNAVAILABLE_MESSAGE = "顾问二维码不可用"
CACHE_CONTROL = "public, max-age=3600"


def resolve_advisor_qr_path(configured: str) -> Path:
    """把配置值解析为 api-py 根目录内的绝对路径;越界(如 `../`)抛 `ValueError`。

    纯函数,便于直接断言「不存在路径拼接入口」:路径**只来自配置**,与请求无关。
    """
    if not configured or not configured.strip():
        raise ValueError("ADVISOR_QR_FILE 未配置")
    root = BASE_DIR.resolve()
    candidate = (root / configured.strip()).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:  # 配置写到了 api-py 目录之外
        raise ValueError("ADVISOR_QR_FILE 必须位于 api-py 目录内") from exc
    return candidate


@router.get(ADVISOR_QR_ROUTE, summary="商家顾问企微二维码(静态单文件,无需登录)")
def advisor_qr():
    """返回顾问企微二维码图片;未配置返回结构化 404,不可用返回结构化 500。"""
    try:
        path = resolve_advisor_qr_path(get_settings().ADVISOR_QR_FILE)
    except ValueError as exc:
        logger.error(f"顾问二维码配置不合法: {exc}")
        return error(code=500, message=UNAVAILABLE_MESSAGE, status_code=500)

    if not path.exists():
        return error(code=404, message=MISSING_MESSAGE, status_code=404)
    if not path.is_file() or not os.access(path, os.R_OK):
        # 不回显路径;细节只进日志
        logger.error("顾问二维码文件不可用(非普通文件或不可读)")
        return error(code=500, message=UNAVAILABLE_MESSAGE, status_code=500)

    # Content-Type 由 FileResponse 按扩展名推断(.jpg -> image/jpeg)
    return FileResponse(path, headers={"Cache-Control": CACHE_CONTROL})
