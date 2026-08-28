"""
视频生成任务管理器（VideoTaskManager）

封装「提交任务 -> 后台轮询 -> 获取结果」的异步闭环：
- submit()：创建任务记录，调用 VideoGenClient 提交，启动后台轮询线程
- 后台轮询线程：周期性查询第三方状态，更新任务记录
    - 成功：写入 video_url，状态 succeeded，并触发闭环（通知 + 写多维表格）
    - 失败：状态 failed，触发通知
    - 超时：超过 VIDEO_GEN_TASK_TIMEOUT 仍处理中 -> timeout
    - 限流/可重试错误：退避后继续轮询（不超过 MAX_RETRIES）
- get_status()：供接口 / Agent 按 task_id 查询
- _on_terminal()：任务状态变更时推送飞书群机器人 + 企业微信，并同步多维表格

设计：轮询线程为 daemon，随进程退出；任务状态持久化（见 task_store），重启可续轮询。
"""
import threading
import time
import uuid

from app.core.config import settings
from app.core.logging import get_logger
from app.core.task_store import AsyncTaskStore, TaskRecord, TaskStatus, video_task_store
from app.video_gen.client import VideoGenClient, VideoGenError, RateLimitError

logger = get_logger("video_gen.manager")


class VideoTaskManager:
    def __init__(self):
        self.store: AsyncTaskStore = video_task_store
        self.client = VideoGenClient()
        self._poller = None
        self._stop = threading.Event()

    # ---------- 提交任务 ----------
    def submit(self, prompt: str, duration: int = 5, resolution: str = "1280x720",
               style: str = "", ref_image: str | None = None,
               source_topic: str | None = None,
               bitable_record_id: str | None = None,
               bitable_table_id: str | None = None,
               notify: bool = True) -> str:
        task_id = "vt_" + uuid.uuid4().hex[:12]
        now = time.time()
        rec = TaskRecord(
            task_id=task_id, task_type="video_generation",
            status=TaskStatus.SUBMITTED.value, created_at=now, updated_at=now,
            payload={"prompt": prompt, "duration": duration, "resolution": resolution,
                     "style": style, "ref_image": ref_image, "source_topic": source_topic},
            bitable_record_id=bitable_record_id, bitable_table_id=bitable_table_id,
            notify=notify,
        )
        self.store.create(rec)
        logger.info("创建视频生成任务 %s", task_id)
        try:
            pid = self.client.submit(prompt, duration, resolution, style, ref_image)
            self.store.update(task_id, provider_task_id=pid, status=TaskStatus.PROCESSING.value)
            logger.info("任务 %s 已提交第三方，provider_task_id=%s", task_id, pid)
        except RateLimitError as e:
            # 提交即限流：标记 rate_limited，交由轮询线程退避后重试提交
            self.store.update(task_id, status=TaskStatus.RATE_LIMITED.value, error=str(e))
            logger.warning("任务 %s 提交限流，进入退避重试", task_id)
        except VideoGenError as e:
            self.store.update(task_id, status=TaskStatus.FAILED.value, error=str(e))
            logger.error("任务 %s 提交失败: %s", task_id, e)
        except Exception as e:
            self.store.update(task_id, status=TaskStatus.FAILED.value, error=str(e))
            logger.exception("任务 %s 提交异常", task_id)
        self.ensure_poller()  # 确保轮询线程运行（续跑持久化任务）
        return task_id

    # ---------- 查询 ----------
    def get_status(self, task_id: str) -> dict:
        rec = self.store.get(task_id)
        if not rec:
            return {"error": f"任务不存在: {task_id}"}
        return rec.to_dict()

    # ---------- 后台轮询线程 ----------
    def ensure_poller(self):
        if self._poller and self._poller.is_alive():
            return
        self._stop.clear()
        self._poller = threading.Thread(target=self._poll_loop, daemon=True)
        self._poller.start()
        logger.info("视频任务轮询线程已启动")

    def stop(self):
        self._stop.set()

    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception as e:
                logger.exception("轮询异常: %s", e)
            self._stop.wait(settings.VIDEO_GEN_POLL_INTERVAL)

    def _poll_once(self):
        for rec in self.store.list_active():
            self._process_one(rec)

    def _process_one(self, rec: TaskRecord):
        # 超时判定（ Creation 起算）
        if time.time() - rec.created_at > settings.VIDEO_GEN_TASK_TIMEOUT:
            self.store.update(rec.task_id, status=TaskStatus.TIMEOUT.value, error="任务超时未完成")
            self._on_terminal(rec.task_id, TaskStatus.TIMEOUT.value, error="任务超时未完成")
            return

        # 限流且尚未拿到 provider_task_id -> 退避后重试「提交」
        if rec.status == TaskStatus.RATE_LIMITED.value and not rec.provider_task_id:
            try:
                pid = self.client.submit(
                    prompt=rec.payload.get("prompt", ""),
                    duration=rec.payload.get("duration", 5),
                    resolution=rec.payload.get("resolution", "1280x720"),
                    style=rec.payload.get("style", ""),
                    ref_image=rec.payload.get("ref_image"),
                )
                self.store.update(rec.task_id, provider_task_id=pid,
                                  status=TaskStatus.PROCESSING.value, error=None)
                logger.info("任务 %s 退避后重提交成功，provider_task_id=%s", rec.task_id, pid)
            except RateLimitError:
                n = rec.retries + 1
                if n >= settings.VIDEO_GEN_MAX_RETRIES:
                    self.store.update(rec.task_id, status=TaskStatus.FAILED.value,
                                      error="限流重试次数耗尽")
                    self._on_terminal(rec.task_id, TaskStatus.FAILED.value, error="限流重试次数耗尽")
                else:
                    self.store.update(rec.task_id, retries=n, error=f"限流退避中({n})")
            except VideoGenError as e:
                self.store.update(rec.task_id, status=TaskStatus.FAILED.value, error=str(e))
                self._on_terminal(rec.task_id, TaskStatus.FAILED.value, error=str(e))
            return

        # 已有 provider_task_id -> 轮询查询
        try:
            info = self.client.query(rec.provider_task_id)
        except RateLimitError:
            n = rec.retries + 1
            if n >= settings.VIDEO_GEN_MAX_RETRIES:
                self.store.update(rec.task_id, status=TaskStatus.FAILED.value, error="限流重试次数耗尽")
                self._on_terminal(rec.task_id, TaskStatus.FAILED.value, error="限流重试次数耗尽")
            else:
                self.store.update(rec.task_id, status=TaskStatus.RATE_LIMITED.value,
                                  retries=n, error=f"限流退避中({n})")
            return
        except VideoGenError as e:
            self.store.update(rec.task_id, status=TaskStatus.FAILED.value, error=str(e))
            self._on_terminal(rec.task_id, TaskStatus.FAILED.value, error=str(e))
            return
        except Exception as e:
            logger.exception("查询任务 %s 异常", rec.task_id)
            self.store.update(rec.task_id, error=str(e))
            return

        status = info.get("status")
        if status == "processing":
            self.store.update(rec.task_id, status=TaskStatus.PROCESSING.value,
                              progress=info.get("progress", 0))
        elif status == "succeeded":
            self.store.update(rec.task_id, status=TaskStatus.SUCCEEDED.value, progress=100,
                              result={"video_url": info.get("video_url")})
            self._on_terminal(rec.task_id, TaskStatus.SUCCEEDED.value,
                              video_url=info.get("video_url"))
        elif status == "failed":
            self.store.update(rec.task_id, status=TaskStatus.FAILED.value, error=info.get("error"))
            self._on_terminal(rec.task_id, TaskStatus.FAILED.value, error=info.get("error"))

    # ---------- 闭环：通知 + 写多维表格 ----------
    def _on_terminal(self, task_id: str, status: str, error: str | None = None,
                     video_url: str | None = None):
        rec = self.store.get(task_id)
        if not rec or not rec.notify:
            return
        msg = self._build_notify_msg(rec, status, error, video_url)
        self._notify(msg)
        if rec.bitable_record_id:
            self._update_bitable(rec, status, error, video_url)

    def _build_notify_msg(self, rec, status, error, video_url) -> str:
        p = rec.payload
        if status == TaskStatus.SUCCEEDED.value:
            return (f"✅ 视频生成完成\n选题：{p.get('source_topic') or '-'}\n"
                    f"提示词：{(p.get('prompt') or '')[:60]}...\n视频链接：{video_url}")
        return (f"❌ 视频生成{('超时' if status == TaskStatus.TIMEOUT.value else '失败')}\n"
                f"任务：{rec.task_id}\n原因：{error or '未知'}")

    def _notify(self, msg: str):
        # 飞书群机器人（免鉴权，最稳）
        try:
            if settings.FEISHU_BOT_WEBHOOK:
                from app.integrations.feishu import FeishuClient
                FeishuClient().send_bot_webhook(msg)
        except Exception as e:
            logger.warning("飞书通知失败: %s", e)
        # 企业微信自建应用
        try:
            if settings.WECOM_CORPID:
                from app.integrations.wecom import WeComClient
                WeComClient().send_text(settings.WECOM_NOTIFY_USER or "@all", msg)
        except Exception as e:
            logger.warning("企微通知失败: %s", e)

    def _update_bitable(self, rec, status, error, video_url):
        try:
            from app.integrations.bitable import BitableClient
            fields = {"状态": status}
            if video_url:
                fields["视频链接"] = video_url
            if error:
                fields["错误信息"] = error
            BitableClient().update_record(rec.bitable_record_id, fields,
                                          table_id=rec.bitable_table_id)
        except Exception as e:
            logger.warning("多维表格更新失败: %s", e)


# 全局单例（接口层 / Agent 共用）
video_task_manager = VideoTaskManager()
