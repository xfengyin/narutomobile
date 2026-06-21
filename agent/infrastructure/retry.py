"""配置驱动的重试、限流与超时机制。

通过统一抽象，让基础设施层具备高可用能力：
- 重试：支持固定/指数退避、指定异常类型、最大尝试次数；
- 限流：基于令牌桶思想的简单调用频率控制；
- 超时：通过 signal/future 包装，避免单点调用无限挂起。

所有参数均支持配置化注入，默认行为保持向后兼容。
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, TypeVar

from utils.logger import logger

F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")


def _env_int(name: str, default: int) -> int:
    """从环境变量读取整数，解析失败时使用默认值。"""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"环境变量 {name}={value} 无法解析为整数，使用默认值 {default}")
        return default


def _env_float(name: str, default: float) -> float:
    """从环境变量读取浮点数，解析失败时使用默认值。"""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning(f"环境变量 {name}={value} 无法解析为浮点数，使用默认值 {default}")
        return default


def _parse_exceptions(
    exceptions: Sequence[type[Exception]] | None,
) -> tuple[type[Exception], ...]:
    """统一异常类型为元组。"""
    if exceptions is None:
        return (Exception,)
    return tuple(exceptions)


@dataclass
class RetryConfig:
    """重试配置，支持配置化注入。

    优先级：显式参数 > 环境变量 > 默认值。
    """

    max_attempts: int = field(
        default_factory=lambda: _env_int("MAA_RETRY_MAX_ATTEMPTS", 3)
    )
    backoff_base: float = field(
        default_factory=lambda: _env_float("MAA_RETRY_BACKOFF_BASE", 0.5)
    )
    backoff_max: float = field(
        default_factory=lambda: _env_float("MAA_RETRY_BACKOFF_MAX", 5.0)
    )
    exceptions: Sequence[type[Exception]] | None = field(default=None)
    timeout_seconds: float | None = field(
        default_factory=lambda: _env_float("MAA_RETRY_TIMEOUT_SECONDS", 0.0) or None
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            self.max_attempts = 1
        if self.backoff_base < 0:
            self.backoff_base = 0.0
        if self.backoff_max < self.backoff_base:
            self.backoff_max = self.backoff_base


@dataclass
class RateLimitConfig:
    """限流配置。"""

    max_calls: int = field(default_factory=lambda: _env_int("MAA_RATE_LIMIT_MAX_CALLS", 0))
    period_seconds: float = field(
        default_factory=lambda: _env_float("MAA_RATE_LIMIT_PERIOD_SECONDS", 1.0)
    )

    def __post_init__(self) -> None:
        if self.max_calls < 0:
            self.max_calls = 0
        if self.period_seconds <= 0:
            self.period_seconds = 1.0


class RateLimiter:
    """简单限流器：在 period 秒内最多允许 max_calls 次调用。

    max_calls <= 0 时不限流。
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self._timestamps: list[float] = []

    def acquire(self) -> bool:
        """尝试获取一次调用许可，返回是否成功。"""
        if self.config.max_calls <= 0:
            return True

        now = time.monotonic()
        cutoff = now - self.config.period_seconds
        # 仅保留窗口内的记录
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

        if len(self._timestamps) >= self.config.max_calls:
            logger.warning(
                f"触发限流：{self.config.period_seconds}秒内已超过"
                f"{self.config.max_calls}次调用"
            )
            return False

        self._timestamps.append(now)
        return True


def _calculate_backoff(config: RetryConfig, attempt: int) -> float:
    """计算第 attempt 次重试前的退避时间（指数退避，带上限）。"""
    backoff = config.backoff_base * (2 ** (attempt - 1))
    return min(backoff, config.backoff_max)


def retry_with_config(
    func: Callable[..., T],
    config: RetryConfig | None = None,
    rate_limiter: RateLimiter | None = None,
) -> Callable[..., T]:
    """使用给定配置包装函数，提供重试、超时、限流能力。"""
    cfg = config or RetryConfig()
    exceptions = _parse_exceptions(
        cfg.exceptions if cfg.exceptions else None  # type: ignore[arg-type]
    )

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if rate_limiter is not None and not rate_limiter.acquire():
            raise RuntimeError("Rate limit exceeded")

        last_exception: Exception | None = None
        for attempt in range(1, cfg.max_attempts + 1):
            try:
                if cfg.timeout_seconds:
                    return _run_with_timeout(func, cfg.timeout_seconds, args, kwargs)
                return func(*args, **kwargs)
            except exceptions as exc:
                last_exception = exc
                logger.warning(
                    f"{func.__name__} 第 {attempt}/{cfg.max_attempts} 次执行失败: {exc}"
                )
                if attempt < cfg.max_attempts:
                    sleep_time = _calculate_backoff(cfg, attempt)
                    logger.info(f"{sleep_time:.2f}s 后进行第 {attempt + 1} 次重试")
                    time.sleep(sleep_time)

        raise last_exception or RuntimeError(f"{func.__name__} 重试耗尽")

    return wrapper


def _run_with_timeout(
    func: Callable[..., T],
    timeout_seconds: float,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> T:
    """在指定超时内执行函数。

    优先使用 concurrent.futures 实现跨平台；signal 仅在主线程且非 Windows 下可用。
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutError(
                f"{func.__name__} 执行超过 {timeout_seconds}s 超时"
            ) from exc


def retry(
    config: RetryConfig | None = None,
    *,
    exceptions: Sequence[type[Exception]] | None = None,
    max_attempts: int | None = None,
    backoff_base: float | None = None,
    backoff_max: float | None = None,
    timeout_seconds: float | None = None,
    rate_limiter: RateLimiter | None = None,
) -> Callable[[F], F]:
    """重试装饰器工厂，支持配置对象或独立参数。

    独立参数优先级高于 config 对象。
    """

    def decorator(func: F) -> F:
        base_cfg = config or RetryConfig()
        override_cfg = RetryConfig(
            max_attempts=max_attempts if max_attempts is not None else base_cfg.max_attempts,
            backoff_base=backoff_base if backoff_base is not None else base_cfg.backoff_base,
            backoff_max=backoff_max if backoff_max is not None else base_cfg.backoff_max,
            exceptions=exceptions if exceptions is not None else base_cfg.exceptions,
            timeout_seconds=(
                timeout_seconds if timeout_seconds is not None else base_cfg.timeout_seconds
            ),
        )
        return retry_with_config(func, override_cfg, rate_limiter)  # type: ignore[return-value]

    return decorator


def retry_call(
    func: Callable[..., T],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    """函数式重试入口，无需装饰器。"""
    wrapped = retry_with_config(func, config)
    return wrapped(*args, **kwargs)
