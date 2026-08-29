"""知识库接口：入库与检索。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.knowledge.ingest import ingest_document, search_knowledge
from app.agent.llm import LLMOverride

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class IngestReq(BaseModel):
    text: str
    source: str = "manual"
    llm: LLMOverride | None = None   # 可选：自带 embedding 密钥（如使用云端向量时）


class SearchReq(BaseModel):
    query: str
    top_k: int = 3
    llm: LLMOverride | None = None   # 可选：自带 embedding 密钥


@router.post("/ingest")
def ingest(req: IngestReq):
    return {"code": 0, **ingest_document(req.text, source=req.source, llm_override=req.llm)}


@router.post("/search")
def search(req: SearchReq):
    return {"code": 0, "results": search_knowledge(req.query, top_k=req.top_k, llm_override=req.llm)}
