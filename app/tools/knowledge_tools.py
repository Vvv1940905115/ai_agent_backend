"""
知识库工具：供任意 Agent 作为外部知识来源调用。
- knowledge_search：检索相关知识片段（RAG）
- knowledge_ingest：把文本写入知识库
"""
from app.agent.tool import tool
from app.knowledge.ingest import ingest_document, search_knowledge


@tool(
    name="knowledge_search",
    description="从企业知识库中检索与问题最相关的文档片段，用于回答前获取事实依据（RAG）。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索问题"},
            "top_k": {"type": "integer", "description": "返回条数", "default": 3},
        },
        "required": ["query"],
    },
)
def knowledge_search(query: str, top_k: int = 3) -> dict:
    return {"results": search_knowledge(query, top_k=top_k)}


@tool(
    name="knowledge_ingest",
    description="把一段文本写入企业知识库，供后续检索。source 标记来源。",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "待入库文本"},
            "source": {"type": "string", "description": "来源标识", "default": "manual"},
        },
        "required": ["text"],
    },
)
def knowledge_ingest(text: str, source: str = "manual") -> dict:
    return ingest_document(text, source=source)
