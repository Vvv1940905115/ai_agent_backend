"""
AI 选题 Agent

链路：
1. 用户给定行业/风格/数量（或从知识库/已解析短视频拉上下文）
2. 调用 topic_generate_batch 批量产出选题+脚本大纲
3. 调用 knowledge_search 参考企业知识；调用 bitable_append_record 把选题写入多维表格待审核
4. 调用 video_generate_submit 把优质选题转成视频生成任务（异步）
5. 用 video_query_status 跟踪，必要时 feishu_bot_notify 通知运营
"""
from app.agent.base import BaseAgent


class TopicAgent(BaseAgent):
    name = "topic_agent"
    system_prompt = (
        "你是企业 AI 选题助手。流程：用 topic_generate_batch 按行业/风格批量产出短视频选题与脚本大纲"
        "（默认已做质量增强：去重/多维度打分/按知识库热度排序，返回带 quality 与 rank 的选题）；"
        "用 knowledge_search 参考企业知识；用 bitable_append_record 把选题写入多维表格待人工审核；"
        "用 topic_approve 的 top_n 参数自动优选排名前 N 的优质选题进入下一环节；"
        "对确定的选题用 video_generate_submit 提交视频生成（异步任务），再用 video_query_status 跟踪进度，"
        "最后用 feishu_bot_notify 推送进展。请逐步调用工具完成任务。"
    )
    tool_names = [
        "topic_generate_batch",
        "knowledge_search",
        "bitable_append_record",
        "video_generate_submit",
        "video_query_status",
        "feishu_bot_notify",
    ]
