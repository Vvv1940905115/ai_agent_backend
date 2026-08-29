"""
短视频分析 -> AI 选题 -> 自动生成 AI 视频 完整业务链路（方案 B）

VideoPipelineAgent：LLM 驱动的端到端编排 Agent，工具包含
- short_video_analyze_url：解析已有短视频，提取选题/脚本/画面风格
- topic_generate_batch：基于分析结果生成全新选题
- video_generate_submit / video_query_status：自动触发视频生成并跟踪
- bitable_append_record / feishu_bot_notify：结果闭环

同时提供 run_topic_to_video_pipeline() 确定性编排函数（不走 LLM，适合接口直接调用，更可控）：
解析 -> 生成选题 -> 选优 -> 组装视频 Prompt -> 提交生成 -> 写库/通知。
"""
from app.agent.base import BaseAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.topic.selection import TopicSelector
from app.video_gen.generator import video_task_manager

logger = get_logger("agent.pipeline")


class VideoPipelineAgent(BaseAgent):
    name = "video_pipeline_agent"
    system_prompt = (
        "你是「选题->脚本->生成视频」全链路编排助手。先用 short_video_analyze_url 解析参考短视频，"
        "提取其选题/脚本/画面风格；再用 topic_generate_batch 基于分析结论产出新选题；"
        "然后用 video_generate_submit 对选定选题提交视频生成任务，并用 video_query_status 跟踪；"
        "最后用 bitable_append_record 落库、feishu_bot_notify 通知。请逐步调用工具完成。"
    )
    tool_names = [
        "short_video_analyze_url",
        "topic_generate_batch",
        "video_generate_submit",
        "video_query_status",
        "bitable_append_record",
        "feishu_bot_notify",
        "knowledge_search",
    ]


def run_topic_to_video_pipeline(video_url: str, industry: str, style: str = "",
                                count: int = 3, write_to_bitable: bool = True,
                                notify: bool = True, ref_image: str | None = None) -> dict:
    """
    确定性编排（方案 B）：解析参考短视频 -> 生成 AI 选题 -> 提交视频生成任务。

    视频生成为异步：本函数返回 video_task_id，真正视频 URL 需轮询
    GET /api/video/status/{task_id} 或由后台通知（飞书/企微）获知。
    """
    from app.video.analyzer import analyze_url
    from app.topic.store import topic_batch_store
    from app.integrations.bitable import BitableClient

    # 1) 解析参考短视频
    parsed = analyze_url(video_url)
    meta = parsed.get("metadata", {})
    analysis = parsed.get("analysis", {})
    context = (
        f"参考视频标题：{meta.get('title', '')}\n"
        f"摘要：{analysis.get('summary', '')}\n"
        f"标签：{analysis.get('tags', '')}\n"
        f"内容分类：{analysis.get('category', '')} / 情感：{analysis.get('sentiment', '')}"
    )

    # 2) 基于分析结果生成新选题
    selector = TopicSelector()
    topics = selector.generate_topics(industry=industry, style=style, count=count, context=context)
    if not topics:
        return {"error": "未生成选题", "parsed": parsed}

    # 3) 选优（此处取第一条，生产可替换为评分/排序逻辑）
    chosen = topics[0]

    # 4) 组装视频生成 Prompt
    vprompt = selector.build_video_prompt(chosen, ref_image=ref_image)

    # 5) 写多维表格（选题+脚本，状态：生成中）
    bitable_record_id = None
    if write_to_bitable and settings.BITABLE_APP_TOKEN and settings.BITABLE_TABLE_ID:
        try:
            resp = BitableClient().append_record({
                "行业": industry, "风格": style,
                "标题": chosen.get("title", ""),
                "选题": chosen.get("topic", ""),
                "脚本大纲": chosen.get("script_outline", ""),
                "标签": ",".join(chosen.get("tags", [])),
                "状态": "生成中",
            })
            bitable_record_id = resp.get("data", {}).get("record", {}).get("record_id")
        except Exception as e:
            logger.warning("选题写多维表格失败: %s", e)

    # 6) 提交视频生成（异步）
    task_id = video_task_manager.submit(
        prompt=vprompt["prompt"], duration=vprompt.get("duration", 5),
        resolution=vprompt.get("resolution", "1280x720"), style=vprompt.get("style", ""),
        ref_image=vprompt.get("ref_image"),
        source_topic=chosen.get("title", ""),
        bitable_record_id=bitable_record_id, notify=notify,
    )

    # 7) 记录选题批次（供人工审核/进入下一环节）
    topic_batch_store.create(industry=industry, style=style, topics=topics)

    return {
        "parsed_video": parsed,
        "generated_topics": topics,
        "chosen_topic": chosen,
        "video_prompt": vprompt,
        "video_task_id": task_id,
        "bitable_record_id": bitable_record_id,
        "tip": "视频为异步生成，请用 GET /api/video/status/{task_id} 查询，或等待飞书/企微通知。",
    }
