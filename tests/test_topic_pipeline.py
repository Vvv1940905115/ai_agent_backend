"""
新增模块测试（pytest）

覆盖不依赖外部密钥/网络的能力，确保本地可一键验证：
- 视频生成异步链路：mock 模式提交 -> 轮询 -> 获取 video_url（无需真实 API）
- 选题批次审核：创建批次 -> approve 标记优质选题

运行：pytest -q
"""
import os

# 强制使用本地兜底 embedding + mock 视频生成，避免依赖外部密钥
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("VIDEO_GEN_PROVIDER", "mock")
os.environ.setdefault("VIDEO_GEN_MOCK_DELAY", "0")

from app.video_gen.generator import video_task_manager
from app.topic.store import topic_batch_store
from app.core.config import settings

# settings 为单例，已在其他测试导入时实例化；此处直接覆盖，确保走 mock 且零延迟
settings.VIDEO_GEN_PROVIDER = "mock"
settings.VIDEO_GEN_MOCK_DELAY = 0


def test_video_submit_and_complete():
    """提交 -> 手动驱动一次轮询 -> 应得到 succeeded 与 video_url。"""
    task_id = video_task_manager.submit(prompt="测试视频提示词", duration=5)
    video_task_manager.stop()           # 停掉后台轮询，改为确定性手动驱动
    video_task_manager._poll_once()
    rec = video_task_manager.get_status(task_id)
    assert rec["status"] == "succeeded"
    assert rec["result"]["video_url"].endswith(".mp4")


def test_topic_batch_approve():
    """人工审核：标记部分选题进入下一环节。"""
    batch = topic_batch_store.create(
        industry="教育", style="科普",
        topics=[{"id": "t1", "title": "选题A"}, {"id": "t2", "title": "选题B"}],
    )
    res = topic_batch_store.approve(batch["batch_id"], ["t1"])
    assert res["approved"] == ["t1"]
    approved = topic_batch_store.list_approved(batch["batch_id"])
    assert [t["id"] for t in approved] == ["t1"]
