"""模拟点击、滑动等输入操作基础设施。"""

import random
from random import randint
from time import sleep
from typing import Callable

from maa.context import Context

from core.pipeline_names import (
    CLICK_AND_WAIT_FOR_FREEZES,
    CUSTOM_SWIPE,
    WAIT_FOR_FREEZES,
)
from infrastructure.common import traced
from utils.logger import logger


@traced
def click(
    context: Context,
    x: int,
    y: int,
    w: int = 1,
    h: int = 1,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """在指定区域内随机点击。"""
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        context.tasker.controller.post_click(
            random.randint(x, x + w - 1), random.randint(y, y + h - 1)
        ).wait()
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] click 异常, target=({x},{y},{w},{h})")
        if on_error is not None:
            on_error(exc)


@traced
def wait_for_freezes(context: Context, wait_ms: int = 200) -> None:
    """等待屏幕静止。"""
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        context.run_task(
            WAIT_FOR_FREEZES, {WAIT_FOR_FREEZES: {WAIT_FOR_FREEZES: wait_ms}}
        )
    except Exception:
        logger.exception(f"[trace_id={trace_id}] wait_for_freezes 异常")


@traced
def click_and_wait_for_freezes(
    context: Context,
    x: int,
    y: int,
    w: int = 1,
    h: int = 1,
    post_wait_freezes: int = 200,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """点击并等待屏幕静止。"""
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        context.run_task(
            CLICK_AND_WAIT_FOR_FREEZES,
            {
                CLICK_AND_WAIT_FOR_FREEZES: {
                    "target": [x, y, w, h],
                    "post_wait_freezes": post_wait_freezes,
                }
            },
        )
    except Exception as exc:
        logger.exception(
            f"[trace_id={trace_id}] click_and_wait_for_freezes 异常, target=({x},{y},{w},{h})"
        )
        if on_error is not None:
            on_error(exc)


@traced
def fast_swipe(
    context: Context,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: int = 300,
    end_hold: bool = True,
    after_swipe_delay: int = 300,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """快速滑动屏幕。"""
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        context.run_action(
            CUSTOM_SWIPE,
            pipeline_override={
                CUSTOM_SWIPE: {
                    # 疑似有闭包问题
                    # 采用手动随机而不是maafw自带的随机
                    "begin": [random.randint(start_x - 50, start_x + 50), start_y],
                    "end": [random.randint(end_x - 50, end_x + 50), end_y],
                    "duration": randint(duration - 100, duration + 100),
                    "end_hold": randint(100, 200) if end_hold else 0,
                }
            },
        )
        sleep(after_swipe_delay / 1000)
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] fast_swipe 异常")
        if on_error is not None:
            on_error(exc)


@traced
def nonlinear_swipe(
    context: Context,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: int = 150,
    end_hold: bool = False,
    after_swipe_delay: int = 300,
    steps: int = 7,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """非线性滑动屏幕。"""
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        s_x = random.randint(start_x - 50, start_x + 50)
        s_y = random.randint(start_y - 50, start_y + 50)
        e_x = random.randint(end_x - 50, end_x + 50)
        e_y = random.randint(end_y - 50, end_y + 50)
        total_dur = random.randint(duration - 100, duration + 100)
        hold_time = random.randint(100, 200) if end_hold else 0

        points = []
        dur_list = []
        total_prog = 0.0

        for i in range(1, steps + 1):
            t = i / steps
            prog = 1 - (1 - t) ** 2
            delta = prog - total_prog
            total_prog = prog

            curr_x = int(s_x + (e_x - s_x) * prog)
            curr_y = int(s_y + (e_y - s_y) * prog)
            points.append([curr_x, curr_y])
            dur_list.append(round(total_dur * delta))

        dur_list[-1] += total_dur - sum(dur_list)

        context.run_action(
            CUSTOM_SWIPE,
            pipeline_override={
                CUSTOM_SWIPE: {
                    "action": "Swipe",
                    "begin": [s_x, s_y],
                    "end": points,
                    "end_hold": hold_time,
                    "duration": dur_list,
                }
            },
        )
        sleep(after_swipe_delay / 1000)
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] nonlinear_swipe 异常")
        if on_error is not None:
            on_error(exc)
