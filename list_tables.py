#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""获取飞书多维表格中的所有表格ID"""

import sys
import os
from pathlib import Path
import yaml
import requests

# 设置控制台编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.feishu import FeishuClient


def load_config():
    config_path = project_root / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_tables():
    """获取多维表格中的所有表格"""
    config = load_config()
    feishu_config = config["feishu"]

    app_id = feishu_config["app_id"]
    app_secret = feishu_config["app_secret"]
    app_token = feishu_config["bitable"]["app_token"]

    print("\n" + "=" * 60)
    print("获取多维表格中的所有表格")
    print("=" * 60)

    # 获取token
    client = FeishuClient(app_id=app_id, app_secret=app_secret)
    token = client.get_tenant_access_token()

    # 请求表格列表
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    data = response.json()

    if data.get("code") != 0:
        print(f"获取失败: {data.get('msg')}")
        return

    tables = data.get("data", {}).get("items", [])

    print(f"\n多维表格 App Token: {app_token}")
    print(f"\n共有 {len(tables)} 个表格:\n")

    for i, table in enumerate(tables, 1):
        table_id = table.get("table_id")
        name = table.get("name")
        print(f"  {i}. 表格名称: {name}")
        print(f"     Table ID: {table_id}")
        print()

    if len(tables) == 1:
        print(f"建议配置: table_id: \"{tables[0]['table_id']}\"")


if __name__ == "__main__":
    list_tables()
