"""基础设施公共能力：根目录解析、JSON 缓存、trace 日志、异常上报。"""

import copy
import os
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from utils import jD, jL, root
from utils.logger import logger

F = TypeVar("F", bound=Callable[..., Any])


def default_error_handler(exc: Exception) -> None:
    """默认异常处理器，调用方可通过 on_error 注入自定义上报逻辑。"""
    pass


def get_project_root(root_dir: Path | None = None) -> Path:
    """返回项目根目录，支持显式传入或环境变量注入。

    优先级：
        1. 函数参数 root_dir；
        2. 环境变量 PROJECT_ROOT；
        3. utils.root 默认值。
    """
    if root_dir is not None:
        return root_dir
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    return root


@lru_cache(maxsize=32)
def read_json_cached(file_path: Path) -> tuple[Any, ...]:
    """读取 JSON 文件并以 tuple 包装返回，便于缓存且 key 可哈希。"""
    with file_path.open(encoding="utf-8") as f:
        return (jL(f),)


def clear_json_cache() -> None:
    """清除 JSON 读取缓存，便于测试或热重载。"""
    read_json_cached.cache_clear()


def load_json(file_path: Path) -> Any:
    """读取 JSON 文件，返回深层拷贝避免缓存被意外修改。"""
    return copy.deepcopy(read_json_cached(file_path)[0])


def write_json_safe(file_path: Path, data: Any, indent: int = 4) -> None:
    """安全写入 JSON 文件，统一编码与格式。"""
    with file_path.open("w", encoding="utf-8") as f:
        jD(data, f, ensure_ascii=False, indent=indent)


def traced(
    func: F | None = None,
    *,
    name: str | None = None,
    trace_id_source: str = "context",
    trace_id_attr: str = "trace_id",
    default_trace_id: str = "MANUAL",
) -> Callable[..., Any] | F:
    """函数级 trace 装饰器。

    自动在入口/出口打印 info 日志，不捕获异常，由被装饰函数自行处理业务异常与上报。

    Args:
        func: 被装饰函数。
        name: trace 名称，默认使用函数名。
        trace_id_source: "context" 表示从第一个位置参数取 trace_id；
                         "manual" 表示不自动提取，使用 default_trace_id。
        trace_id_attr: 从 context 对象上读取 trace_id 的属性名。
        default_trace_id: manual 模式下的默认 trace_id。
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = name or f.__name__
            trace_id = "N/A"
            if trace_id_source == "context" and args:
                for arg in args:
                    candidate = getattr(arg, trace_id_attr, None)
                    if candidate is not None:
                        trace_id = candidate
                        break
            elif trace_id_source == "manual":
                trace_id = kwargs.get(trace_id_attr, default_trace_id)

            logger.info(f"[trace_id={trace_id}] {func_name} 开始")
            result = f(*args, **kwargs)
            logger.info(f"[trace_id={trace_id}] {func_name} 完成")
            return result

        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
