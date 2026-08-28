"""
企业微信客户端（自建应用模式）

能力：
- 获取 access_token（企业级令牌，7200s 有效，简单缓存）
- 通过应用给成员/部门发送消息（文本）

文档：https://developer.work.weixin.qq.com/document/path/90236
touser 支持 "@all" 或具体 userid；party 用于按部门；此处以 touser 为主。
"""
import time

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("wecom")

WECOM_API = "https://qyapi.weixin.qq.com/cgi-bin"


class WeComClient:
    def __init__(self):
        self.corpid = settings.WECOM_CORPID
        self.corpsecret = settings.WECOM_CORPSECRET
        self.agent_id = settings.WECOM_AGENT_ID
        self._token = None
        self._token_expire = 0

    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expire - 60:
            return self._token
        if not self.corpid or not self.corpsecret:
            raise RuntimeError("缺少 WECOM_CORPID / WECOM_CORPSECRET")
        r = httpx.get(
            f"{WECOM_API}/gettoken",
            params={"corpid": self.corpid, "corpsecret": self.corpsecret},
            timeout=settings.REQUEST_TIMEOUT,
        )
        data = r.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"企微获取 token 失败: {data}")
        self._token = data["access_token"]
        self._token_expire = time.time() + data.get("expires_in", 7200)
        return self._token

    def send_text(self, touser: str, content: str) -> dict:
        """通过自建应用发送文本消息。"""
        token = self._ensure_token()
        r = httpx.post(
            f"{WECOM_API}/message/send",
            params={"access_token": token},
            json={
                "touser": touser,
                "msgtype": "text",
                "agentid": int(self.agent_id) if self.agent_id else 0,
                "text": {"content": content},
            },
            timeout=settings.REQUEST_TIMEOUT,
        )
        return r.json()
