"""
第三方文生视频 / 图生视频 API 适配层（VideoGenClient）

能力：
- submit()：提交生成任务（文生视频 text2video / 图生视频 img2video），返回第三方 task_id
- query()：按第三方 task_id 查询状态，返回 {status, progress, video_url, error}

provider 模式：
- mock  （默认）：离线联调。提交即生成模拟 task_id，查询在 MOCK_DELAY 后返回成功与占位视频 URL，
          无需任何外部密钥，用于跑通「提交->轮询->获取结果」全链路。
- generic：对接你自己的第三方 HTTP API。请求/响应字段已留出最常见映射，按实际 API 调整即可。

异常处理：
- RateLimitError(retryable=True)：HTTP 429 / 限流，由上层做退避重试
- VideoGenError：其它失败（retryable 由调用方决定）
"""
import time

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("video_gen.client")

# mock 任务存储：provider_task_id -> 提交时间戳
_MOCK_JOBS: dict[str, float] = {}


class VideoGenError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class RateLimitError(VideoGenError):
    def __init__(self, message: str = "视频生成 API 触发限流(429)"):
        super().__init__(message, retryable=True)


class VideoGenClient:
    def __init__(self):
        self.provider = settings.VIDEO_GEN_PROVIDER
        self.api_url = settings.VIDEO_GEN_API_URL
        self.api_key = settings.VIDEO_GEN_API_KEY

    # ---------- 提交任务 ----------
    def submit(self, prompt: str, duration: int = 5, resolution: str = "1280x720",
               style: str = "", ref_image: str | None = None,
               model: str | None = None) -> str:
        """返回第三方 task_id（provider 内部任务标识）。"""
        if self.provider == "mock":
            return self._mock_submit(prompt)
        return self._generic_submit(prompt, duration, resolution, style, ref_image, model)

    # ---------- 查询任务 ----------
    def query(self, provider_task_id: str) -> dict:
        """返回 {status, progress, video_url, error}。status ∈ processing|succeeded|failed"""
        if self.provider == "mock":
            return self._mock_query(provider_task_id)
        return self._generic_query(provider_task_id)

    # ===================== mock 实现（离线联调）=====================
    def _mock_submit(self, prompt: str) -> str:
        pid = f"mock_{abs(hash(prompt)) % 10 ** 9}_{int(time.time()) % 10 ** 5}"
        _MOCK_JOBS[pid] = time.time()
        logger.info("[mock] 提交视频生成任务 %s", pid)
        return pid

    def _mock_query(self, provider_task_id: str) -> dict:
        created = _MOCK_JOBS.get(provider_task_id)
        if created is None:
            return {"status": "failed", "progress": 0, "video_url": None,
                    "error": "mock task 不存在"}
        if time.time() - created < settings.VIDEO_GEN_MOCK_DELAY:
            return {"status": "processing", "progress": 50, "video_url": None, "error": None}
        return {"status": "succeeded", "progress": 100,
                "video_url": f"https://example.com/mock-videos/{provider_task_id}.mp4",
                "error": None}

    # ===================== generic 实现（对接真实 API）=====================
    @retry(retry=retry_if_exception_type(RateLimitError),
           stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10),
           reraise=True)
    def _generic_submit(self, prompt, duration, resolution, style, ref_image, model) -> str:
        if not self.api_url or not self.api_key:
            raise VideoGenError("缺少 VIDEO_GEN_API_URL / VIDEO_GEN_API_KEY")
        body = {
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "style": style,
        }
        if model:
            body["model"] = model
        if ref_image:
            body["image"] = ref_image  # 图生视频：参考图
        try:
            r = httpx.post(
                f"{self.api_url.rstrip('/')}/v1/video/generations",
                headers={"Authorization": f"Bearer {self.api_key}",
                          "Content-Type": "application/json"},
                json=body,
                timeout=settings.REQUEST_TIMEOUT,
            )
        except Exception as e:
            raise VideoGenError(f"提交网络错误: {e}", retryable=True) from e
        if r.status_code == 429:
            raise RateLimitError()
        if r.status_code >= 400:
            raise VideoGenError(f"提交失败 HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        # 兼容不同字段命名
        pid = data.get("id") or data.get("task_id") or data.get("taskId")
        if not pid:
            raise VideoGenError(f"提交响应缺少 task id: {data}")
        return pid

    def _generic_query(self, provider_task_id: str) -> dict:
        try:
            r = httpx.get(
                f"{self.api_url.rstrip('/')}/v1/video/generations/{provider_task_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=settings.REQUEST_TIMEOUT,
            )
        except Exception as e:
            raise VideoGenError(f"查询网络错误: {e}", retryable=True) from e
        if r.status_code == 429:
            raise RateLimitError()
        if r.status_code >= 400:
            raise VideoGenError(f"查询失败 HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        # 兼容多种状态命名
        raw = (data.get("status") or data.get("state") or "").lower()
        if raw in ("succeeded", "success", "completed", "done"):
            status = "succeeded"
        elif raw in ("failed", "error"):
            status = "failed"
        else:
            status = "processing"
        return {
            "status": status,
            "progress": data.get("progress", 0),
            "video_url": data.get("video_url") or data.get("url") or data.get("output"),
            "error": data.get("error"),
        }
