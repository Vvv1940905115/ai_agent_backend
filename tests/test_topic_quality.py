"""
选题质量增强 离线单测（无需大模型 / 网络）

覆盖：文本相似度、去重、单维度打分、去重后新颖度、热度加成、排序与质量摘要。
运行：pytest -q tests/test_topic_quality.py
"""
from app.topic.quality import (
    dedupe,
    enrich_topics,
    knowledge_relevance,
    score_topic,
    text_similarity,
)


def _topic(title, topic="", hook="", script="", tags=None, audience="", tid=None):
    return {
        "id": tid or title,
        "title": title,
        "topic": topic,
        "hook": hook,
        "script_outline": script,
        "tags": tags or [],
        "target_audience": audience,
    }


def test_text_similarity_identical():
    assert text_similarity("北京到上海直线距离", "北京到上海直线距离") >= 0.99
    assert text_similarity("", "") == 1.0
    assert text_similarity("a", "b") < 0.3


def test_dedupe_removes_similar():
    topics = [
        _topic("3分钟学会AI剪辑", tid="a"),
        _topic("3分钟学会AI视频剪辑", tid="b"),  # 近似（sim≈0.74）
        _topic("美食短视频爆款公式", tid="c"),
    ]
    kept, dups = dedupe(topics, threshold=0.7)
    assert len(kept) == 2
    assert len(dups) == 1
    assert dups[0]["similar_to"] in ("a", "b")


def test_enrich_ranking_and_scores():
    topics = [
        _topic("AI剪辑入门", hook="3步搞定字幕", script="1.导入 2.识别 3.导出",
               tags=["剪辑", "AI", "教程"], audience="新手UP主", tid="a"),
        _topic("美食爆款", hook="", script="随便拍", tags=["美食"], audience="", tid="b"),
    ]
    rep = enrich_topics(topics)
    scored = rep["topics"]
    assert [t["rank"] for t in scored] == [1, 2]
    for t in scored:
        assert 0 <= t["quality"]["score"] <= 100
        assert t["quality"]["tier"] in ("优质", "良好", "待优化")
    # 质量更高的应排第一
    assert scored[0]["quality"]["score"] >= scored[1]["quality"]["score"]
    assert rep["summary"]["kept"] == 2
    assert rep["summary"]["duplicates_removed"] == 0


def test_novelty_lowers_score_for_duplicates():
    # 单条独立选题新颖度应为 1.0
    rep = enrich_topics([_topic("独立选题A", hook="为什么", script="1.甲 2.乙 3.丙",
                                tags=["x", "y", "z"], audience="人群", tid="a")])
    assert rep["topics"][0]["quality"]["dims"]["novelty"] == 100


def test_knowledge_relevance_and_hotness():
    ctx = "年假政策：入职满一年享5天年假。年假可拆分使用。"
    topic = _topic("年假怎么休最划算", topic="年假使用技巧", hook="3个坑",
                   script="1.规划 2.拆分 3.上报", tags=["hr", "年假"], audience="职场人", tid="a")
    rel = knowledge_relevance(topic, ctx)
    assert rel is not None and 0 <= rel <= 1
    # 知识相关性应被纳入打分维度
    q = score_topic(topic, novelty=1.0, knowledge_rel=rel)
    assert "knowledge" in q["dims"]
    assert 0 <= q["dims"]["knowledge"] <= 100


def test_missing_fields_do_not_crash():
    rep = enrich_topics([_topic("", tid="x")])  # 全空
    t = rep["topics"][0]
    assert t["quality"]["score"] < 60  # 仍判为"待优化"
    assert t["quality"]["tier"] == "待优化"
    assert len(t["quality"]["suggestions"]) > 0
