"""滑动搜索通用基础设施。

将"滑动-识别"循环抽象为可配置、可复用的组件，避免在业务动作中重复实现。
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from maa.context import Context

from utils.logger import logger

T = TypeVar("T")


@dataclass
class SwipeSearchStep:
    """单次滑动步骤配置。"""

    name: str
    swipe_action: Callable[[], None]


class SwipeSearch(Generic[T]):
    """滑动搜索器：在多次滑动之间执行识别，命中后返回结果。

    典型使用场景：
    - 主界面左右滑动查找功能入口
    - 忍界指引列表上下滑动查找目标
    """

    def __init__(
        self,
        context: Context,
        recognizer: Callable[[], T | None],
        steps: Sequence[SwipeSearchStep],
        max_attempts: int = 20,
    ) -> None:
        self.context = context
        self.recognizer = recognizer
        self.steps = list(steps)
        self.max_attempts = max_attempts

    def _is_stopping(self) -> bool:
        return bool(getattr(self.context.tasker, "stopping", False))

    def _check_stop(self, message: str = "任务停止，提前退出") -> bool:
        if self._is_stopping():
            logger.info(message)
            return True
        return False

    def search(self) -> T | None:
        """执行滑动搜索，命中则返回识别结果，否则返回 None。"""
        # 先尝试直接识别
        result = self.recognizer()
        if result is not None:
            return result

        for attempt in range(self.max_attempts):
            if self._check_stop():
                return None

            step_index = attempt % len(self.steps) if self.steps else 0
            step = self.steps[step_index]
            logger.info(f"[{step.name}] 第{attempt // len(self.steps) + 1}次滑动查找")
            step.swipe_action()

            if self._check_stop():
                return None

            result = self.recognizer()
            if result is not None:
                return result

        return None


def scroll_to_top(
    context: Context,
    recognizer: Callable[[], bool],
    swipe_action: Callable[[], None],
    max_attempts: int = 20,
) -> bool:
    """滚动到列表顶部，直到识别器返回 True 或达到最大尝试次数。"""
    for attempt in range(max_attempts):
        if getattr(context.tasker, "stopping", False):
            logger.info("任务停止，提前退出")
            return False

        if recognizer():
            return True

        logger.info(f"滑动到最顶端 第{attempt + 1}次")
        swipe_action()

    return False
