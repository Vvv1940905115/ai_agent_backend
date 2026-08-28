"""
选题批次存储（TopicBatchStore）

- 一次「生成选题」产生一个 batch（batch_id），含多条 topic
- 支持人工审核：approve(batch_id, topic_ids) 标记优质选题进入下一环节（生成视频）
- 可选同步写入飞书多维表格（每条 topic 一条记录），保存 record_id 以便后续更新状态
"""
import os
import pickle
import threading
import time
import uuid

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("topic.batch")


class TopicBatchStore:
    def __init__(self, path: str | None = None, filename: str = "topic_batches.pkl"):
        self.path = path or settings.VECTOR_DB_PATH
        os.makedirs(self.path, exist_ok=True)
        self.file = os.path.join(self.path, filename)
        self._batches: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "rb") as f:
                    self._batches = pickle.load(f)
            except Exception as e:
                logger.warning("选题批次文件加载失败，忽略: %s", e)

    def _persist(self):
        try:
            with open(self.file, "wb") as f:
                pickle.dump(self._batches, f)
        except Exception as e:
            logger.warning("选题批次持久化失败: %s", e)

    def create(self, industry: str, style: str, topics: list[dict],
               record_ids: list | None = None) -> dict:
        batch_id = "batch_" + uuid.uuid4().hex[:10]
        with self._lock:
            self._batches[batch_id] = {
                "batch_id": batch_id,
                "industry": industry,
                "style": style,
                "topics": topics,             # list[dict]，含 id
                "record_ids": record_ids or [],  # 对应多维表格 record_id
                "approved": [],                # 已审核通过的 topic id
                "created_at": time.time(),
            }
            self._persist()
        return self._batches[batch_id]

    def get(self, batch_id: str) -> dict | None:
        with self._lock:
            return self._batches.get(batch_id)

    def approve(self, batch_id: str, topic_ids: list) -> dict | None:
        with self._lock:
            b = self._batches.get(batch_id)
            if not b:
                return None
            valid = {t.get("id") for t in b["topics"]}
            b["approved"] = [tid for tid in topic_ids if tid in valid]
            self._persist()
        return b

    def list_approved(self, batch_id: str) -> list[dict]:
        b = self.get(batch_id)
        if not b:
            return []
        appr = set(b["approved"])
        return [t for t in b["topics"] if t.get("id") in appr]


# 全局单例
topic_batch_store = TopicBatchStore()
