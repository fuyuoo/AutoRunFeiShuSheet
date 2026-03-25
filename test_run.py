#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试脚本 - 不依赖飞书，测试Tushare数据获取和指标计算"""

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

from src.tushare_api import TushareDataFetcher
from src.indicators import calculate_indicators_for_security
from src.utils import aggregate_to_weekly


def load_config():
    """加载配置"""
    config_path = project_root / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_stock_data():
    """测试股票数据获取和指标计算"""
    print("\n" + "=" * 60)
    print("📊 测试股票数据")
    print("=" * 60)

    config = load_config()
    token = config["tushare"]["token"]

    fetcher = TushareDataFetcher(
        token=token,
        cache_dir="data/cache",
        cache_enabled=True
    )

    # 测试股票：平安银行 000001.SZ
    ts_code = "000001.SZ"
    print(f"\n📥 获取 {ts_code} 日线数据...")

    daily_df = fetcher.get_daily_data(
        ts_code=ts_code,
        security_type="股票",
        days=120
    )

    if daily_df.empty:
        print(f"❌ 未获取到数据")
        return None

    print(f"✅ 获取到 {len(daily_df)} 条日线数据")
    print(f"   日期范围: {daily_df['trade_date'].iloc[0]} ~ {daily_df['trade_date'].iloc[-1]}")
    print(f"   最新收盘价: {daily_df['close'].iloc[-1]:.2f}")

    # 聚合周线
    print(f"\n📈 聚合周线数据...")
    weekly_df = aggregate_to_weekly(daily_df)
    print(f"✅ 聚合得到 {len(weekly_df)} 条周线数据")

    # 计算指标
    print(f"\n🔧 计算技术指标...")
    indicator_config = config.get("sync", {}).get("indicators", {})
    indicators = calculate_indicators_for_security(
        daily_df=daily_df,
        weekly_df=weekly_df,
        indicator_config=indicator_config
    )

    # 打印结果
    print(f"\n📊 指标结果:")
    print("-" * 40)

    print("\n【日线指标】")
    print(f"  KDJ: K={indicators.get('daily_kdj_k')} D={indicators.get('daily_kdj_d')} J={indicators.get('daily_kdj_j')}")
    print(f"  CCI: {indicators.get('daily_cci')}")
    print(f"  BOLL: 上轨={indicators.get('daily_boll_upper')} 中轨={indicators.get('daily_boll_middle')} 下轨={indicators.get('daily_boll_lower')}")

    print("\n【周线指标】")
    print(f"  KDJ: K={indicators.get('weekly_kdj_k')} D={indicators.get('weekly_kdj_d')} J={indicators.get('weekly_kdj_j')}")
    print(f"  CCI: {indicators.get('weekly_cci')}")
    print(f"  BOLL: 上轨={indicators.get('weekly_boll_upper')} 中轨={indicators.get('weekly_boll_middle')} 下轨={indicators.get('weekly_boll_lower')}")

    print("\n【其他】")
    print(f"  最新收盘价: {indicators.get('close')}")
    print(f"  交易日期: {indicators.get('trade_date')}")

    return indicators


def test_etf_data():
    """测试ETF数据获取"""
    print("\n" + "=" * 60)
    print("📊 测试ETF数据")
    print("=" * 60)

    config = load_config()
    token = config["tushare"]["token"]

    fetcher = TushareDataFetcher(token=token, cache_enabled=True)

    # 测试ETF：沪深300ETF 510300.SH
    ts_code = "510300.SH"
    print(f"\n📥 获取 {ts_code} 日线数据...")

    daily_df = fetcher.get_daily_data(
        ts_code=ts_code,
        security_type="ETF",
        days=120
    )

    if daily_df.empty:
        print(f"❌ 未获取到数据")
        return None

    print(f"✅ 获取到 {len(daily_df)} 条日线数据")
    print(f"   最新收盘价: {daily_df['close'].iloc[-1]:.3f}")

    # 聚合周线并计算指标
    weekly_df = aggregate_to_weekly(daily_df)
    indicators = calculate_indicators_for_security(daily_df, weekly_df)

    print(f"\n【日线KDJ】K={indicators.get('daily_kdj_k')} D={indicators.get('daily_kdj_d')} J={indicators.get('daily_kdj_j')}")
    print(f"【周线KDJ】K={indicators.get('weekly_kdj_k')} D={indicators.get('weekly_kdj_d')} J={indicators.get('weekly_kdj_j')}")

    return indicators


def test_index_data():
    """测试指数/板块数据获取"""
    print("\n" + "=" * 60)
    print("📊 测试指数数据")
    print("=" * 60)

    config = load_config()
    token = config["tushare"]["token"]

    fetcher = TushareDataFetcher(token=token, cache_enabled=True)

    # 测试指数：上证指数 000001.SH
    ts_code = "000001.SH"
    print(f"\n📥 获取 {ts_code} 日线数据...")

    daily_df = fetcher.get_daily_data(
        ts_code=ts_code,
        security_type="板块",
        days=120
    )

    if daily_df.empty:
        print(f"❌ 未获取到数据")
        return None

    print(f"✅ 获取到 {len(daily_df)} 条日线数据")
    print(f"   最新收盘价: {daily_df['close'].iloc[-1]:.2f}")

    # 聚合周线并计算指标
    weekly_df = aggregate_to_weekly(daily_df)
    indicators = calculate_indicators_for_security(daily_df, weekly_df)

    print(f"\n【日线KDJ】K={indicators.get('daily_kdj_k')} D={indicators.get('daily_kdj_d')} J={indicators.get('daily_kdj_j')}")
    print(f"【周线KDJ】K={indicators.get('weekly_kdj_k')} D={indicators.get('weekly_kdj_d')} J={indicators.get('weekly_kdj_j')}")

    return indicators


def test_cache():
    """测试缓存功能"""
    print("\n" + "=" * 60)
    print("📊 测试缓存功能")
    print("=" * 60)

    config = load_config()
    token = config["tushare"]["token"]

    cache_dir = Path("data/cache")
    fetcher = TushareDataFetcher(
        token=token,
        cache_dir=str(cache_dir),
        cache_enabled=True
    )

    # 第一次获取
    print("\n第一次获取 (从API)...")
    import time
    start = time.time()
    df1 = fetcher.get_daily_data("000001.SZ", "股票", days=120)
    time1 = time.time() - start
    print(f"  耗时: {time1:.2f}s, 数据量: {len(df1)}")

    # 第二次获取 (应该从缓存)
    print("\n第二次获取 (从缓存)...")
    start = time.time()
    df2 = fetcher.get_daily_data("000001.SZ", "股票", days=120)
    time2 = time.time() - start
    print(f"  耗时: {time2:.2f}s, 数据量: {len(df2)}")

    # 检查缓存文件
    cache_files = list(cache_dir.glob("*.csv"))
    print(f"\n缓存文件数量: {len(cache_files)}")
    for f in cache_files[:5]:
        print(f"  - {f.name}")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 AutoRunFeiShuSheet 功能测试")
    print("=" * 60)
    print("测试内容: Tushare数据获取、周线聚合、指标计算、缓存")
    print("=" * 60)

    try:
        # 测试股票
        test_stock_data()

        # 测试ETF
        test_etf_data()

        # 测试指数
        test_index_data()

        # 测试缓存
        test_cache()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
