"""业务异常定义。

NestJS 约定:异常时 code = HTTP 状态码,message 为用户可读提示,data = null。
业务侧抛 ApiException 即可,由 main.py 的全局异常处理器统一转为响应。
"""
from typing import Any, Optional


class ApiException(Exception):
    """业务异常。

    Args:
        message: 用户可读提示。
        code: 业务错误码(与 HTTP 状态对齐)。
        status_code: 若需与 code 不同的 HTTP 状态,单独指定。
        background: 失败响应需要**捎带的旁路任务**(starlette `BackgroundTasks`);由统一错误出口
            (`app/core/error_handlers.py`)挂到失败响应上执行。存在的理由(#PB-36):FastAPI 注入的
            `BackgroundTasks` 只在**正常返回**时才会执行(异常路径实测不执行),而「重复登记 400 +
            异步内部通知」要求先返回 400、再发通知,故必须由异常携带。
    """

    def __init__(self, message: str, code: int, status_code: Optional[int] = None,
                 background: Optional[Any] = None):
        self.message = message
        self.code = code
        self.status_code = status_code if status_code is not None else code
        self.background = background
        super().__init__(message)
