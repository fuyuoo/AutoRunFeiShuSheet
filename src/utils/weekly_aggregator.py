"""周线数据聚合模块"""

import pandas as pd
from typing import Optional


def aggregate_to_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    将日线数据聚合为周线数据

    周线规则：
    - 开盘价：本周第一根K线的开盘价
    - 最高价：本周所有K线的最高价
    - 最低价：本周所有K线的最低价
    - 收盘价：本周最后一根K线的收盘价
    - 成交量：本周所有K线成交量之和
    - 日期：使用周五日期作为周线日期

    Args:
        daily_df: 日线数据DataFrame，必须包含 trade_date, open, high, low, close, volume 列

    Returns:
        周线数据DataFrame
    """
    if daily_df.empty:
        return pd.DataFrame()

    # 确保日期格式正确
    df = daily_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    # 添加周信息
    df["year"] = df["trade_date"].dt.isocalendar().year
    df["week"] = df["trade_date"].dt.isocalendar().week

    # 按年周分组聚合
    weekly = df.groupby(["year", "week"]).agg({
        "trade_date": "last",  # 周五日期
        "open": "first",      # 周一开盘
        "high": "max",        # 周内最高
        "low": "min",         # 周内最低
        "close": "last",      # 周五收盘
        "vol": "sum",         # 周成交量
        "amount": "sum" if "amount" in df.columns else "sum"
    }).reset_index()

    # 重命名列
    weekly = weekly.rename(columns={"vol": "volume"})

    # 选择需要的列并按日期排序
    result_cols = ["trade_date", "open", "high", "low", "close", "volume"]
    if "amount" in weekly.columns:
        result_cols.append("amount")

    weekly = weekly[result_cols]
    weekly = weekly.sort_values("trade_date").reset_index(drop=True)

    # 转换日期格式回 YYYYMMDD
    weekly["trade_date"] = weekly["trade_date"].dt.strftime("%Y%m%d")

    return weekly


def aggregate_to_monthly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    将日线数据聚合为月线数据

    月线规则：
    - 开盘价：本月第一根K线的开盘价
    - 最高价：本月所有K线的最高价
    - 最低价：本月所有K线的最低价
    - 收盘价：本月最后一根K线的收盘价
    - 成交量：本月所有K线成交量之和
    - 日期：使用月末日期

    Args:
        daily_df: 日线数据DataFrame，必须包含 trade_date, open, high, low, close, volume 列

    Returns:
        月线数据DataFrame
    """
    if daily_df.empty:
        return pd.DataFrame()

    # 确保日期格式正确
    df = daily_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    # 添加月信息
    df["year"] = df["trade_date"].dt.year
    df["month"] = df["trade_date"].dt.month

    # 按年月分组聚合
    monthly = df.groupby(["year", "month"]).agg({
        "trade_date": "last",  # 月末日期
        "open": "first",      # 月初开盘
        "high": "max",        # 月内最高
        "low": "min",         # 月内最低
        "close": "last",      # 月末收盘
        "vol": "sum",         # 月成交量
        "amount": "sum" if "amount" in df.columns else "sum"
    }).reset_index()

    # 重命名列
    monthly = monthly.rename(columns={"vol": "volume"})

    # 选择需要的列并按日期排序
    result_cols = ["trade_date", "open", "high", "low", "close", "volume"]
    if "amount" in monthly.columns:
        result_cols.append("amount")

    monthly = monthly[result_cols]
    monthly = monthly.sort_values("trade_date").reset_index(drop=True)

    # 转换日期格式回 YYYYMMDD
    monthly["trade_date"] = monthly["trade_date"].dt.strftime("%Y%m%d")

    return monthly


def get_weekly_from_daily(daily_df: pd.DataFrame, weeks: int = 30) -> pd.DataFrame:
    """
    从日线数据获取最近N周的周线数据

    Args:
        daily_df: 日线数据DataFrame
        weeks: 需要的周数

    Returns:
        最近N周的周线数据
    """
    weekly = aggregate_to_weekly(daily_df)

    if weekly.empty:
        return weekly

    # 返回最近N周
    return weekly.tail(weeks).reset_index(drop=True)
