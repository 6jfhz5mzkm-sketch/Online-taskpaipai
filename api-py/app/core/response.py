"""统一响应格式(对齐 NestJS ResponseInterceptor,契约见 project/docs/后端技术方案.md 第四章)。

成功: {"code": 0, "message": "success", "data": ...}
失败: {"code": <http_status>, "message": "...", "data": null}
"""
from typing import Any, Dict, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def api_response(data: Any = None, code: int = 0, message: str = "success") -> Dict[str, Any]:
    """构造统一响应字典。"""
    return {"code": code, "message": message, "data": data}


def success(data: Any = None, message: str = "success") -> Dict[str, Any]:
    """成功响应(对象/任意 data)。"""
    return api_response(data=data, code=0, message=message)


def success_response(
    data: Any = None, message: str = "success", status_code: int = 200
) -> JSONResponse:
    """成功响应(直接返回 JSONResponse,用于已定 status 的场景)。"""
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(success(data=data, message=message)),
    )


def error(code: int, message: str, status_code: Optional[int] = None) -> JSONResponse:
    """失败响应:code 与 HTTP 状态对齐(NestJS 约定),message 为用户可读提示。"""
    return JSONResponse(
        status_code=status_code if status_code is not None else code,
        content={"code": code, "message": message, "data": None},
    )
