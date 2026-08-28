"""
短视频网页数据抓取（反爬友好 / 非暴力）

设计原则：
1. 优先读取页面 Open Graph / 标准 meta，提取标题、描述、封面、作者、发布时间等元数据，
   不解析私有 API、不模拟客户端签名，避免违反平台 ToS。
2. 严格的速率限制（settings.SCRAPE_RATE_LIMIT 秒/请求）+ 随机微小抖动，降低对源站压力。
3. 设置合规 User-Agent、Accept-Language，并声明可读 Robots（如需要可扩展 robots 解析）。
4. 失败重试 2 次，超时可控，异常统一返回结构。

生产建议：对抖音/快手/视频号等，应接入其官方开放平台（如抖音开放平台、巨量引擎），
本 fetcher 作为「公开网页元数据」的通用兜底实现。
"""
import random
import time

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("video.fetcher")

# 上次请求时间戳，用于全局限速
_last_req_ts = 0.0


class PoliteFetcher:
    def __init__(self, rate_limit: float | None = None):
        self.rate_limit = rate_limit if rate_limit is not None else settings.SCRAPE_RATE_LIMIT

    def _throttle(self):
        """全局限速：确保两次请求间隔 >= rate_limit。"""
        global _last_req_ts
        now = time.time()
        wait = self.rate_limit - (now - _last_req_ts)
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.3))  # 加抖动，更像正常访问
        _last_req_ts = time.time()

    def fetch_html(self, url: str, retries: int = 2) -> str:
        """礼貌地获取网页 HTML，失败时抛异常。"""
        for attempt in range(1, retries + 1):
            self._throttle()
            try:
                r = httpx.get(
                    url,
                    headers={
                        "User-Agent": settings.USER_AGENT,
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Accept": "text/html,application/xhtml+xml",
                    },
                    follow_redirects=True,
                    timeout=settings.REQUEST_TIMEOUT,
                )
                r.raise_for_status()
                logger.info("抓取成功 %s (status=%s, bytes=%s)", url, r.status_code, len(r.text))
                return r.text
            except Exception as e:
                logger.warning("抓取失败 第%d次: %s | %s", attempt, url, e)
                if attempt == retries:
                    raise

    @staticmethod
    def extract_metadata(html: str, url: str = "") -> dict:
        """
        从 HTML 提取结构化元数据。
        覆盖 OG 协议、Twitter Card、标准 meta，字段缺失则留空。
        """
        soup = BeautifulSoup(html, "html.parser")
        def meta(prop: str) -> str:
            tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
            return tag.get("content", "").strip() if tag else ""

        return {
            "url": url,
            "title": meta("og:title") or (soup.title.string.strip() if soup.title else ""),
            "description": meta("og:description") or meta("description"),
            "author": meta("og:author") or meta("author"),
            "publish_time": meta("article:published_time") or meta("publishDate"),
            "cover": meta("og:image"),
            "video_url": meta("og:video") or meta("og:video:url"),
            "site_name": meta("og:site_name"),
            "keywords": meta("keywords"),
            "language": soup.html.get("lang", "") if soup.html else "",
        }
