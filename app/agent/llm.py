"""
LLM 多供应商适配层

豆包（火山方舟）、DeepSeek、通义千问 的 Chat/ Embeddings 接口均兼容 OpenAI 协议，
因此统一用 openai SDK，仅切换 base_url / api_key / model 即可，便于横向扩展新模型。

多租户覆盖（每个使用者自带 API 模型）：
- LLMOverride：请求级覆盖配置（服务商 / base_url / api_key / model，可选 embedding 覆盖）
- llm_override_ctx：请求级 contextvar，使覆盖贯穿「路由 -> Agent -> 工具 -> 选题」整条链路
- resolve_llm / resolve_embedding_llm：优先用覆盖，未提供则回退到全局 settings（.env）
"""
from contextvars import ContextVar
from typing import Literal, Optional

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import BusinessError
from app.core.logging import get_logger

logger = get_logger("llm")

# ---------- 请求级 LLM 覆盖（每个使用者自带 API 模型）----------
# 在路由层按请求设置，整条调用链（含 Agent 内部工具）均读取此变量
llm_override_ctx: ContextVar[Optional["LLMOverride"]] = ContextVar("llm_override_ctx", default=None)


class LLMOverride(BaseModel):
    """每个使用者可在请求里携带的 LLM 配置覆盖。所有字段均可选。

    - provider: deepseek / doubao / qwen / custom（缺省则用全局 .env 的 LLM_PROVIDER）
    - 选 deepseek/doubao/qwen 时，base_url 与 model 可省略（自动取全局默认值）
    - 选 custom 时必须填写 base_url
    - embedding_* 为可选：仅当使用云端向量（qwen/doubao）且希望用各自密钥时填写
    """
    provider: Optional[Literal["deepseek", "doubao", "qwen", "custom"]] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None

    embedding_provider: Optional[Literal["qwen", "doubao", "local"]] = None
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: Optional[str] = None


# 各内置服务商的默认 base_url / model，供覆盖缺省时回退
_PROVIDER_DEFAULTS = {
    "deepseek": ("https://api.deepseek.com", "deepseek-chat"),
    "doubao": ("https://ark.cn-beijing.volces.com/api/v3", "ep-xxxxxxxx"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
}


def _resolve_chat_override(ov: LLMOverride) -> tuple[str, str, str]:
    """根据 LLMOverride 计算 (base_url, api_key, model)。"""
    provider = ov.provider or settings.LLM_PROVIDER
    if provider == "custom":
        if not ov.base_url:
            raise ValueError("自定义服务商需填写 base_url")
        base_url = ov.base_url
        model = ov.model or settings.LLM_MODEL
    else:
        defaults = _PROVIDER_DEFAULTS.get(provider)
        base_url = ov.base_url or (defaults[0] if defaults else settings.DEEPSEEK_BASE_URL)
        model = ov.model or (defaults[1] if defaults else settings.LLM_MODEL)
    if not ov.api_key:
        raise ValueError("缺少 API Key，请在请求中携带 llm.api_key 或配置全局密钥")
    return base_url, ov.api_key, model


def _resolve_embedding_override(ov: LLMOverride) -> tuple[str, str, str] | None:
    """根据 LLMOverride 计算云端 embedding 的 (base_url, api_key, model)，无密钥则返回 None。"""
    if not ov.embedding_api_key:
        return None
    provider = ov.embedding_provider or settings.EMBEDDING_PROVIDER
    if provider == "local":
        return None
    defaults = _PROVIDER_DEFAULTS.get(provider)
    base_url = ov.embedding_base_url or (defaults[0] if defaults else settings.QWEN_BASE_URL)
    model = ov.embedding_model or (settings.QWEN_MODEL if provider == "qwen" else settings.DOUBAO_MODEL)
    return base_url, ov.embedding_api_key, model


def resolve_llm(override: LLMOverride | None = None) -> "LLMClient":
    """返回对话模型客户端：优先用显式 override，其次用请求级 contextvar，最后回退全局 settings。"""
    ov = override or llm_override_ctx.get()
    if ov and ov.api_key:
        base_url, api_key, model = _resolve_chat_override(ov)
        return LLMClient(base_url=base_url, api_key=api_key, model=model)
    return get_active_llm()


def resolve_embedding_llm(override: LLMOverride | None = None) -> "LLMClient":
    """返回向量化客户端：优先用覆盖中的 embedding_*，其次回退全局 settings。"""
    ov = override or llm_override_ctx.get()
    if ov:
        emb = _resolve_embedding_override(ov)
        if emb:
            base_url, api_key, model = emb
            provider = ov.embedding_provider or settings.EMBEDDING_PROVIDER
            default_model = settings.QWEN_MODEL if provider == "qwen" else settings.DOUBAO_MODEL
            return LLMClient(base_url=base_url, api_key=api_key, model=model or default_model)
    return get_embedding_llm()


class LLMClient:
    """对单个供应商的轻封装，提供 chat / embed 两类能力。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        if not api_key:
            # 用 BusinessError（HTTP 400）而非 RuntimeError（HTTP 500）：
            # 缺密钥是「配置问题」而非「服务器故障」，应给用户明确可执行的提示。
            raise BusinessError(
                f"缺少 API Key，请配置对应供应商密钥（当前供应商: {settings.LLM_PROVIDER}）",
                code=400,
                detail="在 .env 中填写对应 XXX_API_KEY，或在 Web 控制台右上角「API 配置」里填写你自己的 Key。",
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
    """按 settings.LLM_PROVIDER 返回当前激活的对话模型客户端（全局默认）。"""
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
