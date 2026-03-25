#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试飞书写入权限"""

import sys
import os
from pathlib import Path
import yaml
import requests

if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.feishu import FeishuClient


def test_write_permission():
    """测试写入权限"""
    config_path = project_root / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    feishu_config = config["feishu"]
    app_id = feishu_config["app_id"]
    app_secret = feishu_config["app_secret"]
    app_token = feishu_config["bitable"]["app_token"]
    table_id = feishu_config["bitable"]["table_id"]

    print("\n" + "=" * 60)
    print("调试飞书写入权限")
    print("=" * 60)

    # 获取token
    client = FeishuClient(app_id=app_id, app_secret=app_secret)
    token = client.get_tenant_access_token()
    print(f"\nToken: {token[:30]}...")

    # 尝试更新单条记录
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 先获取一条记录的ID
    list_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    list_response = requests.get(list_url, headers=headers, params={"page_size": 1})
    list_data = list_response.json()

    if list_data.get("code") != 0:
        print(f"\n获取记录失败: {list_data.get('msg')}")
        return

    record_id = list_data["data"]["items"][0]["record_id"]
    print(f"测试记录ID: {record_id}")

    # 尝试更新
    payload = {
        "records": [
            {
                "record_id": record_id,
                "fields": {
                    "最新检查时间": "20260319"
                }
            }
        ]
    }

    print(f"\n请求URL: {url}")
    print(f"请求体: {payload}")

    response = requests.post(url, headers=headers, json=payload)
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")


if __name__ == "__main__":
    test_write_permission()
