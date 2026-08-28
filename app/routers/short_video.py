"""短视频分析接口。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.video.analyzer import analyze_content, analyze_url
from app.core.exceptions import BusinessError

router = APIRouter(prefix="/api/short-video", tags=["short-video"])


class AnalyzeUrlReq(BaseModel):
    url: str


class AnalyzeTextReq(BaseModel):
    title: str = ""
    text: str


@router.post("/analyze-url")
def analyze_url_api(req: AnalyzeUrlReq):
    """输入链接，返回抓取元数据 + 大模型分析。"""
    try:
        return {"code": 0, **analyze_url(req.url)}
    except Exception as e:
        raise BusinessError(f"抓取/分析失败: {e}", code=502)


@router.post("/analyze-text")
def analyze_text_api(req: AnalyzeTextReq):
    """直接分析文案文本。"""
    return {"code": 0, "analysis": analyze_content(text=req.text, title=req.title)}
