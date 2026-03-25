"""飞书API客户端"""

import time
import requests
from typing import Optional


class FeishuClient:
    """飞书开放平台API客户端"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: float = 0

    def get_tenant_access_token(self) -> str:
        """获取tenant_access_token"""
        # 检查token是否有效
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token

        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"获取token失败: {data.get('msg')}")

        self._tenant_access_token = data["tenant_access_token"]
        print(f"\n✨ _tenant_access_token = {self._tenant_access_token}")
        # 提前5分钟过期
        self._token_expire_time = time.time() + data["expire"] - 300

        return self._tenant_access_token

    def _get_headers(self) -> dict:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.get_tenant_access_token()}",
            "Content-Type": "application/json"
        }

    def request(self, method: str, path: str, **kwargs) -> dict:
        """发送API请求"""
        url = f"{self.BASE_URL}{path}"
        headers = self._get_headers()

        method = method.upper()
        if method == "GET":
            response = requests.get(url, headers=headers, **kwargs)
        elif method == "POST":
            response = requests.post(url, headers=headers, **kwargs)
        elif method == "PUT":
            response = requests.put(url, headers=headers, **kwargs)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, **kwargs)
        else:
            raise ValueError(f"不支持的请求方法: {method}")

        response.raise_for_status()
        return response.json()
