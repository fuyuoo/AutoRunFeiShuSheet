#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试字段类型问题"""

import sys
import os
from pathlib import Path
import yaml

if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.feishu import FeishuClient
from src.sync.sync_data import DataSynchronizer


def debug_fields():
    """调试字段类型"""
    print("\n" + "=" * 60)
    print("调试字段类型问题")
    print("=" * 60)

    # 初始化同步器
    sync = DataSynchronizer()

    # 获取字段信息
    print("\n📋 获取飞书表格字段信息...")
    fields_result = sync.bitable.get_fields()

    if fields_result.get("code") != 0:
        print(f"获取字段失败: {fields_result.get('msg')}")
        return

    fields = fields_result.get("data", {}).get("items", [])
    print(f"\n表格字段 ({len(fields)} 个):")
    for field in fields:
        print(f"  - {field.get('field_name')}: 类型={field.get('type')}, ID={field.get('field_id')}")

    # 获取一条记录看看当前值
    print("\n📋 获取一条记录...")
    records = sync.bitable.get_all_records()

    if records:
        record = records[0]
        print(f"\n记录ID: {record.get('record_id')}")
        print("字段值:")
        for key, value in record.get("fields", {}).items():
            print(f"  - {key}: {value} (类型: {type(value).__name__})")

    # 计算一个证券的指标看看输出格式
    print("\n📋 计算指标数据格式...")
    securities = sync.get_securities_from_feishu()
    if securities:
        sec = securities[0]
        indicators = sync.process_security(sec["code"], sec["type"])
        if indicators:
            print("\n计算结果:")
            for key, value in indicators.items():
                print(f"  - {key}: {value} (类型: {type(value).__name__})")

            # 映射后的字段
            feishu_fields = sync._map_fields(indicators)
            print("\n映射后的飞书字段:")
            for key, value in feishu_fields.items():
                print(f"  - {key}: {value} (类型: {type(value).__name__})")


if __name__ == "__main__":
    debug_fields()
