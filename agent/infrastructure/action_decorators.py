"""CustomAction run 方法统一装饰器，消除样板代码。"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from maa.custom_action import CustomAction
    from maa.context import Context

from infrastructure.common import INFRA_EXCEPTIONS

F = Callable[..., object]
T = TypeVar("T")


def action_run(
    on_success: str = "执行成功",
    on_error: str = "执行异常",
) -> Callable[[F], F]:
    """统一 action run 方法的装饰器。

    自动处理异常捕获、trace 日志、成功/失败结果返回。
    子类只需实现 _execute 方法。

    Args:
        on_success: 成功时的日志消息。
        on_error: 异常时的日志消息前缀。

    Example:
        ```python
        @AgentServer.custom_action("MyAction")
        class MyAction(CustomAction):
            @action_run(on_success="我的操作成功", on_error="我的操作异常")
            def _execute(self, context: Context, argv: CustomAction.RunArg) -> None:
                # 业务逻辑
                pass
        ```
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(
            self: CustomAction, context: Context, argv: CustomAction.RunArg
        ) -> CustomAction.RunResult:
            from utils.logger import logger

            trace_id = getattr(context, "trace_id", "N/A")
            try:
                func(self, context, argv)
                logger.info(f"[trace_id={trace_id}] {on_success}")
                return CustomAction.RunResult(success=True)
            except INFRA_EXCEPTIONS as exc:
                logger.error(f"[trace_id={trace_id}] {on_error}: {exc}")
                return CustomAction.RunResult(success=False)

        return wrapper  # type: ignore[return-value]

    return decorator
