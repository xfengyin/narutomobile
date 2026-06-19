"""模拟点击、滑动等输入操作基础设施。"""

from random import randint
from time import sleep

import random
from maa.context import Context


def click(context: Context, x: int, y: int, w: int = 1, h: int = 1) -> None:
    """在指定区域内随机点击。"""
    context.tasker.controller.post_click(
        random.randint(x, x + w - 1), random.randint(y, y + h - 1)
    ).wait()


def wait_for_freezes(context: Context, wait_ms: int = 200) -> None:
    """等待屏幕静止。"""
    context.run_task(
        "wait_for_freezes", {"wait_for_freezes": {"wait_for_freezes": wait_ms}}
    )


def click_and_wait_for_freezes(
    context: Context,
    x: int,
    y: int,
    w: int = 1,
    h: int = 1,
    post_wait_freezes: int = 200,
) -> None:
    """点击并等待屏幕静止。"""
    context.run_task(
        "click_and_wait_for_freezes",
        {
            "click_and_wait_for_freezes": {
                "target": [x, y, w, h],
                "post_wait_freezes": post_wait_freezes,
            }
        },
    )


def fast_swipe(
    context: Context,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: int = 300,
    end_hold: bool = True,
    after_swipe_delay: int = 300,
) -> None:
    """快速滑动屏幕。"""
    context.run_action(
        "custom_swipe",
        pipeline_override={
            "custom_swipe": {
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
) -> None:
    """非线性滑动屏幕。"""
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
        "custom_swipe",
        pipeline_override={
            "custom_swipe": {
                "action": "Swipe",
                "begin": [s_x, s_y],
                "end": points,
                "end_hold": hold_time,
                "duration": dur_list,
            }
        },
    )
    sleep(after_swipe_delay / 1000)
