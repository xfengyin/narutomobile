"""基础设施层：封装与 MaaFramework、OS、文件系统等底层交互。

公共 API:
    logger         -- loguru 日志实例
    log_dir       -- 日志文件存储目录
    counter       -- 操作计数器单例
    INFRA_EXCEPTIONS  -- 统一异常类型元组
    get_project_root()  -- 获取项目根目录
    load_json()   -- 读取 JSON（带缓存）
    write_json_safe()   -- 安全写入 JSON
    traced()      -- trace 装饰器
"""

from agent.infrastructure.logger import logger, log_dir
from agent.infrastructure.counter import counter, Counter
from agent.infrastructure.common import (
    INFRA_EXCEPTIONS,
    get_project_root,
    load_json,
    write_json_safe,
    traced,
)

__all__ = [
    "logger",
    "log_dir",
    "counter",
    "Counter",
    "INFRA_EXCEPTIONS",
    "get_project_root",
    "load_json",
    "write_json_safe",
    "traced",
]
