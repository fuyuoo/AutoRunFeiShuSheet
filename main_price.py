"""
价格同步程序入口

功能：
1. 从飞书多维表格读取证券代码和类型
2. 通过 Tushare 获取最新价格和日涨幅
3. 批量更新到飞书多维表格

使用方法：
    python main_price.py
"""

import sys
import io
from pathlib import Path

# Windows 控制台 UTF-8 支持
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.sync.sync_price import sync_price


def main():
    """主函数"""
    sync_price(config_path="config/config_price.yaml")


if __name__ == "__main__":
    main()
