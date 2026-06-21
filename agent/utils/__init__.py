"""utils 包：公共工具函数与类型。

注意：核心实现已迁移至 agent/infrastructure/，此处保留为向后兼容重导出层。
推荐新代码直接导入：
    from agent.infrastructure.logger import logger
    from agent.infrastructure.counter import counter
"""

import json
from datetime import datetime
from pathlib import Path

# === 基础工具（定义保留在此，确保 utils/logger.py 的模块级初始化正常）===
root: Path = Path(__file__).resolve().parent.parent.parent
jL = json.load
jD = json.dump
logo: Path = (root / "docs" / "imgs" / "logo.png").absolute()


def get_format_timestamp() -> str:
    """返回格式化的带毫秒时间戳字符串，格式：YYYY.MM.DD-HH.MM.SS.mmm"""
    now = datetime.now()
    date = now.strftime("%Y.%m.%d")
    time_str = now.strftime("%H.%M.%S")
    milliseconds = f"{now.microsecond // 1000:03d}"
    return f"{date}-{time_str}.{milliseconds}"


# === 向后兼容重导出（核心实现迁移至 agent/infrastructure/）===
from agent.infrastructure.logger import logger
from agent.infrastructure.counter import counter

__all__ = [
    # 基础工具
    "root",
    "logo",
    "jL",
    "jD",
    "get_format_timestamp",
    # 重导出
    "logger",
    "counter",
]
