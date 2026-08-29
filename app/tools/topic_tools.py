"""
选题工具：把 AI 选题能力封装为 Agent 可调用工具。
- topic_generate_batch：批量生成选题+脚本大纲（可写入多维表格待审核）
- topic_approve：人工审核，标记优质选题进入下一环节（生成视频）
"""
from app.agent.tool import tool
from app.core.config import settings
from app.core.logging import get_logger
from app.topic.selection import TopicSelector
from app.topic.store import topic_batch_store

from app.integrations.bitable import BitableClient

logger = get_logger("tools.topic")


@tool(
    name="topic_generate_batch",
    description="按行业/风格/数量批量生成短视频选题与脚本大纲，并自动做质量增强（去重/多维度打分/按知识库热度优选排序）；可基于知识库检索结果作为参考素材提升相关性。返回选题列表、质量摘要与批次ID。",
    parameters={
        "type": "object",
        "properties": {
            "industry": {"type": "string", "description": "行业，如 美妆/教育/3C"},
            "style": {"type": "string", "description": "风格，如 搞笑/科普/剧情", "default": ""},
            "count": {"type": "integer", "description": "生成数量", "default": 5},
            "use_knowledge": {"type": "boolean", "description": "是否从知识库检索参考素材并纳入质量分", "default": False},
            "write_to_bitable": {"type": "boolean", "description": "是否写入多维表格待审核", "default": False},
            "enhance": {"type": "boolean", "description": "是否启用质量增强（去重/打分/排序）", "default": True},
        },
        "required": ["industry"],
    },
)
def topic_generate_batch(industry: str, style: str = "", count: int = 5,
                         use_knowledge: bool = False, write_to_bitable: bool = False,
                         enhance: bool = True) -> dict:
    selector = TopicSelector()
    if enhance:
        rep = selector.generate_report(industry, style, count, use_knowledge=use_knowledge)
        topics = rep["topics"]
        duplicates = rep["duplicates"]
        quality_summary = rep["summary"]
    else:
        topics = (selector.generate_from_knowledge(industry, style, count)
                  if use_knowledge else selector.generate_topics(industry, style, count))
        duplicates, quality_summary = [], {
            "total": len(topics), "kept": len(topics), "duplicates_removed": 0,
            "avg_score": None, "top_topic": None, "tier_counts": {},
        }

    record_ids = []
    if write_to_bitable and settings.BITABLE_APP_TOKEN and settings.BITABLE_TABLE_ID:
        client = BitableClient()
        for t in topics:
            try:
                fields = {
                    "行业": industry, "风格": style,
                    "标题": t.get("title", ""), "选题": t.get("topic", ""),
                    "脚本大纲": t.get("script_outline", ""),
                    "标签": ",".join(t.get("tags", [])),
                    "状态": "待审核",
                }
                # 质量增强字段（多维表格需先建对应列，缺失则忽略该列）
                if t.get("quality"):
                    fields["质量分"] = t["quality"]["score"]
                    fields["排名"] = t.get("rank")
                    fields["层级"] = t["quality"]["tier"]
                resp = client.append_record(fields)
                record_ids.append(resp.get("data", {}).get("record", {}).get("record_id"))
            except Exception as e:
                record_ids.append(None)
                logger.warning("选题写表失败: %s", e)

    batch = topic_batch_store.create(industry=industry, style=style, topics=topics,
                                      record_ids=record_ids)
    return {
        "batch_id": batch["batch_id"],
        "generated": quality_summary["total"],
        "count": len(topics),
        "topics": topics,
        "duplicates": duplicates,
        "quality_summary": quality_summary,
    }


@tool(
    name="topic_approve",
    description="人工审核：传入批次ID与选中的选题ID列表（或 top_n 自动优选前 N 名），标记优质选题进入下一环节（生成视频）。",
    parameters={
        "type": "object",
        "properties": {
            "batch_id": {"type": "string", "description": "选题批次ID（topic_generate_batch 返回）"},
            "topic_ids": {"type": "array", "description": "通过的选题ID列表", "items": {"type": "string"}},
            "top_n": {"type": "integer", "description": "自动优选排名前 N 的选题（与 topic_ids 合并去重）", "default": 0},
        },
        "required": ["batch_id"],
    },
)
def topic_approve(batch_id: str, topic_ids: list | None = None, top_n: int = 0) -> dict:
    batch = topic_batch_store.get(batch_id)
    if not batch:
        return {"error": f"批次不存在: {batch_id}"}
    ids = list(topic_ids or [])
    if top_n and top_n > 0:
        ranked = sorted(batch["topics"], key=lambda t: t.get("rank") or 999)
        ids += [t.get("id") for t in ranked[:top_n]]
    # 去重保序
    seen, uniq = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    batch = topic_batch_store.approve(batch_id, uniq)
    # 同步更新多维表格记录状态为 已审核通过
    if batch.get("record_ids"):
        try:
            client = BitableClient()
            id_map = {t.get("id"): rid for t, rid in zip(batch["topics"], batch["record_ids"])}
            for tid in batch["approved"]:
                rid = id_map.get(tid)
                if rid:
                    client.update_record(rid, {"状态": "已审核通过"})
        except Exception as e:
            logger.warning("审核更新多维表格失败: %s", e)
    return {"batch_id": batch_id, "approved": batch["approved"],
            "approved_topics": [t for t in batch["topics"] if t.get("id") in batch["approved"]]}
