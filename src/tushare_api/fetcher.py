"""Tushare数据获取模块"""

import tushare as ts
import pandas as pd
from typing import Optional, Literal
from datetime import datetime, timedelta
from pathlib import Path


def normalize_code(code: str) -> str:
    """
    标准化证券代码，添加市场后缀

    Args:
        code: 证券代码 (如 "399303" 或 "000001.SZ" 或 "00700.HK")

    Returns:
        标准化后的代码 (如 "399303.SZ")
    """
    code = str(code).strip()

    # 如果已经有后缀，直接返回
    if "." in code:
        return code.upper()

    # 港股代码处理
    # 格式1: "HK1364" 或 "hk1364" -> "1364.HK"
    if code.upper().startswith("HK"):
        hk_code = code[2:].zfill(5)  # 去掉HK前缀，补齐5位
        return f"{hk_code}.HK"

    # 北交所代码 (899xxx)
    if code.startswith("899"):
        return f"{code}.BJ"

    # 格式2: 5位纯数字 -> 港股
    if len(code) == 5 and code.isdigit():
        return f"{code}.HK"

    # 根据代码规则添加后缀
    # 399开头 -> 深圳指数
    if code.startswith("399"):
        return f"{code}.SZ"

    # 000/001/002/003开头 -> 深圳主板/中小板
    if code.startswith(("000", "001", "002", "003")):
        return f"{code}.SZ"

    # 3开头 -> 创业板
    if code.startswith("3"):
        return f"{code}.SZ"

    # 6开头 -> 上海主板
    if code.startswith("6"):
        return f"{code}.SH"

    # 51/52/56/58开头 -> 上海ETF
    if code.startswith(("51", "52", "56", "58")):
        return f"{code}.SH"

    # 15/16开头 -> 深圳ETF
    if code.startswith(("15", "16")):
        return f"{code}.SZ"

    # 9开头 -> 上海指数
    if code.startswith("9"):
        return f"{code}.SH"

    # 默认深圳
    return f"{code}.SZ"


class TushareDataFetcher:
    """Tushare数据获取器"""

    def __init__(self, token: str, cache_dir: Optional[str] = None, cache_enabled: bool = True):
        ts.set_token(token)
        self.pro = ts.pro_api()
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/cache")
        self.cache_enabled = cache_enabled

        # 创建缓存目录
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_trade_calendar(self, start_date: str, end_date: str) -> list:
        """
        获取交易日历

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            交易日列表
        """
        df = self.pro.trade_cal(
            exchange="SSE",
            start_date=start_date,
            end_date=end_date,
            is_open="1"
        )
        return sorted(df["cal_date"].tolist()) if not df.empty else []

    def get_latest_trade_date(self) -> str:
        """获取最近一个交易日期"""
        today = datetime.now()
        start = (today - timedelta(days=10)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        trade_dates = self.get_trade_calendar(start, end)
        return trade_dates[-1] if trade_dates else None

    def _get_cache_path(self, ts_code: str, data_type: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{ts_code.replace('.', '_')}_{data_type}.csv"

    def _load_cache(self, ts_code: str, data_type: str) -> Optional[pd.DataFrame]:
        """加载缓存数据"""
        if not self.cache_enabled:
            return None

        cache_path = self._get_cache_path(ts_code, data_type)
        if cache_path.exists():
            try:
                df = pd.read_csv(cache_path)
                if not df.empty:
                    return df
            except Exception:
                pass
        return None

    def _save_cache(self, df: pd.DataFrame, ts_code: str, data_type: str):
        """保存缓存数据"""
        if not self.cache_enabled or df.empty:
            return

        cache_path = self._get_cache_path(ts_code, data_type)
        df.to_csv(cache_path, index=False)

    def get_stock_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 120,
        adj: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取股票日线数据（前复权）

        Args:
            ts_code: 股票代码 (如 000001.SZ)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            days: 如果未指定日期，获取最近N天
            adj: 复权类型 qfq=前复权 hfq=后复权 None=不复权

        Returns:
            日线数据DataFrame，包含 open, high, low, close, volume 等
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        # 使用 pro_bar 获取前复权数据
        df = ts.pro_bar(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            adj=adj,
            api=self.pro
        )

        if df.empty:
            return df

        # 标准化列名和排序
        df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def get_etf_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 120
    ) -> pd.DataFrame:
        """
        获取ETF日线数据

        Args:
            ts_code: ETF代码 (如 510050.SH)
            start_date: 开始日期
            end_date: 结束日期
            days: 获取最近N天

        Returns:
            日线数据DataFrame
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        # ETF使用 fund_daily 接口
        df = self.pro.fund_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            return df

        df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def get_index_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 120
    ) -> pd.DataFrame:
        """
        获取指数/板块日线数据

        Args:
            ts_code: 指数代码 (如 000001.SH 上证指数, 399001.SZ 深证成指)
            start_date: 开始日期
            end_date: 结束日期
            days: 获取最近N天

        Returns:
            日线数据DataFrame
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        # 指数使用 index_daily 接口
        df = self.pro.index_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            return df

        df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def get_hk_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 120
    ) -> pd.DataFrame:
        """
        获取港股日线数据

        Args:
            ts_code: 港股代码 (如 00700.HK 腾讯)
            start_date: 开始日期
            end_date: 结束日期
            days: 获取最近N天

        Returns:
            日线数据DataFrame
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        # 港股使用 hk_daily 接口
        df = self.pro.hk_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            return df

        df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def get_daily_data(
        self,
        ts_code: str,
        security_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 120
    ) -> pd.DataFrame:
        """
        根据证券类型获取日线数据

        Args:
            ts_code: 证券代码
            security_type: 证券类型 (股票/ETF/板块)
            start_date: 开始日期
            end_date: 结束日期
            days: 获取最近N天

        Returns:
            日线数据DataFrame
        """
        # 尝试加载缓存
        cached = self._load_cache(ts_code, "daily")
        if cached is not None and not cached.empty:
            # 检查缓存是否包含足够的数据
            latest_date = cached["trade_date"].max()
            if end_date and latest_date >= end_date:
                return cached

        # 根据类型调用不同接口
        type_lower = security_type.lower() if security_type else ""

        if type_lower in ["股票", "stock"]:
            df = self.get_stock_daily(ts_code, start_date, end_date, days)
        elif type_lower in ["etf", "基金"]:
            df = self.get_etf_daily(ts_code, start_date, end_date, days)
        elif type_lower in ["板块", "指数", "index"]:
            df = self.get_index_daily(ts_code, start_date, end_date, days)
        elif type_lower in ["港股", "hk", "hstock"]:
            df = self.get_hk_daily(ts_code, start_date, end_date, days)
        else:
            # 尝试自动识别
            detected_type = self.detect_security_type(ts_code)
            if detected_type == "stock":
                df = self.get_stock_daily(ts_code, start_date, end_date, days)
            elif detected_type == "etf":
                df = self.get_etf_daily(ts_code, start_date, end_date, days)
            elif detected_type == "index":
                df = self.get_index_daily(ts_code, start_date, end_date, days)
            elif detected_type == "hk":
                df = self.get_hk_daily(ts_code, start_date, end_date, days)
            else:
                # 默认尝试股票接口
                df = self.get_stock_daily(ts_code, start_date, end_date, days)

        # 保存缓存
        if not df.empty:
            self._save_cache(df, ts_code, "daily")

        return df

    def detect_security_type(self, ts_code: str) -> Literal["stock", "etf", "index", "hk", "unknown"]:
        """
        识别证券类型

        Args:
            ts_code: 证券代码

        Returns:
            证券类型
        """
        code, market = ts_code.split(".")

        # 港股
        if market == "HK":
            return "hk"

        # 北交所
        if market == "BJ":
            return "index"

        # ETF基金代码规则 (51/52/56/58开头是上交所ETF, 15/16开头是深交所ETF)
        if code.startswith(("51", "52", "56", "58")) and market == "SH":
            return "etf"
        if code.startswith("15") or code.startswith("16"):
            return "etf"

        # 指数代码规则
        if code.startswith("000") and market == "SH":
            return "index"
        if code.startswith("399") and market == "SZ":
            return "index"
        if code.startswith("9"):
            return "index"

        # 默认为股票
        if market in ["SH", "SZ"]:
            return "stock"

        return "unknown"
