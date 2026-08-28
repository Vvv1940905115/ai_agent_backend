"""
飞书多维表格（Bitable）客户端

能力：
- 读取记录（list records，支持翻页）
- 追加记录（create records）
- 更新/删除（示例给出更新，删除可类比）

多维表格 = 应用(app_token) + 数据表(table_id)。获取方式见飞书开发者后台。
文档：https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview
"""
import httpx

from app.core.config import settings
from app.core.logging import get_logger

from app.integrations.feishu import FeishuClient

logger = get_logger("bitable")


class BitableClient:
    def __init__(self):
        self.fs = FeishuClient()  # 复用飞书鉴权

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.fs._ensure_token()}"}

    def list_records(self, app_token: str | None = None, table_id: str | None = None,
                     page_size: int = 50) -> list[dict]:
        """读取某表全部记录（自动翻页到末页）。"""
        app_token = app_token or settings.BITABLE_APP_TOKEN
        table_id = table_id or settings.BITABLE_TABLE_ID
        if not app_token or not table_id:
            raise RuntimeError("缺少 BITABLE_APP_TOKEN / BITABLE_TABLE_ID")
        out = []
        page_token = None
        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            r = httpx.get(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                params=params,
                headers=self._headers(),
                timeout=settings.REQUEST_TIMEOUT,
            )
            data = r.json()
            if data.get("code") != 0:
                raise RuntimeError(f"多维表格读取失败: {data}")
            out.extend(data["data"]["items"])
            page_token = data["data"].get("page_token")
            if not page_token or not data["data"].get("has_more"):
                break
        return out

    def append_record(self, fields: dict, app_token: str | None = None,
                      table_id: str | None = None) -> dict:
        """追加一条记录。fields 为 {列名: 值}。"""
        app_token = app_token or settings.BITABLE_APP_TOKEN
        table_id = table_id or settings.BITABLE_TABLE_ID
        if not app_token or not table_id:
            raise RuntimeError("缺少 BITABLE_APP_TOKEN / BITABLE_TABLE_ID")
        r = httpx.post(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            headers=self._headers(),
            json={"fields": fields},
            timeout=settings.REQUEST_TIMEOUT,
        )
        return r.json()

    def update_record(self, record_id: str, fields: dict, app_token: str | None = None,
                      table_id: str | None = None) -> dict:
        """更新一条记录（如把选题状态从「生成中」改为「已完成」并写入视频链接）。"""
        app_token = app_token or settings.BITABLE_APP_TOKEN
        table_id = table_id or settings.BITABLE_TABLE_ID
        if not app_token or not table_id:
            raise RuntimeError("缺少 BITABLE_APP_TOKEN / BITABLE_TABLE_ID")
        r = httpx.put(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            headers=self._headers(),
            json={"fields": fields},
            timeout=settings.REQUEST_TIMEOUT,
        )
        return r.json()
