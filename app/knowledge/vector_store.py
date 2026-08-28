"""
向量存储（Vector Store）

采用轻量 numpy + pickle 持久化方案：
- 优点：零额外服务依赖，Docker 直接挂载卷即可，适合中小规模知识库（万级以内）
- 检索：余弦相似度 Top-K
- 扩展：如数据量增大，可把本类替换为 Chroma / Milvus 后端（保持 search/upsert 接口不变）

存储文件：settings.VECTOR_DB_PATH/vector_store.pkl
"""
import os
import pickle

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("knowledge.store")


class VectorStore:
    def __init__(self, path: str | None = None):
        self.path = path or settings.VECTOR_DB_PATH
        os.makedirs(self.path, exist_ok=True)
        self.file = os.path.join(self.path, "vector_store.pkl")
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metas: list[dict] = []
        self._vecs: np.ndarray | None = None
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            with open(self.file, "rb") as f:
                d = pickle.load(f)
            self._ids, self._texts, self._metas, self._vecs = (
                d["ids"], d["texts"], d["metas"], np.array(d["vecs"]) if d["vecs"] else None
            )
            logger.info("已加载向量库：%d 条", len(self._ids))

    def _persist(self):
        with open(self.file, "wb") as f:
            pickle.dump({
                "ids": self._ids,
                "texts": self._texts,
                "metas": self._metas,
                "vecs": self._vecs.tolist() if self._vecs is not None else [],
            }, f)

    def upsert(self, embeddings: list[list[float]], texts: list[str],
               metas: list[dict] | None = None, ids: list[str] | None = None):
        """批量写入向量。"""
        metas = metas or [{} for _ in texts]
        ids = ids or [f"doc_{len(self._ids) + i}" for i in range(len(texts))]
        new_vecs = np.array(embeddings, dtype=np.float32)
        if self._vecs is None or len(self._vecs) == 0:
            self._vecs = new_vecs
        else:
            self._vecs = np.vstack([self._vecs, new_vecs])
        self._ids.extend(ids)
        self._texts.extend(texts)
        self._metas.extend(metas)
        self._persist()
        logger.info("向量库写入 %d 条，当前共 %d 条", len(texts), len(self._ids))

    def search(self, query_vec: list[float], top_k: int = 3) -> list[dict]:
        """余弦相似度 Top-K 检索。"""
        if self._vecs is None or len(self._vecs) == 0:
            return []
        q = np.array(query_vec, dtype=np.float32)
        qn = np.linalg.norm(q)
        if qn > 0:
            q = q / qn
        db = self._vecs / (np.linalg.norm(self._vecs, axis=1, keepdims=True) + 1e-9)
        sims = db @ q  # 余弦相似度
        idx = np.argsort(-sims)[:top_k]
        return [
            {"id": self._ids[i], "score": float(sims[i]),
             "text": self._texts[i], "meta": self._metas[i]}
            for i in idx
        ]
