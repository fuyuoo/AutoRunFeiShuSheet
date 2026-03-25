"""飞书多维表格操作"""

from typing import List, Optional
from .client import FeishuClient


class BitableClient:
    """多维表格API客户端"""

    def __init__(self, client: FeishuClient, app_token: str, table_id: str):
        self.client = client
        self.app_token = app_token
        self.table_id = table_id

    def _get_base_path(self) -> str:
        return f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}"

    def list_records(
        self,
        view_id: Optional[str] = None,
        field_names: Optional[List[str]] = None,
        page_size: int = 500,
        page_token: Optional[str] = None
    ) -> dict:
        """
        获取记录列表

        Args:
            view_id: 视图ID
            field_names: 需要返回的字段名列表
            page_size: 每页记录数
            page_token: 分页token

        Returns:
            包含记录列表的字典
        """
        path = f"{self._get_base_path()}/records"
        params = {"page_size": page_size}

        if view_id:
            params["view_id"] = view_id
        if field_names:
            params["field_names"] = ",".join(field_names)
        if page_token:
            params["page_token"] = page_token

        return self.client.request("GET", path, params=params)

    def get_all_records(self, view_id: Optional[str] = None,
                       field_names: Optional[List[str]] = None) -> List[dict]:
        """
        获取所有记录(自动分页)

        Returns:
            所有记录的列表
        """
        all_records = []
        page_token = None

        while True:
            result = self.list_records(
                view_id=view_id,
                field_names=field_names,
                page_token=page_token
            )

            if result.get("code") != 0:
                raise Exception(f"获取记录失败: {result.get('msg')}")

            items = result.get("data", {}).get("items", [])
            all_records.extend(items)

            page_token = result.get("data", {}).get("page_token")
            if not page_token:
                break

        return all_records

    def update_record(self, record_id: str, fields: dict) -> dict:
        """
        更新记录

        Args:
            record_id: 记录ID
            fields: 要更新的字段键值对

        Returns:
            API响应
        """
        path = f"{self._get_base_path()}/records/{record_id}"
        payload = {
            "fields": fields
        }
        return self.client.request("PUT", path, json=payload)

    def batch_update_records(self, records: List[dict]) -> dict:
        """
        批量更新记录

        Args:
            records: 记录列表, 每条记录包含 record_id 和 fields

        Returns:
            API响应
        """
        path = f"{self._get_base_path()}/records/batch_update"
        payload = {"records": records}
        return self.client.request("POST", path, json=payload)

    def create_record(self, fields: dict) -> dict:
        """
        创建记录

        Args:
            fields: 字段键值对

        Returns:
            API响应
        """
        path = f"{self._get_base_path()}/records"
        payload = {"fields": fields}
        return self.client.request("POST", path, json=payload)

    def get_fields(self) -> dict:
        """获取表格字段列表"""
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/fields"
        return self.client.request("GET", path)
