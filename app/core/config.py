"""
全局配置中心。

使用 pydantic-settings 读取 .env 与环境变量，集中管理所有密钥与可调参数。
所有模块通过 `from app.core.config import settings` 获取配置，避免在代码中硬编码。
"""
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 允许从项目根目录的 .env 文件加载；生产环境优先使用真实环境变量
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    # ---------- 服务 ----------
    APP_NAME: str = "ai-agent-backend"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT: float = 30.0

    # ---------- 大模型（LLM，OpenAI 兼容接口）----------
    LLM_PROVIDER: Literal["doubao", "deepseek", "qwen"] = "deepseek"
    LLM_MODEL: str = "deepseek-chat"

    DOUBAO_API_KEY: Optional[str] = None
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = "ep-xxxxxxxx"

    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v3"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    QWEN_API_KEY: Optional[str] = None
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"

    # ---------- 飞书开放平台 ----------
    FEISHU_APP_ID: Optional[str] = None
    FEISHU_APP_SECRET: Optional[str] = None
    FEISHU_BOT_WEBHOOK: Optional[str] = None

    # ---------- 企业微信 ----------
    WECOM_CORPID: Optional[str] = None
    WECOM_CORPSECRET: Optional[str] = None
    WECOM_AGENT_ID: Optional[str] = None

    # ---------- 飞书多维表格 ----------
    BITABLE_APP_TOKEN: Optional[str] = None
    BITABLE_TABLE_ID: Optional[str] = None

    # ---------- 向量知识库 ----------
    EMBEDDING_PROVIDER: Literal["qwen", "doubao", "local"] = "local"
    EMBEDDING_DIM: int = 256
    VECTOR_DB_PATH: str = "./data/vector_store"

    # ---------- 抓取策略（反爬友好）----------
    SCRAPE_RATE_LIMIT: float = 1.0
    USER_AGENT: str = "Mozilla/5.0 (compatible; AIgentBot/1.0)"

    # ---------- AI 选题 ----------
    TOPIC_DEFAULT_COUNT: int = 5
    TOPIC_DEFAULT_STYLE: str = "科普"
    TOPIC_DEDUPE_THRESHOLD: float = 0.7   # 选题去重相似度阈值（0-1，越高越严格）

    # ---------- 文生视频 / 图生视频（异步任务）----------
    # provider: mock(离线联调) | generic(自定义第三方 HTTP API)
    VIDEO_GEN_PROVIDER: Literal["mock", "generic"] = "mock"
    VIDEO_GEN_API_URL: Optional[str] = None
    VIDEO_GEN_API_KEY: Optional[str] = None
    VIDEO_GEN_POLL_INTERVAL: float = 5.0     # 后台轮询间隔(秒)
    VIDEO_GEN_TASK_TIMEOUT: float = 600.0    # 单任务超时(秒)
    VIDEO_GEN_MAX_RETRIES: int = 3           # 限流/可重试错误最大重试次数
    VIDEO_GEN_MOCK_DELAY: float = 2.0        # mock 模式模拟生成耗时(秒)

    # ---------- 企业微信通知接收人 ----------
    WECOM_NOTIFY_USER: str = "@all"          # 任务状态变更通知的企微接收人

    # ---------- 派生属性：按当前 LLM 供应商选择 base_url / key / model ----------
    @property
    def active_llm(self) -> tuple[str, str, str]:
        """返回 (base_url, api_key, model) 三元组。"""
        if self.LLM_PROVIDER == "doubao":
            return self.DOUBAO_BASE_URL, self.DOUBAO_API_KEY or "", self.DOUBAO_MODEL
        if self.LLM_PROVIDER == "qwen":
            return self.QWEN_BASE_URL, self.QWEN_API_KEY or "", self.QWEN_MODEL
        # 默认 deepseek
        return self.DEEPSEEK_BASE_URL, self.DEEPSEEK_API_KEY or "", self.DEEPSEEK_MODEL


settings = Settings()
