"""GEO 地理信息接口（也可直接走 /api/agent/run?agent_type=geo）。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.geo_agent import GeoAgent

router = APIRouter(prefix="/api/geo", tags=["geo"])


class GeoQueryReq(BaseModel):
    query: str
    conversation_id: str | None = None


@router.post("/query")
def geo_query(req: GeoQueryReq):
    """自然语言地理查询，由 GEO Agent 自主编排工具。"""
    agent = GeoAgent()
    result = agent.run(req.query, conversation_id=req.conversation_id)
    return {"code": 0, **result}
