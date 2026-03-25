"""速率限制工具类 - 用于处理API请求频率限制"""

import time
from typing import Dict, Optional


class RateLimiter:
    """
    速率限制器

    用于控制不同类型API的请求频率，防止触发速率限制
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化速率限制器

        Args:
            config: 速率限制配置字典，格式：
                {
                    "hk_stock_interval": 31,  # 港股请求间隔(秒)
                    # 可扩展其他类型...
                }
        """
        config = config or {}
        self.hk_stock_interval = config.get("hk_stock_interval", 31)
        self.last_hk_request_time = 0.0
        self.hk_request_count = 0

    def is_hk_stock(self, ts_code: str) -> bool:
        """
        判断是否是港股

        Args:
            ts_code: 证券代码

        Returns:
            是否为港股
        """
        return ts_code.endswith(".HK")

    def wait_if_needed(self, ts_code: str) -> bool:
        """
        根据证券类型进行速率限制等待

        Args:
            ts_code: 证券代码

        Returns:
            是否进行了等待
        """
        if not self.is_hk_stock(ts_code):
            return False

        current_time = time.time()

        # 第一个港股请求也需要等待，防止之前有其他请求触发限制
        if self.hk_request_count == 0:
            self._wait(self.hk_stock_interval, "港股首次请求")
        else:
            elapsed = current_time - self.last_hk_request_time
            if elapsed < self.hk_stock_interval:
                wait_time = self.hk_stock_interval - elapsed
                self._wait(wait_time, "港股速率限制")

        self.last_hk_request_time = time.time()
        self.hk_request_count += 1
        return True

    def _wait(self, seconds: float, reason: str = ""):
        """
        等待指定时间

        Args:
            seconds: 等待秒数
            reason: 等待原因（用于日志）
        """
        print(f"\n    ⏳ {reason}，等待 {seconds:.1f} 秒...", end="")
        time.sleep(seconds)

    def reset(self):
        """重置计数器（用于新的同步周期）"""
        self.last_hk_request_time = 0.0
        self.hk_request_count = 0
