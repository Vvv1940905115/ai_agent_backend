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
from app.agent.llm import LLMOverride, llm_override_ctx

router = APIRouter(prefix="/api", tags=["topic-video"])

# ---------- 选题 ----------
class TopicGenerateReq(BaseModel):
    industry: str
    style: str = ""
    count: int = 5
    use_knowledge: bool = False
    write_to_bitable: bool = False
    enhance: bool = True
    llm: LLMOverride | None = None   # 可选：每个使用者自带 API 模型（provider/base_url/api_key/model）


class TopicApproveReq(BaseModel):
    batch_id: str
    topic_ids: list[str] | None = None
    top_n: int = 0


@router.post("/topic/generate")
def topic_generate(req: TopicGenerateReq):
    """批量生成选题（默认带质量增强：去重/打分/排序）；可选基于知识库、可选写多维表格待审核。"""
    token = llm_override_ctx.set(req.llm) if req.llm is not None else None
    try:
        out = topic_generate_batch(
            industry=req.industry, style=req.style, count=req.count,
            use_knowledge=req.use_knowledge, write_to_bitable=req.write_to_bitable,
            enhance=req.enhance,
        )
        return {"code": 0, **out}
    finally:
        if token is not None:
            llm_override_ctx.reset(token)


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
# 可选模型规格：前端下拉与后端校验共用同一份事实来源
VIDEO_MODELS = [
    {"id": "seedance_2_0_mini", "name": "Seedance 2.0 Mini", "max_duration": 15,
     "resolutions": ["1280x720", "1920x1080"]},
    {"id": "seedance_2_0_fast", "name": "Seedance 2.0 Fast", "max_duration": 15,
     "resolutions": ["1280x720", "1920x1080"]},
    {"id": "seedance_2_0_std", "name": "Seedance 2.0 标准版", "max_duration": 15,
     "resolutions": ["1280x720", "1920x1080"]},
    {"id": "seedance_2_5", "name": "Seedance 2.5", "max_duration": 30,
     "resolutions": ["1280x720", "1920x1080", "2K"]},
    {"id": "minmax_h3", "name": "Minmax H3", "max_duration": 16,
     "resolutions": ["1280x720", "1920x1080"]},
]
_MODEL_MAP = {m["id"]: m for m in VIDEO_MODELS}

# 支持的比例（横版 / 竖版）
ASPECT_RATIOS = ["16:9", "9:16"]

# 支持的生成方式：文生视频 / 图生视频 / 视频生视频 / 首尾帧生视频
GEN_MODES = [
    {"id": "text2video", "name": "文生视频（仅文字）"},
    {"id": "image2video", "name": "图生视频（参考图）"},
    {"id": "video2video", "name": "视频生视频（参考视频）"},
    {"id": "frame2video", "name": "首尾帧生视频（首帧+尾帧）"},
]
_MODE_SET = {m["id"] for m in GEN_MODES}


@router.get("/video/models")
def video_models():
    """返回可选视频生成模型、支持的比例、生成方式（供前端动态渲染下拉）。"""
    return {"code": 0, "models": VIDEO_MODELS,
            "aspect_ratios": ASPECT_RATIOS, "modes": GEN_MODES}


class VideoApiConfig(BaseModel):
    """每个任务可覆盖的视频生成 API 配置；不填则走服务端 .env 默认配置。"""
    provider: str = "mock"   # mock | generic
    api_url: str | None = None
    api_key: str | None = None


class VideoSubmitReq(BaseModel):
    prompt: str
    duration: int = 5
    resolution: str = "1280x720"
    style: str = "cinematic"
    model: str | None = None
    mode: str = "text2video"            # 生成方式：text2video / image2video / video2video / frame2video
    aspect_ratio: str = "16:9"          # 比例：16:9 横版 / 9:16 竖版
    ref_image: str | None = None        # 图生视频：参考图 URL / dataURL
    ref_video: str | None = None        # 视频生视频：参考视频 URL / dataURL
    first_frame: str | None = None      # 首尾帧生视频：首帧图
    last_frame: str | None = None       # 首尾帧生视频：尾帧图
    source_topic: str | None = None
    api_config: VideoApiConfig | None = None   # 可选：前端自定义 API 入口


@router.post("/video/submit")
def video_submit(req: VideoSubmitReq):
    """提交视频生成任务（异步），立即返回 task_id。"""
    if req.mode not in _MODE_SET:
        raise BusinessError(
            f"不支持的生成方式: {req.mode}（可选：{', '.join(sorted(_MODE_SET))}）", code=400)
    if req.aspect_ratio not in ASPECT_RATIOS:
        raise BusinessError(
            f"不支持的比例: {req.aspect_ratio}（可选：{', '.join(ASPECT_RATIOS)}）", code=400)
    if req.model:
        spec = _MODEL_MAP.get(req.model)
        if not spec:
            raise BusinessError(f"不支持的模型: {req.model}", code=400)
        if req.duration > spec["max_duration"]:
            raise BusinessError(
                f"模型 {spec['name']} 最长 {spec['max_duration']} 秒，当前已选 {req.duration} 秒", code=400)
        if req.resolution not in spec["resolutions"]:
            raise BusinessError(
                f"模型 {spec['name']} 不支持分辨率 {req.resolution}（可选：{', '.join(spec['resolutions'])}）", code=400)
    # 各生成方式的必填参考项校验
    if req.mode == "image2video" and not req.ref_image:
        raise BusinessError("图生视频必须提供参考图（ref_image）", code=400)
    if req.mode == "video2video" and not req.ref_video:
        raise BusinessError("视频生视频必须提供参考视频（ref_video）", code=400)
    if req.mode == "frame2video":
        if not req.first_frame:
            raise BusinessError("首尾帧生视频必须提供首帧图（first_frame）", code=400)
        if not req.last_frame:
            raise BusinessError("首尾帧生视频必须提供尾帧图（last_frame）", code=400)
    if req.api_config and req.api_config.provider != "mock":
        if not req.api_config.api_url or not req.api_config.api_key:
            raise BusinessError("generic 模式必须填写 API URL 与 API Key", code=400)
    task_id = video_task_manager.submit(
        prompt=req.prompt, duration=req.duration, resolution=req.resolution,
        style=req.style, ref_image=req.ref_image, source_topic=req.source_topic,
        model=req.model, mode=req.mode, aspect_ratio=req.aspect_ratio,
        ref_video=req.ref_video, first_frame=req.first_frame, last_frame=req.last_frame,
        api_config=req.api_config.model_dump() if req.api_config else None,
    )
    return {"code": 0, "task_id": task_id, "status": "submitted",
            "model": req.model, "mode": req.mode, "aspect_ratio": req.aspect_ratio}


@router.post("/video/test-config")
def video_test_config(cfg: VideoApiConfig):
    """测试视频生成 API 配置是否可连通（仅校验 URL/KEY 是否填写，不实际扣费提交）。"""
    if cfg.provider == "mock":
        return {"code": 0, "ok": True, "message": "mock 模式无需外部 API"}
    if not cfg.api_url or not cfg.api_key:
        raise BusinessError("generic 模式必须填写 API URL 与 API Key", code=400)
    from app.video_gen.client import VideoGenClient
    client = VideoGenClient()
    try:
        client._generic_submit(
            prompt="ping", duration=1, resolution="1280x720",
            style="cinematic", ref_image=None, model="ping",
            mode="text2video", aspect_ratio="16:9",
            ref_video=None, first_frame=None, last_frame=None,
            api_config=cfg.model_dump(),
        )
        return {"code": 0, "ok": True, "message": "连接成功"}
    except Exception as e:
        msg = str(e)
        if "提交失败 HTTP" in msg:
            return {"code": 0, "ok": True, "message": f"接口可达（鉴权响应：{msg[:120]}）"}
        return {"code": 0, "ok": False, "message": msg[:200]}


@router.get("/video/status/{task_id}")
def video_status(task_id: str):
    """按 task_id 查询视频生成任务状态与结果。"""
    rec = video_task_manager.get_status(task_id)
    if rec.get("error"):
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
    llm: LLMOverride | None = None   # 可选：每个使用者自带 API 模型


@router.post("/pipeline/topic-to-video")
def pipeline_topic_to_video(req: PipelineReq):
    """方案B 全链路：解析参考短视频 -> 生成 AI 选题 -> 提交视频生成任务。"""
    from app.agents.video_pipeline_agent import run_topic_to_video_pipeline
    token = llm_override_ctx.set(req.llm) if req.llm is not None else None
    try:
        return {"code": 0, **run_topic_to_video_pipeline(
            video_url=req.video_url, industry=req.industry, style=req.style, count=req.count,
            write_to_bitable=req.write_to_bitable, notify=req.notify, ref_image=req.ref_image,
        )}
    finally:
        if token is not None:
            llm_override_ctx.reset(token)
