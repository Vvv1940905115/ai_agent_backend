"""知识库接口：入库与检索。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.knowledge.ingest import ingest_document, search_knowledge

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class IngestReq(BaseModel):
    text: str
    source: str = "manual"


class SearchReq(BaseModel):
    query: str
    top_k: int = 3


@router.post("/ingest")
def ingest(req: IngestReq):
    return {"code": 0, **ingest_document(req.text, source=req.source)}


@router.post("/search")
def search(req: SearchReq):
    return {"code": 0, "results": search_knowledge(req.query, top_k=req.top_k)}
