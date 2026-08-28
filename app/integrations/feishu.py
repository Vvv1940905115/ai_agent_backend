"""
飞书开放平台客户端（app 鉴权模式）

能力：
- 获取 tenant_access_token（应用级令牌，2 小时有效，内部做简单缓存）
- 发送消息（文本 / 富文本 markdown）到用户/群/部门
- 群机器人 Webhook 推送（无需 app 鉴权，最简单）

文档：https://open.feishu.cn/document/server-docs/im-v1/message
注意：receive_id_type 与 receive_id 需匹配，例如 chat_id(群)/open_id(用户)/user_id/union_id。
"""
import time

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("feishu")

FEISHU_API = "https://open.feishu.cn/open-apis"


class FeishuClient:
    def __init__(self):
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self._token = None
        self._token_expire = 0

    # ---------- 鉴权 ----------
    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expire - 60:
            return self._token
        if not self.app_id or not self.app_secret:
            raise RuntimeError("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")
        r = httpx.post(
            f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=settings.REQUEST_TIMEOUT,
        )
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书获取 token 失败: {data}")
        self._token = data["tenant_access_token"]
        self._token_expire = time.time() + data.get("expire", 7200)
        return self._token

    # ---------- 发消息 ----------
    def send_message(self, receive_id: str, content: str, msg_type: str = "text",
                     receive_id_type: str = "chat_id") -> dict:
        """
        发送消息。
        :param receive_id: 接收者 ID（群 chat_id / 用户 open_id 等）
        :param content: 文本内容（text 类型直接传纯文本；markdown 需包成 {"zh_cn":{...}}）
        :param msg_type: text | post(富文本) | image | ...
        :param receive_id_type: chat_id | open_id | user_id | union_id | email
        """
        import json
        token = self._ensure_token()
        # 文本类型 content 必须是 JSON 字符串：{"text":"..."}；其余类型由调用方传入合法 JSON 字符串
        if msg_type == "text":
            content = json.dumps({"text": content}, ensure_ascii=False)
        body = {"receive_id": receive_id, "msg_type": msg_type, "content": content}
        r = httpx.post(
            f"{FEISHU_API}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}"},
            json=body,
            timeout=settings.REQUEST_TIMEOUT,
        )
        return r.json()

    def send_bot_webhook(self, text: str) -> dict:
        """群机器人 Webhook 推送（最简单，免 app 鉴权）。"""
        if not settings.FEISHU_BOT_WEBHOOK:
            raise RuntimeError("缺少 FEISHU_BOT_WEBHOOK")
        r = httpx.post(
            settings.FEISHU_BOT_WEBHOOK,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=settings.REQUEST_TIMEOUT,
        )
        return r.json()
