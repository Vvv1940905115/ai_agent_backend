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

# 每个用户可自带 LLM Key：把 OpenAI 的鉴权/接口错误转成友好的中文提示，
# 避免把原始 traceback 直接抛给用户。
try:
    from openai import APIError as _OAApiError
    from openai import AuthenticationError as _OAAuthError
    _HAS_OPENAI = True
except Exception:  # pragma: no cover - openai 一定存在，但保持健壮
    _HAS_OPENAI = False


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

    if _HAS_OPENAI:
        @app.exception_handler(_OAAuthError)
        async def _oa_auth(request: Request, exc: "_OAAuthError"):
            # 多半是用户在界面里填的 Key 无效/过期
            logger.warning("LLM 鉴权失败（可能是用户自填的 API Key 无效）：%s", exc)
            return JSONResponse(status_code=400, content={
                "code": 401,
                "message": "API Key 无效或已过期，请检查你在「API 配置」中填写的模型 Key",
                "detail": str(exc),
            })

        @app.exception_handler(_OAApiError)
        async def _oa_api(request: Request, exc: "_OAApiError"):
            logger.warning("LLM 接口调用失败：%s", exc)
            return JSONResponse(status_code=502, content={
                "code": 502,
                "message": "调用大模型接口失败，请检查 base_url / model 是否正确，或网络是否可达",
                "detail": str(exc),
            })
