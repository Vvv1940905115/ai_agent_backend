"""
文本向量化（Embeddings）

支持三种来源，按 settings.EMBEDDING_PROVIDER 切换：
- qwen   : 通义千问 text-embedding-v3（DashScope，OpenAI 兼容）
- doubao : 火山方舟 doubao-embedding
- local  : 本地哈希兜底（无需网络/密钥，确定性，仅用于联调演示，
           语义质量远低于真实模型，生产请务必切换到 qwen/doubao）

统一接口：embed(texts: list[str]) -> list[list[float]]
"""
import hashlib
import math

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("knowledge.embed")


class LocalEmbedding:
    """
    本地兜底 embedding：哈希词袋法。
    把文本切词（按字符 n-gram）映射到固定维度向量并 L2 归一化。
    特点：确定性、零依赖、可离线；但不是语义向量，仅用于跑通链路。
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            tokens = self._ngrams(t)
            if not tokens:
                out.append(vec.tolist())
                continue
            for tk in tokens:
                h = int(hashlib.md5(tk.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                vec[idx] += 1.0
            # L2 归一化，便于余弦相似度
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            out.append(vec.tolist())
        return out

    @staticmethod
    def _ngrams(text: str, n: int = 3) -> list[str]:
        text = text.lower().strip()
        if len(text) <= n:
            return [text]
        return [text[i:i + n] for i in range(len(text) - n + 1)]


def get_embedder(override=None):
    """根据配置返回 embedder（真实模型走 OpenAI 兼容，本地走 LocalEmbedding）。

    override：可选 LLMOverride，用于每个使用者自带 embedding 密钥（优先于全局 .env）。
    """
    from app.agent.llm import llm_override_ctx, resolve_embedding_llm
    ov = override or llm_override_ctx.get()
    # 云端 embedding 是否由覆盖提供密钥
    if ov and ov.embedding_api_key:
        provider = ov.embedding_provider or settings.EMBEDDING_PROVIDER
    else:
        provider = settings.EMBEDDING_PROVIDER

    if provider == "local":
        logger.warning("使用本地兜底 embedding（非语义向量），生产请配置 qwen/doubao")
        return LocalEmbedding(dim=settings.EMBEDDING_DIM)

    client = resolve_embedding_llm(override)
    model = (ov.embedding_model if (ov and ov.embedding_model) else
             (settings.QWEN_MODEL if provider == "qwen" else settings.DOUBAO_MODEL))

    class _Remote:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return client.embed(texts, model=model)

    return _Remote()
