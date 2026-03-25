"""测试技术指标计算"""

import pytest
import pandas as pd
import numpy as np

from src.indicators import (
    calculate_kdj,
    calculate_cci,
    calculate_boll,
    calculate_all_indicators,
    calculate_indicators_for_security
)


@pytest.fixture
def sample_daily_df():
    """创建测试日线数据"""
    np.random.seed(42)
    n = 30
    close = np.cumsum(np.random.randn(n)) + 100
    high = close + np.random.rand(n) * 2
    low = close - np.random.rand(n) * 2

    return pd.DataFrame({
        "trade_date": pd.date_range("2024-01-01", periods=n).strftime("%Y%m%d"),
        "open": close + np.random.randn(n),
        "high": high,
        "low": low,
        "close": close,
        "vol": np.random.randint(1000000, 10000000, n)
    })


@pytest.fixture
def sample_weekly_df():
    """创建测试周线数据"""
    np.random.seed(42)
    n = 10
    close = np.cumsum(np.random.randn(n)) + 100
    high = close + np.random.rand(n) * 2
    low = close - np.random.rand(n) * 2

    return pd.DataFrame({
        "trade_date": pd.date_range("2024-01-01", periods=n, freq="W-FRI").strftime("%Y%m%d"),
        "open": close + np.random.randn(n),
        "high": high,
        "low": low,
        "close": close,
        "volume": np.random.randint(5000000, 50000000, n)
    })


def test_calculate_kdj(sample_daily_df):
    """测试KDJ计算"""
    k, d, j = calculate_kdj(sample_daily_df)

    assert len(k) == len(sample_daily_df)
    assert len(d) == len(sample_daily_df)
    assert len(j) == len(sample_daily_df)

    # K和D应该在0-100之间
    assert 0 <= k.iloc[-1] <= 100
    assert 0 <= d.iloc[-1] <= 100


def test_calculate_cci(sample_daily_df):
    """测试CCI计算"""
    cci = calculate_cci(sample_daily_df)

    assert len(cci) == len(sample_daily_df)
    assert not pd.isna(cci.iloc[-1])


def test_calculate_boll(sample_daily_df):
    """测试BOLL计算"""
    upper, middle, lower = calculate_boll(sample_daily_df)

    assert len(upper) == len(sample_daily_df)
    assert len(middle) == len(sample_daily_df)
    assert len(lower) == len(sample_daily_df)

    # 上轨应该大于中轨，中轨应该大于下轨
    assert upper.iloc[-1] > middle.iloc[-1]
    assert middle.iloc[-1] > lower.iloc[-1]


def test_calculate_all_indicators_daily(sample_daily_df):
    """测试计算所有日线指标"""
    result = calculate_all_indicators(sample_daily_df, prefix="daily")

    assert "daily_kdj_k" in result
    assert "daily_kdj_d" in result
    assert "daily_kdj_j" in result
    assert "daily_cci" in result
    assert "daily_boll_upper" in result
    assert "daily_boll_middle" in result
    assert "daily_boll_lower" in result


def test_calculate_all_indicators_weekly(sample_weekly_df):
    """测试计算所有周线指标"""
    result = calculate_all_indicators(sample_weekly_df, prefix="weekly")

    assert "weekly_kdj_k" in result
    assert "weekly_kdj_d" in result
    assert "weekly_kdj_j" in result
    assert "weekly_cci" in result
    assert "weekly_boll_upper" in result
    assert "weekly_boll_middle" in result
    assert "weekly_boll_lower" in result


def test_calculate_indicators_for_security(sample_daily_df, sample_weekly_df):
    """测试计算证券的所有指标"""
    result = calculate_indicators_for_security(
        daily_df=sample_daily_df,
        weekly_df=sample_weekly_df
    )

    # 检查日线指标
    assert "daily_kdj_k" in result
    assert "daily_cci" in result
    assert "daily_boll_upper" in result

    # 检查周线指标
    assert "weekly_kdj_k" in result
    assert "weekly_cci" in result
    assert "weekly_boll_upper" in result

    # 检查其他字段
    assert "close" in result
    assert "trade_date" in result


def test_empty_dataframe():
    """测试空DataFrame"""
    empty_df = pd.DataFrame()
    result = calculate_all_indicators(empty_df)

    assert result == {}


def test_custom_params(sample_daily_df):
    """测试自定义参数"""
    result = calculate_all_indicators(
        sample_daily_df,
        prefix="test",
        kdj_params={"n": 14, "m1": 3, "m2": 3},
        cci_params={"n": 20},
        boll_params={"n": 26, "k": 2}
    )

    assert "test_kdj_k" in result
    assert "test_cci" in result
    assert "test_boll_upper" in result
