"""
视频生成工具：把文生视频/图生视频封装为 Agent 可调用工具。
- video_generate_submit：提交视频生成任务（异步），返回 task_id
- video_query_status：按 task_id 查询任务状态/结果
"""
from app.agent.tool import tool
from app.video_gen.generator import video_task_manager


@tool(
    name="video_generate_submit",
    description="提交文生视频/图生视频任务（异步）。返回 task_id；视频生成完成后可用 video_query_status 查询URL。支持提示词/时长/分辨率/风格/参考图。",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "视频内容提示词"},
            "duration": {"type": "integer", "description": "时长(秒)", "default": 5},
            "resolution": {"type": "string", "description": "分辨率", "default": "1280x720"},
            "style": {"type": "string", "description": "画面风格", "default": "cinematic"},
            "ref_image": {"type": "string", "description": "图生视频的参考图URL（可选）"},
        },
        "required": ["prompt"],
    },
)
def video_generate_submit(prompt: str, duration: int = 5, resolution: str = "1280x720",
                          style: str = "cinematic", ref_image: str | None = None) -> dict:
    task_id = video_task_manager.submit(prompt=prompt, duration=duration, resolution=resolution,
                                        style=style, ref_image=ref_image)
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
