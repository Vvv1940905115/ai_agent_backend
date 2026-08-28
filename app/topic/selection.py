"""
AI 选题能力（TopicSelector）

核心职责：
- 基于「知识库检索结果 + 已解析短视频数据」作为上下文，调用大模型批量产出
  短视频选题、标题、脚本大纲。
- 支持指定行业(industry)、风格(style)、数量(count)。
- 产出结构化选题列表（JSON），便于入库多维表格、人工审核、进入下一环节。
- 提供 build_video_prompt：把优质选题组装成「文生视频/图生视频」所需提示词，
  打通 选题 -> 脚本 -> 生成视频 的链路。

风格与现有 analyzer 一致：让 LLM 返回严格 JSON，做容错解析。
"""
import json
import uuid

from app.agent.llm import get_active_llm
from app.core.config import settings
from app.core.logging import get_logger
from app.topic.quality import enrich_topics

logger = get_logger("topic.selector")

_TOPIC_SYSTEM = (
    "你是一名资深短视频内容策划。基于给定【行业/风格/参考素材】，批量产出短视频选题。"
    "必须输出严格 JSON 数组，每个元素包含字段："
    '{"title":"吸睛标题","topic":"核心选题角度","script_outline":"分镜脚本大纲(3-5步，含画面与口播)",'
    '"tags":["标签1","标签2"],"hook":"开头3秒钩子文案","target_audience":"目标人群","angle":"差异点"}。'
    "只输出 JSON 数组，不要输出其它任何内容。"
)


def _extract_json_array(text: str) -> list:
    """从 LLM 输出中容错提取 JSON 数组（截取第一个 [ 到最后一个 ]）。"""
    text = (text or "").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("LLM 未返回可用的 JSON 数组")
    return json.loads(text[start:end + 1])


class TopicSelector:
    def __init__(self):
        self.llm = get_active_llm()  # 缺 key 时抛 RuntimeError（与现有 LLM 层一致）

    def _generate_raw(self, industry: str, style: str, count: int,
                      context: str, hotspots: str) -> list[dict]:
        """原始 LLM 调用：产出选题 JSON 并补充稳定 id（不做质量增强）。"""
        ctx_block = ""
        if context:
            ctx_block += f"\n【参考素材/企业知识】\n{context}\n"
        if hotspots:
            ctx_block += f"\n【近期热点】\n{hotspots}\n"

        user_msg = (
            f"行业：{industry}\n风格：{style or '不限'}\n需要数量：{count}\n"
            f"{ctx_block}"
            "请基于以上信息产出具有传播力的短视频选题。"
        )
        resp = self.llm.chat(
            messages=[
                {"role": "system", "content": _TOPIC_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.8,  # 选题需要一定发散性
            max_tokens=2000,
        )
        content = resp.choices[0].message.content or "[]"
        topics = _extract_json_array(content)
        for t in topics:
            t.setdefault("id", str(uuid.uuid4())[:8])
        logger.info("生成选题 %d 条 (行业=%s, 风格=%s)", len(topics), industry, style)
        return topics

    def generate_report(self, industry: str, style: str = "", count: int = 5,
                        use_knowledge: bool = False, context: str = "",
                        hotspots: str = "") -> dict:
        """增强入口：返回 {topics(已去重/打分/排序), duplicates, summary}。

        当 use_knowledge=True 时自动检索企业知识库作为上下文与热度来源，
        使选题质量分纳入知识相关性维度，并按知识热点优选排序。
        """
        knowledge_hits = None
        if use_knowledge:
            from app.knowledge.ingest import search_knowledge
            hits = search_knowledge(context or industry, top_k=5)
            knowledge_hits = [h.get("text", "") for h in hits]
            ctx = "\n".join(f"- {h}" for h in knowledge_hits) or "（知识库暂无相关片段）"
            context = ctx
        raw = self._generate_raw(industry, style, count, context, hotspots)
        return enrich_topics(
            raw,
            knowledge_context=context or None,
            knowledge_hits=knowledge_hits,
            dedupe_threshold=settings.TOPIC_DEDUPE_THRESHOLD,
        )

    def generate_topics(self, industry: str, style: str = "", count: int = 5,
                        context: str = "", hotspots: str = "",
                        enhance: bool = True) -> list[dict]:
        """生成选题列表（默认带质量增强：去重/打分/排名）。

        :param context: 参考素材（知识库检索片段 / 已解析短视频分析结论），提升相关性
        :param hotspots: 热点线索（可选），如热搜词
        :param enhance: False 时返回未增强的原始选题（向后兼容）
        """
        if enhance:
            return self.generate_report(industry, style, count,
                                        use_knowledge=False, context=context,
                                        hotspots=hotspots)["topics"]
        return self._generate_raw(industry, style, count, context, hotspots)

    def generate_from_knowledge(self, industry: str, style: str = "", count: int = 5,
                               query: str | None = None, enhance: bool = True) -> list[dict]:
        """从企业知识库检索相关片段作为上下文，再生成选题（RAG 驱动）。"""
        if enhance:
            return self.generate_report(industry, style, count,
                                        use_knowledge=True, context=query or "")["topics"]
        from app.knowledge.ingest import search_knowledge
        hits = search_knowledge(query or industry, top_k=5)
        context = "\n".join(f"- {h['text']}" for h in hits) or "（知识库暂无相关片段）"
        return self._generate_raw(industry, style, count, context, "")

    def build_video_prompt(self, topic: dict, ref_image: str | None = None,
                          duration: int = 5, resolution: str = "1280x720") -> dict:
        """
        把选题组装成视频生成工具所需的入参。
        返回 {prompt, duration, resolution, style, ref_image}
        - prompt：融合标题/钩子/脚本大纲，喂给文生视频模型
        - style：从选题风格或脚本推断
        """
        title = topic.get("title", "")
        hook = topic.get("hook", "")
        outline = topic.get("script_outline", "")
        prompt = (
            f"请根据以下短视频脚本生成视频。标题：{title}。开头钩子：{hook}。"
            f"分镜脚本：{outline}。画面风格：{topic.get('style', '电影感写实')}，"
            f"节奏明快，适合短视频平台传播。"
        )
        return {
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "style": topic.get("style", "cinematic"),
            "ref_image": ref_image,
        }
