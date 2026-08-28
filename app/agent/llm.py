"""
LLM 多供应商适配层

豆包（火山方舟）、DeepSeek、通义千问 的 Chat/ Embeddings 接口均兼容 OpenAI 协议，
因此统一用 openai SDK，仅切换 base_url / api_key / model 即可，便于横向扩展新模型。
"""
from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("llm")


class LLMClient:
    """对单个供应商的轻封装，提供 chat / embed 两类能力。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        if not api_key:
            raise RuntimeError(
                f"缺少 API Key，请配置对应供应商密钥（当前供应商: {settings.LLM_PROVIDER}）"
            )
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             temperature: float = 0.3, max_tokens: int = 1500) -> object:
        """
        一次对话补全。支持 tools（函数调用）。
        返回 openai 的 ChatCompletion 对象，由调用方解析 tool_calls。
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """批量文本向量化（兼容 embeddings 接口）。"""
        resp = self.client.embeddings.create(model=model or self.model, input=texts)
        return [d.embedding for d in resp.data]


def get_active_llm() -> LLMClient:
    """按 settings.LLM_PROVIDER 返回当前激活的对话模型客户端。"""
    base_url, api_key, model = settings.active_llm
    return LLMClient(base_url=base_url, api_key=api_key, model=model)


def get_embedding_llm(provider: str | None = None, model: str | None = None) -> LLMClient:
    """返回用于向量化的客户端（embeddings 供应商可独立于对话模型配置）。"""
    provider = provider or settings.EMBEDDING_PROVIDER
    if provider == "qwen":
        return LLMClient(settings.QWEN_BASE_URL, settings.QWEN_API_KEY or "", model or "text-embedding-v3")
    if provider == "doubao":
        return LLMClient(settings.DOUBAO_BASE_URL, settings.DOUBAO_API_KEY or "", model or "doubao-embedding")
    raise RuntimeError("本地兜底 embedding 不需要 LLM 客户端；请直接使用 LocalEmbedding。")
