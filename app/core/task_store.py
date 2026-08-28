"""
异步任务状态存储（通用）

用于「提交任务 -> 轮询状态 -> 获取结果」这类异步业务（如文生视频）。
- 内存字典 + pickle 持久化（Docker 已挂卷，重启可续跑任务）
- 线程安全（threading.Lock）
- 状态机：submitted -> processing -> succeeded | failed （失败含 timeout / rate_limited）

视频生成任务统一走本存储；业务 Agent 与接口层通过 task_id 查询进度。
"""
import os
import pickle
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("task_store")


class TaskStatus(str, Enum):
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    status: str
    created_at: float
    updated_at: float
    payload: dict
    provider_task_id: Optional[str] = None
    progress: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    retries: int = 0
    # 闭环相关（结果写多维表格 + 通知）
    bitable_record_id: Optional[str] = None
    bitable_table_id: Optional[str] = None
    notify: bool = True

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "payload": self.payload,
        }


class AsyncTaskStore:
    """通用异步任务存储（视频生成等）。单文件 pickle 持久化。"""

    def __init__(self, path: str | None = None, filename: str = "video_tasks.pkl"):
        self.path = path or settings.VECTOR_DB_PATH  # 复用持久化目录（Docker 已挂卷）
        os.makedirs(self.path, exist_ok=True)
        self.file = os.path.join(self.path, filename)
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "rb") as f:
                    self._tasks = pickle.load(f)
                logger.info("已加载异步任务 %d 个", len(self._tasks))
            except Exception as e:
                logger.warning("任务文件加载失败，忽略: %s", e)

    def _persist(self):
        try:
            with open(self.file, "wb") as f:
                pickle.dump(self._tasks, f)
        except Exception as e:
            logger.warning("任务持久化失败: %s", e)

    def create(self, record: TaskRecord) -> TaskRecord:
        with self._lock:
            self._tasks[record.task_id] = record
            self._persist()
        return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id: str, **changes) -> Optional[TaskRecord]:
        with self._lock:
            rec = self._tasks.get(task_id)
            if not rec:
                return None
            for k, v in changes.items():
                setattr(rec, k, v)
            rec.updated_at = time.time()
            self._tasks[task_id] = rec
            self._persist()
        return rec

    def list_active(self) -> list[TaskRecord]:
        """返回仍在处理中的任务，供轮询线程扫描。"""
        with self._lock:
            return [t for t in self._tasks.values()
                    if t.status in (TaskStatus.SUBMITTED.value, TaskStatus.PROCESSING.value,
                                    TaskStatus.RATE_LIMITED.value)]


# 视频生成任务的全局单例存储
video_task_store = AsyncTaskStore()
