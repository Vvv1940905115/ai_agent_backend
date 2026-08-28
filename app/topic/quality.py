"""
选题质量增强模块（TopicQualityScorer / enrich_topics）

职责：在「AI 产出选题」之后，对选题做三件事，提升进入视频生成环节的选题质量：

1. 去重（dedupe）
   - 基于文本相似度（CJK 字符 bigram Jaccard + difflib 序列比）识别近似选题，
     合并为一条，保留信息量更大者，其余标记为重复。

2. 质量打分（score_topic）
   - 多维度加权：钩子强度 / 脚本分镜完整度 / 标签丰富度 / 目标人群明确度 /
     新颖度（来自去重） / 知识相关性（来自知识库上下文）。
   - 产出 0-100 总分、等级（优质/良好/待优化）、薄弱维度改进建议。

3. 知识库热度优选（hotness_boost）
   - 当选题基于知识库生成时，对命中知识片段中的高频词（"热点"信号）做重叠度加成，
     让更贴合企业知识热点的选题排名更靠前。

设计约束：
- 纯标准库实现（re / difflib / collections），无需任何大模型或第三方依赖，离线可跑。
- 所有评分对字段缺失健壮（缺字段即按低分处理并给出建议），不会因 LLM 返回格式波动而崩溃。
- enrich_topics() 是编排入口：去重 -> 打分(含新颖度) -> 热度加成 -> 排序 -> 附质量摘要。
"""
import difflib
import re
from collections import Counter

# 钩子文案里常见"吸睛"信号：数字、疑问、感叹、悬念词
_HOOK_SIGNALS = (
    "？", "?", "！", "!", "数字", "几", "如何", "怎样", "为什么", "为何",
    "揭秘", "居然", "竟然", "难怪", "原来", "盘点", "避坑", "干货", "警告", "注意",
)
# 脚本分镜常见步骤标记
_STEP_MARKERS = ("1.", "2.", "3.", "4.", "5.", "①", "②", "③", "步骤", "分镜", "首先", "其次", "然后", "最后", "\n")


def _norm_chars(s: str) -> str:
    """归一化：转小写，仅保留中英文字母/数字与 CJK，便于相似度比较。"""
    s = (s or "").lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]", "", s)
    return s


def _bigrams(s: str) -> set:
    """字符级 bigram 集合（对中文相似度效果较好）。"""
    s = _norm_chars(s)
    if len(s) <= 1:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _rep(topic: dict) -> str:
    """用选题主要文本拼出代表性字符串，供相似度比较。"""
    return " ".join([
        str(topic.get("title", "") or ""),
        str(topic.get("topic", "") or ""),
        str(topic.get("hook", "") or ""),
        str(topic.get("script_outline", "") or ""),
    ])


def text_similarity(a: str, b: str) -> float:
    """两段文本的相似度 0-1：bigram Jaccard(0.6) + 序列比(0.4)。"""
    a, b = (a or ""), (b or "")
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ba, bb = _bigrams(a), _bigrams(b)
    union = ba | bb
    jac = len(ba & bb) / len(union) if union else 0.0
    seq = difflib.SequenceMatcher(None, _norm_chars(a), _norm_chars(b)).ratio()
    return round(0.6 * jac + 0.4 * seq, 4)


def dedupe(topics: list[dict], threshold: float = 0.7):
    """同批内近似选题去重。

    返回 (kept, duplicates)：
    - kept：保留的选题（每条带临时字段 `_max_sim`，会在 enrich 末尾清理）
    - duplicates：被合并的选题 [{id, title, similar_to, similarity}]
    合并策略：保留先出现（信息量优先由打分阶段决定，这里简单保留首条）的，其余标记重复。
    """
    kept: list[dict] = []
    duplicates: list[dict] = []
    for t in topics:
        rep = _rep(t)
        best_sim, best_kept = 0.0, None
        for k in kept:
            sim = text_similarity(rep, _rep(k))
            if sim > best_sim:
                best_sim, best_kept = sim, k
        if best_sim >= threshold:
            duplicates.append({
                "id": t.get("id"),
                "title": t.get("title", "") or t.get("topic", ""),
                "similar_to": best_kept.get("id") if best_kept else None,
                "similarity": round(best_sim, 2),
            })
        else:
            t["_max_sim"] = best_sim
            kept.append(t)
    return kept, duplicates


def knowledge_relevance(topic: dict, context: str | None) -> float | None:
    """选题文本与知识库上下文的重叠度 0-1；无上下文返回 None（打分时不计入）。"""
    if not context:
        return None
    ctx, tok = _bigrams(context), _bigrams(_rep(topic))
    union = ctx | tok
    if not union:
        return 0.0
    return round(len(ctx & tok) / len(union), 4)


def _hotness_boost(kept: list[dict], knowledge_hits: list | None) -> dict:
    """基于知识库命中片段的高频词，给贴合热点的选题最多 +10 分加成。"""
    if not knowledge_hits:
        return {t.get("id"): 0.0 for t in kept}
    freq: Counter = Counter()
    for h in knowledge_hits:
        text = h.get("text", "") if isinstance(h, dict) else str(h)
        freq.update(_bigrams(text))
    top_terms = {t for t, _ in freq.most_common(30)}
    boosts = {}
    for t in kept:
        toks = _bigrams(_rep(t))
        if not toks:
            boosts[t.get("id")] = 0.0
            continue
        overlap = len(toks & top_terms) / len(toks)
        boosts[t.get("id")] = min(overlap, 1.0) * 0.1  # 最终 *100 -> 最多 +10 分
    return boosts


# ---------- 单维度评分（每个返回 (分数0-100, 改进建议|None)）----------

def _dim_hook(topic: dict):
    hook = str(topic.get("hook", "") or "").strip()
    if not hook:
        return 0, "缺少开头钩子文案（前3秒）"
    score = 40
    if 6 <= len(hook) <= 60:
        score += 25
    if any(sig in hook for sig in _HOOK_SIGNALS):
        score += 35
    score = min(score, 100)
    sug = None if score >= 70 else "钩子偏弱，建议加入数字、反问或悬念词提升完播"
    return score, sug


def _dim_script(topic: dict):
    outline = str(topic.get("script_outline", "") or "").strip()
    if not outline:
        return 0, "缺少分镜脚本大纲"
    steps = 1 + sum(1 for m in _STEP_MARKERS[4:] if m in outline)  # 粗略步骤数
    # 也算显式编号 1. 2. 3.
    numbered = len(re.findall(r"\d+\.", outline))
    steps = max(steps, numbered)
    score = 40 + min(steps, 5) * 12  # 5 步封顶 100
    score = min(score, 100)
    sug = None if steps >= 3 else "脚本分镜建议至少 3 步（画面+口播）"
    return score, sug


def _dim_tags(topic: dict):
    tags = topic.get("tags") or []
    n = len(tags) if isinstance(tags, list) else 0
    score = min(n * 35, 100)
    sug = None if n >= 3 else "标签偏少，建议补充至 3 个以上以提升检索与推荐"
    return score, sug


def _dim_audience(topic: dict):
    aud = str(topic.get("target_audience", "") or "").strip()
    if not aud:
        return 0, "未指定目标人群"
    score = 100 if len(aud) >= 3 else 50
    sug = None if len(aud) >= 3 else "目标人群描述过短，建议更具体"
    return score, sug


def score_topic(topic: dict, novelty: float = 1.0, knowledge_rel: float | None = None,
                hot_boost: float = 0.0) -> dict:
    """对单条选题打分，返回 {score, tier, dims, suggestions}。"""
    s_hook, sug_hook = _dim_hook(topic)
    s_script, sug_script = _dim_script(topic)
    s_tags, sug_tags = _dim_tags(topic)
    s_aud, sug_aud = _dim_audience(topic)
    novelty_i = int(max(0.0, min(1.0, novelty)) * 100)
    # 知识相关性：未提供上下文时给中性 70 分，不拉低非知识库生成的选题
    knowledge_i = int((knowledge_rel if knowledge_rel is not None else 0.7) * 100)

    weighted = (
        s_hook * 0.20 + s_script * 0.25 + s_tags * 0.15 +
        s_aud * 0.15 + novelty_i * 0.15 + knowledge_i * 0.10
    )
    final = max(0, min(100, round(weighted + hot_boost * 100)))
    tier = "优质" if final >= 80 else ("良好" if final >= 60 else "待优化")
    suggestions = [s for s in (sug_hook, sug_script, sug_tags, sug_aud) if s]
    return {
        "score": final,
        "tier": tier,
        "dims": {
            "hook": s_hook, "script": s_script, "tags": s_tags,
            "audience": s_aud, "novelty": novelty_i, "knowledge": knowledge_i,
        },
        "suggestions": suggestions,
    }


def enrich_topics(topics: list[dict], knowledge_context: str | None = None,
                  knowledge_hits: list | None = None,
                  dedupe_threshold: float = 0.7) -> dict:
    """编排入口：去重 -> 打分(含新颖度) -> 热度加成 -> 排序 -> 质量摘要。

    返回 {
      "topics": [带 quality / rank / is_duplicate=False 的选题（已按分数降序）],
      "duplicates": [被合并的近似选题],
      "summary": {total, kept, duplicates_removed, avg_score, top_topic, tier_counts}
    }
    注意：会给选题写入 quality/rank/is_duplicate 字段，并清理内部 _max_sim 临时字段。
    """
    raw_total = len(topics)
    kept, duplicates = dedupe(topics, dedupe_threshold)

    # 新颖度：与同批其它选题的最大相似度越低越新颖
    nov = {t.get("id"): 1.0 - t.get("_max_sim", 0.0) for t in kept}
    rel = {t.get("id"): knowledge_relevance(t, knowledge_context) for t in kept}
    boosts = _hotness_boost(kept, knowledge_hits)

    scored = []
    for t in kept:
        tid = t.get("id")
        q = score_topic(t, novelty=nov[tid], knowledge_rel=rel[tid],
                        hot_boost=boosts.get(tid, 0.0))
        t["quality"] = q
        t["is_duplicate"] = False
        t.pop("_max_sim", None)
        scored.append(t)

    scored.sort(key=lambda x: x["quality"]["score"], reverse=True)
    for i, t in enumerate(scored, 1):
        t["rank"] = i

    for d in duplicates:
        d["is_duplicate"] = True

    scores = [t["quality"]["score"] for t in scored]
    tier_counts: dict[str, int] = {}
    for t in scored:
        tier_counts[t["quality"]["tier"]] = tier_counts.get(t["quality"]["tier"], 0) + 1
    top_topic = None
    if scored:
        top = scored[0]
        top_topic = {"id": top.get("id"), "title": top.get("title", ""), "score": top["quality"]["score"]}

    summary = {
        "total": raw_total,
        "kept": len(scored),
        "duplicates_removed": len(duplicates),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "top_topic": top_topic,
        "tier_counts": tier_counts,
    }
    return {"topics": scored, "duplicates": duplicates, "summary": summary}
