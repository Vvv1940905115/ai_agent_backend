"""
FastAPI 后端入口

- 注册全局异常处理（BusinessError / 校验 / 未捕获异常）
- 开启 CORS（生产请收紧 allow_origins）
- 挂载业务路由
- 提供 /health 健康检查（供 Docker HEALTHCHECK 与负载均衡探测）

启动：uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger

# 关键：import tools 聚合层，触发所有 @tool 注册（否则 Agent 找不到工具）
import app.tools  # noqa: F401

from app.routers import agent, short_video, geo, knowledge, topic
from app.video_gen.generator import video_task_manager

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("服务启动：%s (LLM=%s, EMBED=%s)", settings.APP_NAME,
                settings.LLM_PROVIDER, settings.EMBEDDING_PROVIDER)
    # 启动视频生成任务的后台轮询线程（续跑持久化任务）
    video_task_manager.ensure_poller()
    yield
    video_task_manager.stop()


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为具体前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(agent.router)
app.include_router(short_video.router)
app.include_router(geo.router)
app.include_router(knowledge.router)
app.include_router(topic.router)


@app.get("/health")
def health():
    return {"code": 0, "status": "ok", "service": settings.APP_NAME}


# ---------- 静态前端（Web 控制台，零依赖）----------
# 挂载在根路径：访问 / 即返回 frontend/index.html；/docs、/api、/health 等具体路由优先匹配。
from fastapi.staticfiles import StaticFiles
import os as _os

_FRONTEND_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "frontend")
if _os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
