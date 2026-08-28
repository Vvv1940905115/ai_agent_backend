"""
短视频分析 Agent

业务链路（任务自动化流转）：
1. 用户提供视频链接或文案
2. Agent 调用 short_video_analyze_* 工具完成内容分析
3. 调用 knowledge_search 拉取企业知识（如品牌规范/历史爆款）辅助判断
4. 将分析结果通过 feishu_bot_notify / bitable_append_record 推送并落库，形成闭环

仅声明 system_prompt 与 tool_names 即可复用通用框架，无需重写循环逻辑。
"""
from app.agent.base import BaseAgent


class ShortVideoAgent(BaseAgent):
    name = "short_video_agent"
    system_prompt = (
        "你是企业短视频分析助手。流程：先用 short_video_analyze_url/short_video_analyze_text "
        "分析内容，再用 knowledge_search 参考企业知识，最后用 feishu_bot_notify 推送摘要、"
        "用 bitable_append_record 把「标题/标签/情感/分类」写入多维表格。请逐步调用工具完成任务。"
    )
    tool_names = [
        "short_video_analyze_url",
        "short_video_analyze_text",
        "knowledge_search",
        "feishu_bot_notify",
        "bitable_append_record",
    ]
