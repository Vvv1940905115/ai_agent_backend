"""
短视频内容分析（调用大模型）

输入：抓取到的元数据 / 用户提供的文案文本
输出：结构化分析结果 —— 摘要、关键词标签、情感倾向、内容分类、建议

让 LLM 以 JSON 形式返回，便于下游入库/推送到多维表格。
"""
import json

from app.agent.llm import get_active_llm
from app.core.logging import get_logger

logger = get_logger("video.analyzer")

_SYSTEM = (
    "你是一名资深短视频内容运营分析师。请基于给定素材，输出严格 JSON："
    '{"summary":"一句话摘要","tags":["标签1","标签2"],"sentiment":"正面/中性/负面",'
    '"category":"内容分类","suggest":"运营建议"}。不要输出 JSON 之外的任何内容。'
)


def analyze_content(text: str, title: str = "") -> dict:
    """
    调用大模型分析文本内容（标题+正文）。返回 dict。
    """
    if not text and not title:
        return {"error": "缺少可分析文本"}

    llm = get_active_llm()
    user_msg = f"标题：{title}\n素材：{text}"
    try:
        resp = llm.chat(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
            max_tokens=800,
        )
        content = resp.choices[0].message.content or "{}"
        # 容错：截取第一个 { 到最后一个 }
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end + 1]
        return json.loads(content)
    except Exception as e:
        logger.exception("短视频分析失败")
        return {"error": str(e)}


def analyze_url(url: str) -> dict:
    """端到端：抓取 -> 提取元数据 -> 大模型分析。"""
    from app.video.fetcher import PoliteFetcher
    html = PoliteFetcher().fetch_html(url)
    meta = PoliteFetcher.extract_metadata(html, url)
    analysis = analyze_content(text=meta.get("description", ""), title=meta.get("title", ""))
    return {"metadata": meta, "analysis": analysis}
