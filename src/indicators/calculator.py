"""技术指标计算模块"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional


def calculate_kdj(
    df: pd.DataFrame,
    n: int = 9,
    m1: int = 3,
    m2: int = 3
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算KDJ指标

    Args:
        df: 包含 high, low, close 列的DataFrame
        n: RSV周期 (默认9)
        m1: K值平滑周期 (默认3)
        m2: D值平滑周期 (默认3)

    Returns:
        (K, D, J) 三个Series
    """
    if df.empty:
        return pd.Series(), pd.Series(), pd.Series()

    low_n = df["low"].rolling(window=n, min_periods=1).min()
    high_n = df["high"].rolling(window=n, min_periods=1).max()

    # 避免除零
    denom = high_n - low_n
    denom = denom.replace(0, np.nan)

    rsv = (df["close"] - low_n) / denom * 100
    rsv = rsv.fillna(50)

    k = rsv.ewm(alpha=1/m1, adjust=False).mean()
    d = k.ewm(alpha=1/m2, adjust=False).mean()
    j = 3 * k - 2 * d

    return k, d, j


def calculate_cci(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """
    计算CCI指标 (商品通道指数)

    Args:
        df: 包含 high, low, close 列的DataFrame
        n: 周期 (默认14)

    Returns:
        CCI Series
    """
    if df.empty:
        return pd.Series()

    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma_tp = tp.rolling(window=n, min_periods=1).mean()

    # 计算平均绝对偏差
    def mad(x):
        return np.abs(x - x.mean()).mean() if len(x) > 0 else 0

    md = tp.rolling(window=n, min_periods=1).apply(mad)

    # 避免除零
    cci = (tp - ma_tp) / (0.015 * md.replace(0, np.nan))

    return cci


def calculate_boll(
    df: pd.DataFrame,
    n: int = 20,
    k: int = 2
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算布林带指标

    Args:
        df: 包含 close 列的DataFrame
        n: 移动平均周期 (默认20)
        k: 标准差倍数 (默认2)

    Returns:
        (upper, middle, lower) 三个Series
    """
    if df.empty:
        return pd.Series(), pd.Series(), pd.Series()

    middle = df["close"].rolling(window=n, min_periods=1).mean()
    std = df["close"].rolling(window=n, min_periods=1).std()

    upper = middle + k * std
    lower = middle - k * std

    return upper, middle, lower


def calculate_all_indicators(
    df: pd.DataFrame,
    prefix: str = "",
    kdj_params: Optional[Dict] = None,
    cci_params: Optional[Dict] = None,
    boll_params: Optional[Dict] = None
) -> Dict:
    """
    计算所有技术指标并返回最新值

    Args:
        df: 包含OHLC数据的DataFrame
        prefix: 指标名称前缀 (如 "daily_" 或 "weekly_")
        kdj_params: KDJ参数 {"n": 9, "m1": 3, "m2": 3}
        cci_params: CCI参数 {"n": 14}
        boll_params: BOLL参数 {"n": 20, "k": 2}

    Returns:
        包含所有指标的字典(取最新一期的值)
    """
    if df.empty:
        return {}

    # 默认参数
    kdj_params = kdj_params or {"n": 9, "m1": 3, "m2": 3}
    cci_params = cci_params or {"n": 14}
    boll_params = boll_params or {"n": 20, "k": 2}

    # 计算KDJ
    k, d, j = calculate_kdj(df, **kdj_params)

    # 计算CCI
    cci = calculate_cci(df, **cci_params)

    # 计算BOLL
    upper, middle, lower = calculate_boll(df, **boll_params)

    # 取最新一期的值
    p = prefix.rstrip("_") + "_" if prefix else ""

    return {
        f"{p}kdj_k": round(float(k.iloc[-1]), 2) if not k.empty else None,
        f"{p}kdj_d": round(float(d.iloc[-1]), 2) if not d.empty else None,
        f"{p}kdj_j": round(float(j.iloc[-1]), 2) if not j.empty else None,
        f"{p}cci": round(float(cci.iloc[-1]), 2) if not cci.empty else None,
        f"{p}boll_upper": round(float(upper.iloc[-1]), 2) if not upper.empty else None,
        f"{p}boll_middle": round(float(middle.iloc[-1]), 2) if not middle.empty else None,
        f"{p}boll_lower": round(float(lower.iloc[-1]), 2) if not lower.empty else None,
    }


def calculate_indicators_for_security(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    monthly_df: pd.DataFrame = None,
    indicator_config: Optional[Dict] = None
) -> Dict:
    """
    计算证券的所有指标（日线 + 周线 + 月线）

    Args:
        daily_df: 日线数据
        weekly_df: 周线数据
        monthly_df: 月线数据
        indicator_config: 指标配置

    Returns:
        包含所有指标的字典
    """
    indicator_config = indicator_config or {}

    # 提取参数配置
    kdj_params = indicator_config.get("kdj", {"n": 9, "m1": 3, "m2": 3})
    cci_params = indicator_config.get("cci", {"n": 14})
    boll_params = indicator_config.get("boll", {"n": 20, "k": 2})

    params = {
        "kdj_params": kdj_params,
        "cci_params": cci_params,
        "boll_params": boll_params
    }

    result = {}

    # 计算日线指标
    if not daily_df.empty:
        daily_indicators = calculate_all_indicators(daily_df, prefix="daily", **params)
        result.update(daily_indicators)

        # 添加最新交易信息
        latest = daily_df.iloc[-1]
        result["close"] = float(latest["close"])
        result["trade_date"] = str(latest["trade_date"])

    # 计算周线指标
    if not weekly_df.empty:
        weekly_indicators = calculate_all_indicators(weekly_df, prefix="weekly", **params)
        result.update(weekly_indicators)

        # 添加周收盘价
        result["weekly_close"] = float(weekly_df.iloc[-1]["close"])

    # 计算月线指标
    if monthly_df is not None and not monthly_df.empty:
        monthly_indicators = calculate_all_indicators(monthly_df, prefix="monthly", **params)
        result.update(monthly_indicators)

        # 添加月收盘价
        result["monthly_close"] = float(monthly_df.iloc[-1]["close"])

    return result
