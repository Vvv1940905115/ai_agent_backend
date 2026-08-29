"""
文档入库与检索封装

- chunk_text：简单按长度切分（生产可换为按语义/句子切分）
- ingest_document：切分 -> 向量化 -> 入库
- search_knowledge：向量化查询 -> 检索 -> 返回上下文
"""
import re

from app.knowledge.embeddings import get_embedder
from app.knowledge.vector_store import VectorStore
from app.core.logging import get_logger
from app.agent.llm import LLMOverride

logger = get_logger("knowledge.ingest")

_store = VectorStore()


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """按字符窗口切分，带 overlap 避免截断语义。"""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - overlap
    return chunks


def ingest_document(text: str, source: str = "manual", meta: dict | None = None,
                   llm_override: LLMOverride | None = None) -> dict:
    """把一篇文档切分、向量化并写入知识库。"""
    chunks = chunk_text(text)
    if not chunks:
        return {"error": "空文档"}
    embedder = get_embedder(llm_override)
    embs = embedder.embed(chunks)
    metas = [{"source": source, **(meta or {}), "chunk": i} for i in range(len(chunks))]
    _store.upsert(embs, chunks, metas)
    return {"ingested": len(chunks), "source": source}


def search_knowledge(query: str, top_k: int = 3,
                     llm_override: LLMOverride | None = None) -> list[dict]:
    """用自然语言查询知识库，返回最相关片段。"""
    embedder = get_embedder(llm_override)
    q_vec = embedder.embed([query])[0]
    return _store.search(q_vec, top_k=top_k)

