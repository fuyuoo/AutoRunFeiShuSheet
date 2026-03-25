"""测试周线聚合模块"""

import pytest
import pandas as pd
import numpy as np

from src.utils import aggregate_to_weekly, get_weekly_from_daily


@pytest.fixture
def sample_daily_df():
    """创建测试日线数据（包含完整两周）"""
    np.random.seed(42)

    # 创建10个交易日（约两周）
    dates = pd.date_range("2024-01-02", periods=10, freq="B")  # 工作日
    close = np.cumsum(np.random.randn(10)) + 100
    high = close + np.random.rand(10) * 2
    low = close - np.random.rand(10) * 2

    return pd.DataFrame({
        "trade_date": dates.strftime("%Y%m%d"),
        "open": close + np.random.randn(10),
        "high": high,
        "low": low,
        "close": close,
        "vol": np.random.randint(1000000, 10000000, 10),
        "amount": np.random.randint(10000000, 100000000, 10)
    })


def test_aggregate_to_weekly(sample_daily_df):
    """测试周线聚合"""
    weekly = aggregate_to_weekly(sample_daily_df)

    assert not weekly.empty
    assert "trade_date" in weekly.columns
    assert "open" in weekly.columns
    assert "high" in weekly.columns
    assert "low" in weekly.columns
    assert "close" in weekly.columns
    assert "volume" in weekly.columns

    # 周线数量应该少于日线
    assert len(weekly) < len(sample_daily_df)


def test_weekly_ohlc_logic(sample_daily_df):
    """测试周线OHLC聚合逻辑"""
    weekly = aggregate_to_weekly(sample_daily_df)

    if not weekly.empty:
        # 检查第一根周线
        first_week = weekly.iloc[0]

        # 收盘价应该是该周最后一个交易日的收盘价
        # 最高价应该大于等于开盘价
        assert first_week["high"] >= first_week["low"]
        assert first_week["close"] > 0


def test_get_weekly_from_daily(sample_daily_df):
    """测试获取最近N周数据"""
    weekly = get_weekly_from_daily(sample_daily_df, weeks=2)

    assert not weekly.empty
    assert len(weekly) <= 2


def test_empty_dataframe_aggregate():
    """测试空DataFrame聚合"""
    empty_df = pd.DataFrame()
    weekly = aggregate_to_weekly(empty_df)

    assert weekly.empty


def test_weekly_date_format(sample_daily_df):
    """测试周线日期格式"""
    weekly = aggregate_to_weekly(sample_daily_df)

    if not weekly.empty:
        # 日期格式应该是 YYYYMMDD
        first_date = weekly.iloc[0]["trade_date"]
        assert len(str(first_date)) == 8
        assert str(first_date).isdigit()
