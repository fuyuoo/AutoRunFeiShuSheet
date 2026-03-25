"""价格同步模块 - 同步最新价格和日涨幅"""

import yaml
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..feishu import FeishuClient, BitableClient
from ..tushare_api import TushareDataFetcher
from ..tushare_api.fetcher import normalize_code
from ..utils import RateLimiter


@dataclass
class PriceSyncResult:
    """价格同步结果"""
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
        print("📊 价格同步报告")
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


class PriceSynchronizer:
    """价格数据同步器"""

    def __init__(self, config_path: str = "config/config_price.yaml"):
        self.config = self._load_config(config_path)
        self._init_clients()
        self.result = PriceSyncResult()

        # 配置
        self.field_mapping = self.config.get("field_mapping", {})
        self.history_days = self.config.get("sync", {}).get("history_days", 5)
        self.code_column = self.config["feishu"]["bitable"].get("code_column", "代码")
        self.type_column = self.config["feishu"]["bitable"].get("type_column", "股票类型")
        self.status_column = self.config["feishu"]["bitable"].get("status_column", "交易状态")
        self.hold_status = self.config["feishu"]["bitable"].get("hold_status", "持仓")

        # 速率限制器
        rate_limit_config = self.config.get("rate_limit", {})
        self.rate_limiter = RateLimiter(rate_limit_config)

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
            cache_enabled=cache_config.get("enabled", False)
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

    def _map_fields(self, price_data: Dict) -> Dict:
        """
        将价格数据映射到飞书字段

        Args:
            price_data: 包含 close, pct_chg, trade_date 的字典

        Returns:
            映射后的飞书字段字典
        """
        feishu_fields = {}

        for feishu_col, indicator_name in self.field_mapping.items():
            if indicator_name in price_data:
                value = price_data[indicator_name]
                if value is not None:
                    # 处理日期字段 - 转换为毫秒级时间戳（包含时分秒）
                    if indicator_name == "trade_date":
                        try:
                            # 使用当前时间，包含时分秒
                            now = datetime.now()
                            value = int(now.timestamp() * 1000)
                        except (ValueError, TypeError):
                            pass

                    # 处理涨幅字段 - 除以100转换为百分比
                    if indicator_name == "pct_chg":
                        value = value / 100

                    feishu_fields[feishu_col] = value

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
            status = fields.get(self.status_column, "")

            if code:
                # 标准化代码格式
                normalized_code = normalize_code(str(code))
                securities.append({
                    "record_id": record["record_id"],
                    "code": normalized_code,
                    "original_code": str(code),
                    "type": str(sec_type),
                    "status": str(status)
                })

        print(f"📋 共获取到 {len(securities)} 个证券")
        return securities

    def get_latest_price(self, ts_code: str, sec_type: str, retry_count: int = 0) -> Optional[Dict]:
        """
        获取最新价格数据

        Args:
            ts_code: 证券代码
            sec_type: 证券类型
            retry_count: 重试次数

        Returns:
            包含 close, pct_chg, trade_date 的字典，失败返回 None
        """
        max_retries = 2  # 最大重试次数

        try:
            # 获取最近几天的日线数据
            daily_df = self.tushare.get_daily_data(
                ts_code=ts_code,
                security_type=sec_type,
                days=self.history_days
            )

            if daily_df.empty:
                return None

            # 获取最新一条数据
            latest = daily_df.iloc[-1]

            # 提取价格信息
            price_data = {
                "close": float(latest.get("close", 0)),
                "pct_chg": float(latest.get("pct_chg", 0)),  # 日涨幅百分比
                "trade_date": str(latest.get("trade_date", ""))
            }

            return price_data

        except Exception as e:
            error_msg = str(e)

            # 检查是否是速率限制错误
            if "每分钟最多访问" in error_msg or "权限" in error_msg:
                if retry_count < max_retries:
                    wait_time = 60  # 等待60秒后重试
                    print(f"\n    ⚠️  速率限制，等待 {wait_time} 秒后重试...", end="")
                    time.sleep(wait_time)
                    return self.get_latest_price(ts_code, sec_type, retry_count + 1)

            print(f"\n    ❌ [ERROR] {ts_code}: {e}")
            self.result.add_error(ts_code, error_msg)
            return None

    def sync_all(self):
        """同步所有价格数据"""
        print("\n" + "=" * 60)
        print("🚀 开始同步价格数据")
        print("=" * 60)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. 获取证券列表
        securities = self.get_securities_from_feishu()

        if not securities:
            print("⚠️  没有需要同步的证券")
            return

        # 2. 处理每个证券
        print("\n📊 开始获取最新价格...")
        update_records = []

        for i, sec in enumerate(securities, 1):
            code = sec["code"]
            sec_type = sec["type"]
            status = sec["status"]
            print(f"  [{i}/{len(securities)}] 处理 {code} ({sec_type})...", end=" ")

            # 检查交易状态，只有持仓才更新
            if status != self.hold_status:
                self.result.skipped += 1
                print(f"⏭️  非持仓状态 ({status})")
                continue

            # 速率限制等待
            self.rate_limiter.wait_if_needed(code)

            price_data = self.get_latest_price(code, sec_type)

            if price_data is not None:
                # 映射字段
                feishu_fields = self._map_fields(price_data)

                if feishu_fields:
                    update_records.append({
                        "record_id": sec["record_id"],
                        "fields": feishu_fields
                    })
                    self.result.success += 1
                    print(f"✅ 价格: {price_data['close']}, 涨幅: {price_data['pct_chg']}%")
                else:
                    self.result.add_warning(code, "字段映射为空")
                    self.result.skipped += 1
                    print("⚠️  字段映射为空")
            else:
                self.result.add_warning(code, "未获取到价格数据")
                self.result.skipped += 1
                print("⚠️  无数据")

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


def sync_price(config_path: str = "config/config_price.yaml"):
    """价格同步入口函数"""
    synchronizer = PriceSynchronizer(config_path)
    synchronizer.sync_all()
