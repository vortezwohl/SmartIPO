"""扩展能力包。

该包用于存放独立于基础文本模型之外的扩展能力封装。当前主要提供
FMP 美股 IPO / 估值研究客户端，供上层按需导入和组合。
"""

from src.ext.fmp import FmpClient, create_fmp_client

__all__ = [
    "FmpClient",
    "create_fmp_client",
]
