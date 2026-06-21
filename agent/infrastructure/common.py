"""基础设施公共能力：根目录解析、JSON 缓存、trace 日志、异常上报。"""

import copy
import os
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from agent.infrastructure._config import jD, jL, root
from agent.infrastructure.logger import logger

F = TypeVar("F", bound=Callable[..., Any])

# 基础设施层统一捕获的异常集合，避免裸 except Exception 吞掉 SystemExit/KeyboardInterrupt。
INFRA_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    ValueError,
    TypeError,
    RuntimeError,
    AttributeError,
    IndexError,
    KeyError,
)


def get_project_root(root_dir: Path | None = None) -> Path:
    """返回项目根目录，支持显式传入或环境变量注入。

    优先级：
        1. 函数参数 root_dir；
        2. 环境变量 PROJECT_ROOT；
        3. _config.root 默认值。
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
    on_error: Callable[[Exception], None] | None = None,
) -> Callable[..., Any] | F:
    """函数级 trace 装饰器。

    自动在入口/出口打印 info 日志，异常时打印 exception 日志并调用 on_error 回调。

    Args:
        func: 被装饰函数。
        name: trace 名称，默认使用函数名。
        trace_id_source: "context" 表示从第一个位置参数取 trace_id；
                         "manual" 表示不自动提取，trace_id 显示为 MANUAL。
        trace_id_attr: 从 context 对象上读取 trace_id 的属性名。
        on_error: 异常回调，接收异常实例。
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = name or f.__name__
            trace_id = "N/A"
            if trace_id_source == "context" and args:
                trace_id = getattr(args[0], trace_id_attr, "N/A")
            elif trace_id_source == "manual":
                trace_id = kwargs.get(trace_id_attr, "MANUAL")

            logger.info(f"[trace_id={trace_id}] {func_name} 开始")
            try:
                result = f(*args, **kwargs)
                logger.info(f"[trace_id={trace_id}] {func_name} 完成")
                return result
            except Exception as exc:
                logger.exception(f"[trace_id={trace_id}] {func_name} 异常")
                if on_error is not None:
                    on_error(exc)
                raise

        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
