"""
集成类工具：把飞书/企微/多维表格能力封装为 Agent 可调用工具。

这些工具让 Agent 具备「消息收发 + 数据读写」的企业闭环能力：
- 分析完短视频 -> 调用 feishu_send_message 推送给运营群
- 写入分析结果 -> bitable_append_record 落库多维表格
"""
from app.agent.tool import tool
from app.integrations.bitable import BitableClient
from app.integrations.feishu import FeishuClient
from app.integrations.wecom import WeComClient


@tool(
    name="feishu_send_message",
    description="通过飞书应用给指定会话发送文本消息。receive_id 为群/用户ID，receive_id_type 指示ID类型(chat_id/open_id/user_id)。",
    parameters={
        "type": "object",
        "properties": {
            "receive_id": {"type": "string", "description": "接收者ID"},
            "content": {"type": "string", "description": "消息文本"},
            "receive_id_type": {"type": "string", "description": "chat_id/open_id/user_id", "default": "chat_id"},
        },
        "required": ["receive_id", "content"],
    },
)
def feishu_send_message(receive_id: str, content: str, receive_id_type: str = "chat_id") -> dict:
    return FeishuClient().send_message(receive_id, content, msg_type="text", receive_id_type=receive_id_type)


@tool(
    name="feishu_bot_notify",
    description="通过飞书群机器人 Webhook 推送文本通知（最简单，无需指定接收人）。",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "通知文本"}},
        "required": ["text"],
    },
)
def feishu_bot_notify(text: str) -> dict:
    return FeishuClient().send_bot_webhook(text)


@tool(
    name="wecom_send_message",
    description="通过企业微信自建应用给成员发送文本消息。touser 为成员账号或 @all。",
    parameters={
        "type": "object",
        "properties": {
            "touser": {"type": "string", "description": "接收成员userid或@all"},
            "content": {"type": "string", "description": "消息文本"},
        },
        "required": ["touser", "content"],
    },
)
def wecom_send_message(touser: str, content: str) -> dict:
    return WeComClient().send_text(touser, content)


@tool(
    name="bitable_append_record",
    description="向飞书多维表格追加一条记录，fields 为 {列名: 值} 的字典。",
    parameters={
        "type": "object",
        "properties": {
            "fields": {"type": "object", "description": "列名->值的映射，例如 {\"标题\":\"xxx\",\"标签\":\"AI\"}"}
        },
        "required": ["fields"],
    },
)
def bitable_append_record(fields: dict) -> dict:
    return BitableClient().append_record(fields)
