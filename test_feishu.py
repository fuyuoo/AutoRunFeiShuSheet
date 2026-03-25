#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试飞书API连接"""

import sys
import os
from pathlib import Path
import yaml

# 设置控制台编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.feishu import FeishuClient, BitableClient


def load_config():
    """加载配置"""
    config_path = project_root / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_feishu_connection():
    """测试飞书连接"""
    print("\n" + "=" * 60)
    print("测试飞书API连接")
    print("=" * 60)

    config = load_config()
    feishu_config = config["feishu"]

    # 检查配置
    app_id = feishu_config.get("app_id", "")
    app_secret = feishu_config.get("app_secret", "")
    app_token = feishu_config.get("bitable", {}).get("app_token", "")
    table_id = feishu_config.get("bitable", {}).get("table_id", "")

    print(f"\n配置检查:")
    print(f"  App ID: {app_id[:8]}...{app_id[-4:] if len(app_id) > 12 else app_id}")
    print(f"  App Secret: {'*' * 8}...{app_secret[-4:] if len(app_secret) > 8 else '未配置'}")
    print(f"  App Token: {app_token[:8]}...{app_token[-4:] if len(app_token) > 12 else app_token}")
    print(f"  Table ID: {table_id}")

    if "your_" in app_id or "your_" in app_secret:
        print("\n请先在 config/config.yaml 中配置飞书应用凭证")
        return False

    # 测试获取 token
    print("\n测试1: 获取 access_token...")
    try:
        client = FeishuClient(app_id=app_id, app_secret=app_secret)
        token = client.get_tenant_access_token()
        print(f"  成功! Token: {token[:20]}...")
    except Exception as e:
        print(f"  失败: {e}")
        return False

    # 测试获取表格字段
    print("\n测试2: 获取多维表格字段...")
    try:
        bitable = BitableClient(
            client=client,
            app_token=app_token,
            table_id=table_id
        )
        fields_result = bitable.get_fields()
        if fields_result.get("code") == 0:
            fields = fields_result.get("data", {}).get("items", [])
            print(f"  成功! 共 {len(fields)} 个字段:")
            for f in fields:
                print(f"    - {f.get('field_name')} ({f.get('type')})")
        else:
            print(f"  失败: {fields_result.get('msg')}")
            return False
    except Exception as e:
        print(f"  失败: {e}")
        return False

    # 测试获取记录
    print("\n测试3: 获取表格记录...")
    try:
        records = bitable.get_all_records()
        print(f"  成功! 共 {len(records)} 条记录")

        if records:
            # 显示第一条记录
            first_record = records[0]
            print(f"\n  第一条记录示例:")
            for key, value in first_record.get("fields", {}).items():
                print(f"    {key}: {value}")
    except Exception as e:
        print(f"  失败: {e}")
        return False

    print("\n" + "=" * 60)
    print("飞书API连接测试通过!")
    print("=" * 60)
    return True


def main():
    try:
        success = test_feishu_connection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
