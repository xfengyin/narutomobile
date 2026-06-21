"""日志基础设施，使用 loguru 提供结构化日志输出。"""

from pathlib import Path
import sys

from loguru import logger as _logger

from agent.infrastructure._config import root

# 默认日志目录使用绝对路径
log_dir: Path = root / "debug" / "custom"


def setup_logger(log_dir: Path = log_dir, console_level: str = "INFO") -> type[_logger]:
    """
    配置 loguru 日志器，同时输出到控制台和文件。

    Args:
        log_dir: 日志文件存储目录。
        console_level: 控制台日志级别（如 "DEBUG", "INFO", "WARNING", "ERROR"）。
    """
    _logger.remove()  # 移除默认 logger

    # 定义日志级别的简短格式标签
    def format_level(record) -> bool:
        level_map = {
            "INFO": "info",
            "ERROR": "err",
            "WARNING": "warn",
            "DEBUG": "debug",
            "CRITICAL": "critical",
            "SUCCESS": "success",
            "TRACE": "trace",
        }
        record["extra"]["level_short"] = level_map.get(
            record["level"].name, record["level"].name.lower()
        )
        return True

    _logger.add(
        sys.stdout,
        format="<level>{extra[level_short]}</level>:<level>{message}</level>",
        colorize=True,
        level=console_level,
        filter=format_level,
    )

    log_dir.mkdir(parents=True, exist_ok=True)
    _logger.add(
        log_dir / "{time:YYYY-MM-DD}.log",
        rotation="00:00",  # 午夜轮转
        retention="2 weeks",  # 保留两周
        compression="zip",  # 压缩旧日志
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{line} | {message}",
        encoding="utf-8",
        enqueue=True,  # 线程安全
        backtrace=True,  # 包含堆栈跟踪
        diagnose=True,  # 显示诊断信息
    )

    return _logger


def change_console_level(level: str = "DEBUG") -> None:
    """动态修改控制台日志等级。"""
    setup_logger(console_level=level)
    _logger.info(f"控制台日志等级已更改为: {level}")


# 模块级初始化：确保任何地方导入 logger 都已配置完毕
logger: type[_logger] = setup_logger()
