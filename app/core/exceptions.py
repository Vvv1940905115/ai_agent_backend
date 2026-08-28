"""
业务异常与全局异常处理器。

- BusinessError：可预期的业务错误（如缺少 API Key、外部调用失败），返回 4xx
- 统一错误响应结构：{"code": int, "message": str, "detail": Any}
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("exceptions")


class BusinessError(Exception):
    """可预期的业务异常。"""

    def __init__(self, message: str, code: int = 400, detail=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = detail


def register_exception_handlers(app: FastAPI) -> None:
    """在 main.py 中调用，集中注册异常处理。"""

    @app.exception_handler(BusinessError)
    async def _biz(request: Request, exc: BusinessError):
        logger.warning("BusinessError: %s | %s", exc.message, exc.detail)
        return JSONResponse(status_code=exc.code, content={
            "code": exc.code, "message": exc.message, "detail": exc.detail
        })

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        logger.warning("ValidationError: %s", exc.errors())
        return JSONResponse(status_code=422, content={
            "code": 422, "message": "请求参数校验失败", "detail": exc.errors()
        })

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(status_code=500, content={
            "code": 500, "message": "服务器内部错误", "detail": str(exc)
        })
