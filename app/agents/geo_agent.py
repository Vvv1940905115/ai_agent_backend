"""
GEO 地理信息 Agent

业务链路：
1. 用户描述地理需求（如「A 店到 B 店多远」「某地址周边 5km 范围」）
2. Agent 调用 geo_geocode / geo_reverse 解析坐标
3. 调用 geo_distance / geo_bounding_box 做距离与范围计算
4. 必要时用 knowledge_search 检索区域相关政策/门店知识

工具调用链路由 LLM 自主编排（ReAct），框架负责循环执行。
"""
from app.agent.base import BaseAgent


class GeoAgent(BaseAgent):
    name = "geo_agent"
    system_prompt = (
        "你是企业地理信息助手。可调用 geo_geocode(地址转坐标)、geo_reverse(坐标转地址)、"
        "geo_distance(两点距离)、geo_bounding_box(生成范围)、knowledge_search(检索区域知识)。"
        "请先解析坐标，再做距离/范围计算，最后用清晰中文给出结论与数值。"
    )
    tool_names = [
        "geo_geocode",
        "geo_reverse",
        "geo_distance",
        "geo_bounding_box",
        "knowledge_search",
    ]
