"""数据同步模块"""

import yaml
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..feishu import FeishuClient, BitableClient
from ..tushare_api import TushareDataFetcher
from ..tushare_api.fetcher import normalize_code
from ..indicators import calculate_indicators_for_security
from ..utils import aggregate_to_weekly, aggregate_to_monthly


@dataclass
class SyncResult:
    """同步结果"""
    success: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[Dict] = field(default_factory=list)
    warnings: List[Dict] = field(default_factory=list)

    def add_error(self, code: str, reason: str):
        self.errors.append({"code": code, "reason": reason})
        self.failed += 1

    def add_warning(self, code: str, message: str):
        self.warnings.append({"code": code, "message": message})

    def print_report(self):
        """打印同步报告"""
        total = self.success + self.failed + self.skipped
        print("\n" + "=" * 60)
        print("📊 同步报告")
        print("=" * 60)
        print(f"✅ 成功: {self.success}")
        print(f"❌ 失败: {self.failed}")
        print(f"⏭️  跳过: {self.skipped}")
        print(f"📋 总计: {total}")

        if self.errors:
            print("\n❌ 失败详情:")
            for err in self.errors:
                print(f"   - {err['code']}: {err['reason']}")

        if self.warnings:
            print("\n⚠️  警告:")
            for warn in self.warnings:
                print(f"   - {warn['code']}: {warn['message']}")

        print("=" * 60)


class DataSynchronizer:
    """数据同步器"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self._init_clients()
        self.result = SyncResult()

        # 配置
        self.field_mapping = self.config.get("field_mapping", {})
        self.history_days = self.config.get("sync", {}).get("history_days", 120)
        self.indicator_config = self.config.get("sync", {}).get("indicators", {})
        self.code_column = self.config["feishu"]["bitable"].get("code_column", "证券代码")
        self.type_column = self.config["feishu"]["bitable"].get("type_column", "类型")

        # 速率限制配置 (港股每分钟最多2次请求)
        self.rate_limit_config = self.config.get("rate_limit", {})
        self.hk_stock_interval = self.rate_limit_config.get("hk_stock_interval", 31)  # 港股请求间隔(秒)
        self.last_hk_request_time = 0  # 上次港股请求时间
        self.hk_request_count = 0  # 港股请求计数器

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _init_clients(self):
        """初始化API客户端"""
        # Tushare
        cache_config = self.config.get("cache", {})
        self.tushare = TushareDataFetcher(
            token=self.config["tushare"]["token"],
            cache_dir=cache_config.get("dir", "data/cache"),
            cache_enabled=cache_config.get("enabled", True)
        )

        # 飞书
        feishu_config = self.config["feishu"]
        self.feishu_client = FeishuClient(
            app_id=feishu_config["app_id"],
            app_secret=feishu_config["app_secret"]
        )
        self.bitable = BitableClient(
            client=self.feishu_client,
            app_token=feishu_config["bitable"]["app_token"],
            table_id=feishu_config["bitable"]["table_id"]
        )

    def _map_fields(self, indicators: Dict, has_daily_data: bool = True, has_weekly_data: bool = True, has_monthly_data: bool = True) -> Dict:
        """
        将计算结果映射到飞书字段

        Args:
            indicators: 计算得到的指标字典
            has_daily_data: 是否有日线数据
            has_weekly_data: 是否有周线数据
            has_monthly_data: 是否有月线数据

        Returns:
            映射后的飞书字段字典
        """
        feishu_fields = {}

        for feishu_col, indicator_name in self.field_mapping.items():
            # 判断指标类型
            is_weekly_indicator = indicator_name.startswith("weekly_")
            is_monthly_indicator = indicator_name.startswith("monthly_")
            # 判断是否为日期字段
            is_date_field = indicator_name == "trade_date"

            if indicator_name in indicators:
                value = indicators[indicator_name]
                if value is not None:
                    # 处理日期字段 - 转换为毫秒级时间戳（包含时分秒）
                    if is_date_field:
                        try:
                            # 使用当前时间，包含时分秒
                            now = datetime.now()
                            value = int(now.timestamp() * 1000)
                        except (ValueError, TypeError):
                            pass

                    feishu_fields[feishu_col] = value
                # 值为None时跳过，不发送任何值（飞书显示空白）
            else:
                # 字段不存在时跳过，不发送任何值
                pass

        return feishu_fields

    def get_securities_from_feishu(self) -> List[Dict]:
        """从飞书获取证券代码列表"""
        print("📥 正在从飞书多维表格获取证券代码...")
        records = self.bitable.get_all_records()

        securities = []
        for record in records:
            fields = record.get("fields", {})
            code = fields.get(self.code_column, "")
            sec_type = fields.get(self.type_column, "股票")

            if code:
                # 标准化代码格式 (如 "399303" -> "399303.SZ")
                normalized_code = normalize_code(str(code))
                securities.append({
                    "record_id": record["record_id"],
                    "code": normalized_code,
                    "original_code": str(code),
                    "type": str(sec_type)
                })

        print(f"📋 共获取到 {len(securities)} 个证券")
        return securities

    def _is_hk_stock(self, ts_code: str) -> bool:
        """判断是否是港股"""
        return ts_code.endswith(".HK")

    def _wait_for_rate_limit(self, ts_code: str):
        """
        根据证券类型进行速率限制等待

        Args:
            ts_code: 证券代码
        """
        if self._is_hk_stock(ts_code):
            current_time = time.time()

            # 第一个港股请求也需要等待，防止之前有其他请求触发限制
            if self.hk_request_count == 0:
                print(f"\n    ⏳ 港股首次请求，等待 {self.hk_stock_interval} 秒确保速率限制...", end="")
                time.sleep(self.hk_stock_interval)
            else:
                elapsed = current_time - self.last_hk_request_time

                if elapsed < self.hk_stock_interval:
                    wait_time = self.hk_stock_interval - elapsed
                    print(f"\n    ⏳ 港股速率限制，等待 {wait_time:.1f} 秒...", end="")
                    time.sleep(wait_time)

            self.last_hk_request_time = time.time()
            self.hk_request_count += 1

    def process_security(self, ts_code: str, sec_type: str, retry_count: int = 0) -> Tuple[Optional[Dict], bool, bool, bool]:
        """
        处理单个证券

        Args:
            ts_code: 证券代码
            sec_type: 证券类型
            retry_count: 重试次数

        Returns:
            (指标字典, 是否有日线数据, 是否有周线数据, 是否有月线数据)，失败返回 (None, False, False, False)
        """
        has_daily_data = False
        has_weekly_data = False
        has_monthly_data = False
        max_retries = 2  # 最大重试次数

        try:
            # 1. 获取日线数据
            daily_df = self.tushare.get_daily_data(
                ts_code=ts_code,
                security_type=sec_type,
                days=self.history_days
            )

            if daily_df.empty:
                # 日线数据缺失，记录警告
                print(f"\n    ⚠️  [WARN] {ts_code}: 未获取到日线数据")
                self.result.add_warning(ts_code, "未获取到日线数据")
                return {}, has_daily_data, has_weekly_data, has_monthly_data

            has_daily_data = True

            # 2. 聚合周线数据
            weekly_df = aggregate_to_weekly(daily_df)

            if weekly_df.empty:
                # 周线数据缺失，记录警告
                print(f"\n    ⚠️  [WARN] {ts_code}: 周线数据聚合失败")
                self.result.add_warning(ts_code, "周线数据聚合失败")
            else:
                has_weekly_data = True

            # 3. 聚合月线数据
            monthly_df = aggregate_to_monthly(daily_df)

            if monthly_df.empty:
                # 月线数据缺失，记录警告
                print(f"\n    ⚠️  [WARN] {ts_code}: 月线数据聚合失败")
                self.result.add_warning(ts_code, "月线数据聚合失败")
            else:
                has_monthly_data = True

            # 4. 计算指标
            indicators = calculate_indicators_for_security(
                daily_df=daily_df,
                weekly_df=weekly_df,
                monthly_df=monthly_df,
                indicator_config=self.indicator_config
            )

            return indicators, has_daily_data, has_weekly_data, has_monthly_data

        except Exception as e:
            error_msg = str(e)

            # 检查是否是速率限制错误
            if "每分钟最多访问" in error_msg or "权限" in error_msg:
                if retry_count < max_retries:
                    wait_time = 60  # 等待60秒后重试
                    print(f"\n    ⚠️  速率限制，等待 {wait_time} 秒后重试...", end="")
                    time.sleep(wait_time)
                    return self.process_security(ts_code, sec_type, retry_count + 1)

            print(f"\n    ❌ [ERROR] {ts_code}: {e}")
            self.result.add_error(ts_code, error_msg)
            return None, False, False, False

    def sync_all(self):
        """同步所有数据"""
        print("\n" + "=" * 60)
        print("🚀 开始同步数据")
        print("=" * 60)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. 获取证券列表
        securities = self.get_securities_from_feishu()

        if not securities:
            print("⚠️  没有需要同步的证券")
            return

        # 2. 处理每个证券
        print("\n📊 开始处理证券数据...")
        update_records = []

        for i, sec in enumerate(securities, 1):
            code = sec["code"]
            sec_type = sec["type"]
            print(f"  [{i}/{len(securities)}] 处理 {code} ({sec_type})...", end=" ")

            indicators, has_daily, has_weekly, has_monthly = self.process_security(code, sec_type)

            # 即使数据缺失，也要更新飞书（显示N/A）
            if indicators is not None:
                # 映射字段（包含N/A处理）
                feishu_fields = self._map_fields(indicators, has_daily, has_weekly, has_monthly)

                if feishu_fields:
                    update_records.append({
                        "record_id": sec["record_id"],
                        "fields": feishu_fields
                    })

                    if has_daily:
                        self.result.success += 1
                        status = "✅"
                        if not has_weekly:
                            status += " (周线缺失)"
                        if not has_monthly:
                            status += " (月线缺失)"
                        print(status)
                    else:
                        self.result.skipped += 1
                        print("⚠️ (日线缺失)")
                else:
                    self.result.add_warning(code, "字段映射为空")
                    self.result.skipped += 1
                    print("⚠️  字段映射为空")
            else:
                # 异常情况
                print("❌")

        # 3. 批量更新飞书
        if update_records:
            print(f"\n📤 正在更新飞书多维表格 ({len(update_records)} 条记录)...")
            try:
                result = self.bitable.batch_update_records(update_records)

                if result.get("code") == 0:
                    print("✅ 飞书更新成功!")
                else:
                    print(f"❌ 飞书更新失败: {result.get('msg')}")
                    self.result.add_error("FEISHU", result.get("msg", "未知错误"))
            except Exception as e:
                print(f"❌ 飞书更新异常: {e}")
                self.result.add_error("FEISHU", str(e))

        # 4. 打印报告
        self.result.print_report()
        print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def sync_data(config_path: str = "config/config.yaml"):
    """同步数据入口函数"""
    synchronizer = DataSynchronizer(config_path)
    synchronizer.sync_all()
