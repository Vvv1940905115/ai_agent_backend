"""
视频生成工具：把文生视频/图生视频封装为 Agent 可调用工具。
- video_generate_submit：提交视频生成任务（异步），返回 task_id
- video_query_status：按 task_id 查询任务状态/结果
"""
from app.agent.tool import tool
from app.video_gen.generator import video_task_manager


@tool(
    name="video_generate_submit",
    description="提交视频生成任务（异步），支持文生视频/图生视频/视频生视频/首尾帧生视频，支持横版16:9与竖版9:16。返回 task_id；视频生成完成后可用 video_query_status 查询URL。",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "视频内容提示词"},
            "duration": {"type": "integer", "description": "时长(秒)", "default": 5},
            "resolution": {"type": "string", "description": "分辨率", "default": "1280x720"},
            "style": {"type": "string", "description": "画面风格", "default": "cinematic"},
            "mode": {"type": "string", "description": "生成方式: text2video/image2video/video2video/frame2video", "default": "text2video"},
            "aspect_ratio": {"type": "string", "description": "比例: 16:9 或 9:16", "default": "16:9"},
            "ref_image": {"type": "string", "description": "图生视频的参考图URL（mode=image2video 时必填）"},
            "ref_video": {"type": "string", "description": "视频生视频的参考视频URL（mode=video2video 时必填）"},
            "first_frame": {"type": "string", "description": "首尾帧生视频的首帧图URL（mode=frame2video 时必填）"},
            "last_frame": {"type": "string", "description": "首尾帧生视频的尾帧图URL（mode=frame2video 时必填）"},
        },
        "required": ["prompt"],
    },
)
def video_generate_submit(prompt: str, duration: int = 5, resolution: str = "1280x720",
                          style: str = "cinematic", mode: str = "text2video",
                          aspect_ratio: str = "16:9", ref_image: str | None = None,
                          ref_video: str | None = None, first_frame: str | None = None,
                          last_frame: str | None = None) -> dict:
    task_id = video_task_manager.submit(
        prompt=prompt, duration=duration, resolution=resolution, style=style,
        mode=mode, aspect_ratio=aspect_ratio, ref_image=ref_image, ref_video=ref_video,
        first_frame=first_frame, last_frame=last_frame)
    return {"task_id": task_id, "status": "submitted",
            "tip": "异步生成中，请用 GET /api/video/status/{task_id} 查询"}


@tool(
    name="video_query_status",
    description="按 task_id 查询视频生成任务状态与结果（video_url）。状态：submitted/processing/succeeded/failed/timeout。",
    parameters={
        "type": "object",
        "properties": {"task_id": {"type": "string", "description": "提交时返回的任务ID"}},
        "required": ["task_id"],
    },
)
def video_query_status(task_id: str) -> dict:
    return video_task_manager.get_status(task_id)
