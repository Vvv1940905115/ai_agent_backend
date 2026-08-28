"""
统一日志配置。

- 控制台输出带颜色/级别
- 同时写文件 logs/app.log（便于 Linux 服务器排查）
- 提供 get_logger(name) 供各模块使用，避免重复配置
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from app.core.config import settings

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)


def _build_logger() -> logging.Logger:
    logger = logging.getLogger(settings.APP_NAME)
    if logger.handlers:  # 避免重复添加 handler
        return logger

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 文件（滚动，单文件 10MB，保留 3 份）
    fh = RotatingFileHandler(
        os.path.join(_LOG_DIR, "app.log"), maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger.propagate = False
    return logger


app_logger = _build_logger()


def get_logger(name: str) -> logging.Logger:
    """业务模块调用：get_logger(__name__)"""
    child = logging.getLogger(f"{settings.APP_NAME}.{name}")
    child.setLevel(app_logger.level)
    return child
