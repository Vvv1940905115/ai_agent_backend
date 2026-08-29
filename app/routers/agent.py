"""通用 Agent 运行接口：可指定业务 Agent 类型或直接传工具名。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.geo_agent import GeoAgent
from app.agents.short_video_agent import ShortVideoAgent
from app.agents.topic_agent import TopicAgent
from app.agents.video_pipeline_agent import VideoPipelineAgent
from app.agent.base import BaseAgent
from app.agent.llm import LLMOverride
from app.core.exceptions import BusinessError

router = APIRouter(prefix="/api/agent", tags=["agent"])

# 已注册的业务 Agent 工厂
AGENTS = {
    "short_video": ShortVideoAgent,
    "geo": GeoAgent,
    "topic": TopicAgent,                 # 新增：AI 选题
    "video_pipeline": VideoPipelineAgent,  # 新增：选题->脚本->生成视频 全链路
}


class AgentRunReq(BaseModel):
    agent_type: str = "short_video"   # short_video | geo | topic | video_pipeline
    user_input: str
    conversation_id: str | None = None
    max_iterations: int = 6
    llm: LLMOverride | None = None   # 可选：每个使用者自带 API 模型


@router.post("/run")
def agent_run(req: AgentRunReq):
    """运行指定业务 Agent，返回最终文本与工具调用轨迹。"""
    agent_cls = AGENTS.get(req.agent_type)
    if not agent_cls:
        raise BusinessError(f"未知 agent_type: {req.agent_type}", code=400,
                            detail=list(AGENTS.keys()))
    agent: BaseAgent = agent_cls(max_iterations=req.max_iterations, llm_override=req.llm)
    result = agent.run(req.user_input, conversation_id=req.conversation_id)
    return {"code": 0, "agent": agent.name, **result}
