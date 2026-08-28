"""
短视频相关工具：供「短视频分析 Agent」调用。
"""
from app.agent.tool import tool
from app.video.analyzer import analyze_content, analyze_url


@tool(
    name="short_video_analyze_url",
    description="输入短视频网页链接，自动抓取公开元数据并调用大模型生成摘要/标签/情感/分类。适合抖音/快手/B站等公开分享页。",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "短视频公开分享链接"}},
        "required": ["url"],
    },
)
def short_video_analyze_url(url: str) -> dict:
    return analyze_url(url)


@tool(
    name="short_video_analyze_text",
    description="直接对给定的标题+文案文本做内容分析（无需链接），输出摘要/标签/情感/分类。",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "视频标题"},
            "text": {"type": "string", "description": "视频文案/描述文本"},
        },
        "required": ["text"],
    },
)
def short_video_analyze_text(title: str = "", text: str = "") -> dict:
    return analyze_content(text=text, title=title)
