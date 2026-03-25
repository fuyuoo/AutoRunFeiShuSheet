#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AutoRunFeiShuSheet - 自动同步金融数据到飞书多维表格"""

import sys
import os
from pathlib import Path

# Windows 控制台编码修复
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.sync import sync_data


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("📈 AutoRunFeiShuSheet - 金融数据同步工具")
    print("=" * 60)
    print("功能: 从Tushare获取数据，计算技术指标，同步到飞书多维表格")
    print("=" * 60)

    try:
        sync_data()
    except FileNotFoundError as e:
        print(f"\n❌ 配置文件错误: {e}")
        print("\n📝 请确保已正确配置 config/config.yaml 文件")
        sys.exit(1)
    except KeyError as e:
        print(f"\n❌ 配置项缺失: {e}")
        print("\n📝 请检查 config/config.yaml 中的配置项是否完整")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✨ 同步完成!")


if __name__ == "__main__":
    main()
