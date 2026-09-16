"""全局异常处理器(FastAPI 应用的统一错误出口)。

真源:project/docs/后端技术方案.md §4(统一响应 {code, message, data} 与失败场景表)。
四条出口,信封与 HTTP 状态码语义保持不变:

1. `ApiException`(业务异常)-> `code` = 既有业务/HTTP 分段,message 为用户可读中文;
2. `RequestValidationError`(参数校验失败)-> **400**,message 为**口语化中文专句**(见 `VALIDATION_MESSAGE`):
   **不回显字段名、不暴露 Pydantic 内部 Loc 前缀**(`body.`/`query.`/`path.`/`header.`/`cookie.`)——
   `totalCount`/`jd_merchant_id` 这类英文字段名对商家用户没有意义(#PB-24-1-R1 用户裁决);
   完整校验细节(`loc`/`type`/`msg`)**只进日志**,且**丢弃 `input`/`ctx`** —— 避免把请求体里的
   password/token 等敏感值写进日志;
3. 框架 `HTTPException`(404/405 等)-> 中文兜底文案(404「接口不存在」/405「请求方法不允许」),
   其它状态沿用 `detail`;
4. 未知异常 -> 500「服务器内部错误」,堆栈只进日志。
"""
import json
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import ApiException
from app.core.response import error

logger = logging.getLogger("api")

# 用户可见的校验失败文案(**单一真源**;口语化,不含英文字段名与 Loc 路径):
# 排障信息不丢 —— 完整 `loc`/`type`/`msg` 由 validation_log_detail() 写进日志(见下)。
VALIDATION_MESSAGE = "提交的内容有误，请检查后重试"

# 框架级 HTTP 异常的中文兜底文案(状态码与信封不变,仅文案中文化)
HTTP_STATUS_MESSAGES: Dict[int, str] = {
    404: "接口不存在",
    405: "请求方法不允许",
}

# 单次校验失败最多写日志的错误条数(有界,避免恶意请求刷爆日志)
MAX_LOGGED_ERRORS = 20


def validation_message(exc: RequestValidationError) -> str:
    """用户可见的校验失败文案:一句口语化提示(**不回显字段名**;明细只进日志)。

    保留 `exc` 形参以维持调用方签名,并保证"措辞由本函数独占"——路由/服务不得另拼校验文案。
    #PB-24-1-R1 之前本函数会拼上「：字段 <英文字段名>」;用户裁决改为口语化,字段名不再回显。
    """
    return VALIDATION_MESSAGE


def validation_log_detail(exc: RequestValidationError) -> List[Dict[str, Any]]:
    """写日志用的校验细节:只保留 `loc`/`type`/`msg`,**丢弃 `input`/`ctx`**(防敏感值入日志)。"""
    detail: List[Dict[str, Any]] = []
    for item in (exc.errors() or [])[:MAX_LOGGED_ERRORS]:
        detail.append({
            "loc": [str(part) for part in item.get("loc", [])],
            "type": item.get("type"),
            "msg": item.get("msg"),
        })
    return detail


def register_exception_handlers(app: FastAPI) -> None:
    """把统一错误出口注册到 FastAPI 应用(唯一注册点,路由内不得自行处理这些异常)。"""

    @app.exception_handler(ApiException)
    async def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
        logger.warning(f"[{request.method}] {request.url.path} -> {exc.code} {exc.message}")
        response = error(code=exc.code, message=exc.message, status_code=exc.status_code)
        # #PB-36:业务异常可捎带旁路任务(如「重复登记 400 之后再异步发内部通知」)。
        # 失败响应同样会执行 `response.background`(starlette),故「先返回 400、再发通知」成立。
        if exc.background is not None:
            response.background = exc.background
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "参数校验失败: " + request.method + " " + request.url.path
            + " errors=" + json.dumps(validation_log_detail(exc), ensure_ascii=False)
        )
        return error(code=400, message=validation_message(exc), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = HTTP_STATUS_MESSAGES.get(exc.status_code, str(exc.detail))
        return error(code=exc.status_code, message=message, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"未处理异常: {request.method} {request.url.path} - {exc}")
        return error(code=500, message="服务器内部错误", status_code=500)
