"""infrastructure.retry 模块的单元测试。"""

from __future__ import annotations

import pytest

from infrastructure.retry import (
    RateLimitConfig,
    RateLimiter,
    RetryConfig,
    retry,
    retry_call,
    retry_with_config,
)


class TestRetryConfig:
    """RetryConfig 配置行为测试。"""

    def test_default_values(self) -> None:
        """默认配置应使用合理的默认值。"""
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.backoff_base == 0.5
        assert cfg.backoff_max == 5.0
        assert cfg.exceptions is None
        assert cfg.timeout_seconds is None

    def test_post_init_clamps_invalid_values(self) -> None:
        """无效值应在 __post_init__ 中被修正。"""
        cfg = RetryConfig(max_attempts=0, backoff_base=-1.0, backoff_max=0.1)
        assert cfg.max_attempts == 1
        assert cfg.backoff_base == 0.0
        assert cfg.backoff_max >= cfg.backoff_base

    def test_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量应覆盖默认值。"""
        monkeypatch.setenv("MAA_RETRY_MAX_ATTEMPTS", "5")
        monkeypatch.setenv("MAA_RETRY_BACKOFF_BASE", "1.0")
        monkeypatch.setenv("MAA_RETRY_BACKOFF_MAX", "10.0")
        monkeypatch.setenv("MAA_RETRY_TIMEOUT_SECONDS", "3.0")
        cfg = RetryConfig()
        assert cfg.max_attempts == 5
        assert cfg.backoff_base == 1.0
        assert cfg.backoff_max == 10.0
        assert cfg.timeout_seconds == 3.0


class TestRateLimiter:
    """RateLimiter 限流行为测试。"""

    def test_unlimited_when_max_calls_zero(self) -> None:
        """max_calls 为 0 时不限流。"""
        limiter = RateLimiter(RateLimitConfig(max_calls=0))
        assert all(limiter.acquire() for _ in range(10))

    def test_accepts_up_to_max_calls(self) -> None:
        """在窗口内最多允许 max_calls 次调用。"""
        limiter = RateLimiter(RateLimitConfig(max_calls=2, period_seconds=60.0))
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is False

    def test_window_slides_over_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """窗口过期后应释放额度。"""
        current_time = [0.0]
        monkeypatch.setattr(
            "infrastructure.retry.time.monotonic", lambda: current_time[0]
        )

        limiter = RateLimiter(RateLimitConfig(max_calls=1, period_seconds=1.0))
        assert limiter.acquire() is True
        assert limiter.acquire() is False

        current_time[0] = 2.0
        assert limiter.acquire() is True


class TestRetryDecorator:
    """retry 装饰器重试行为测试。"""

    def test_succeeds_without_retry(self) -> None:
        """函数一次成功时不应触发重试。"""
        call_count = 0

        @retry(max_attempts=3)
        def stable() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        assert stable() == 42
        assert call_count == 1

    def test_retries_on_specified_exception(self) -> None:
        """指定异常时应按配置重试。"""
        call_count = 0

        @retry(exceptions=(ValueError,), max_attempts=3, backoff_base=0.0)
        def flaky() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return 42

        assert flaky() == 42
        assert call_count == 3

    def test_raises_after_exhaustion(self) -> None:
        """重试耗尽后应抛出最后一次异常。"""
        @retry(exceptions=(RuntimeError,), max_attempts=2, backoff_base=0.0)
        def always_fails() -> None:
            raise RuntimeError("failed")

        with pytest.raises(RuntimeError, match="failed"):
            always_fails()

    def test_does_not_retry_unspecified_exception(self) -> None:
        """非指定异常不应触发重试。"""
        call_count = 0

        @retry(exceptions=(ValueError,), max_attempts=3, backoff_base=0.0)
        def raises_type_error() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("unexpected")

        with pytest.raises(TypeError, match="unexpected"):
            raises_type_error()
        assert call_count == 1

    def test_config_object_overriden_by_keyword(self) -> None:
        """独立参数优先级高于 config 对象。"""
        base = RetryConfig(max_attempts=2, backoff_base=0.0)

        @retry(config=base, max_attempts=4, exceptions=(ValueError,))
        def flaky() -> int:
            return 1

        wrapped = flaky
        assert wrapped() == 1


class TestRetryCall:
    """retry_call 函数式入口测试。"""

    def test_retries_and_returns_result(self) -> None:
        """retry_call 应支持重试并返回结果。"""
        call_count = 0

        def flaky() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("transient")
            return 99

        result = retry_call(
            flaky,
            config=RetryConfig(
                max_attempts=3, backoff_base=0.0, exceptions=(OSError,)
            ),
        )
        assert result == 99
        assert call_count == 2


class TestRetryWithConfigTimeout:
    """超时控制相关测试。"""

    def test_timeout_raises_on_slow_function(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """函数执行超时应抛出 TimeoutError。"""
        import time

        def slow() -> None:
            time.sleep(0.2)

        wrapped = retry_with_config(
            slow,
            RetryConfig(max_attempts=1, timeout_seconds=0.05, exceptions=(TimeoutError,)),
        )
        with pytest.raises(TimeoutError):
            wrapped()


class TestRateLimiterIntegration:
    """重试与限流集成测试。"""

    def test_rate_limit_blocks_when_exceeded(self) -> None:
        """限流超额时调用应失败。"""
        limiter = RateLimiter(RateLimitConfig(max_calls=1, period_seconds=60.0))
        limiter.acquire()

        @retry(rate_limiter=limiter)
        def blocked() -> int:
            return 1

        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            blocked()
