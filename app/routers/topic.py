"""
选题 / 视频生成 / 全链路 接口

- POST /api/topic/generate            批量生成选题（可选写多维表格待审核）
- POST /api/topic/approve             人工审核，标记优质选题进入下一环节
- GET  /api/topic/batch/{id}          查看某批次选题与审核状态
- POST /api/video/submit              提交视频生成任务（异步），返回 task_id
- GET  /api/video/status/{id}         查询任务状态/结果
- POST /api/pipeline/topic-to-video   方案B全链路：解析参考短视频 -> 生成选题 -> 提交视频生成
"""
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import BusinessError
from app.topic.store import topic_batch_store
from app.tools.topic_tools import topic_approve, topic_generate_batch
from app.video_gen.generator import video_task_manager

router = APIRouter(prefix="/api", tags=["topic-video"])

# ---------- 选题 ----------
class TopicGenerateReq(BaseModel):
    industry: str
    style: str = ""
    count: int = 5
    use_knowledge: bool = False
    write_to_bitable: bool = False
    enhance: bool = True


class TopicApproveReq(BaseModel):
    batch_id: str
    topic_ids: list[str] | None = None
    top_n: int = 0


@router.post("/topic/generate")
def topic_generate(req: TopicGenerateReq):
    """批量生成选题（默认带质量增强：去重/打分/排序）；可选基于知识库、可选写多维表格待审核。"""
    out = topic_generate_batch(
        industry=req.industry, style=req.style, count=req.count,
        use_knowledge=req.use_knowledge, write_to_bitable=req.write_to_bitable,
        enhance=req.enhance,
    )
    return {"code": 0, **out}


@router.post("/topic/approve")
def topic_approve_api(req: TopicApproveReq):
    """人工审核：标记优质选题进入下一环节（生成视频）。可传 topic_ids 或 top_n 自动优选。"""
    out = topic_approve(batch_id=req.batch_id, topic_ids=req.topic_ids, top_n=req.top_n)
    if "error" in out:
        raise BusinessError(out["error"], code=404)
    return {"code": 0, **out}


@router.get("/topic/batch/{batch_id}")
def topic_batch(batch_id: str):
    b = topic_batch_store.get(batch_id)
    if not b:
        raise BusinessError("批次不存在", code=404)
    return {"code": 0, **b}


# ---------- 视频生成 ----------
class VideoSubmitReq(BaseModel):
    prompt: str
    duration: int = 5
    resolution: str = "1280x720"
    style: str = "cinematic"
    ref_image: str | None = None
    source_topic: str | None = None


@router.post("/video/submit")
def video_submit(req: VideoSubmitReq):
    """提交视频生成任务（异步），立即返回 task_id。"""
    task_id = video_task_manager.submit(
        prompt=req.prompt, duration=req.duration, resolution=req.resolution,
        style=req.style, ref_image=req.ref_image, source_topic=req.source_topic,
    )
    return {"code": 0, "task_id": task_id, "status": "submitted"}


@router.get("/video/status/{task_id}")
def video_status(task_id: str):
    """按 task_id 查询视频生成任务状态与结果。"""
    rec = video_task_manager.get_status(task_id)
    if "error" in rec:
        raise BusinessError(rec["error"], code=404)
    return {"code": 0, **rec}


# ---------- 全链路：选题 -> 脚本 -> 生成视频 ----------
class PipelineReq(BaseModel):
    video_url: str
    industry: str
    style: str = ""
    count: int = 3
    write_to_bitable: bool = True
    notify: bool = True
    ref_image: str | None = None


@router.post("/pipeline/topic-to-video")
def pipeline_topic_to_video(req: PipelineReq):
    """方案B 全链路：解析参考短视频 -> 生成 AI 选题 -> 提交视频生成任务。"""
    from app.agents.video_pipeline_agent import run_topic_to_video_pipeline
    return {"code": 0, **run_topic_to_video_pipeline(
        video_url=req.video_url, industry=req.industry, style=req.style, count=req.count,
        write_to_bitable=req.write_to_bitable, notify=req.notify, ref_image=req.ref_image,
    )}
