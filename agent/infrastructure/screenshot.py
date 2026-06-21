"""截图与分辨率相关基础设施。"""

import os
from pathlib import Path
from typing import Callable

from PIL import Image
from maa.context import Context

from infrastructure.common import INFRA_EXCEPTIONS, traced
from infrastructure.retry import retry
from utils import get_format_timestamp
from utils.logger import log_dir, logger
from core.constants import (
    ASPECT_RATIO_TOLERANCE_SCREENSHOT,
    RECOMMENDED_RESOLUTION,
    TARGET_ASPECT_RATIO,
)


@traced
@retry(exceptions=INFRA_EXCEPTIONS, max_attempts=2)
def save_screenshot(
    context: Context,
    save_dir: Path | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> Path | None:
    """保存当前屏幕截图到指定目录。"""
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        screen_array = context.tasker.controller.cached_image
        height, width = screen_array.shape[:2]
        aspect_ratio = width / height

        if abs(aspect_ratio - TARGET_ASPECT_RATIO) / TARGET_ASPECT_RATIO > ASPECT_RATIO_TOLERANCE_SCREENSHOT:
            logger.error(f"[trace_id={trace_id}] 当前模拟器分辨率不是16:9! 当前分辨率: {width}x{height}")

        # BGR2RGB
        if len(screen_array.shape) == 3 and screen_array.shape[2] == 3:
            rgb_array = screen_array[:, :, ::-1]
        else:
            rgb_array = screen_array
            logger.warning(f"[trace_id={trace_id}] 当前截图并非三通道")

        img = Image.fromarray(rgb_array)

        target_dir = save_dir or log_dir
        os.makedirs(target_dir, exist_ok=True)
        time_str = get_format_timestamp()
        file_path = target_dir / f"{time_str}.png"
        img.save(file_path)
        logger.info(f"[trace_id={trace_id}] 截图保存至 {file_path}")
        return file_path
    except INFRA_EXCEPTIONS as exc:
        logger.exception(f"[trace_id={trace_id}] 保存截图异常")
        if on_error is not None:
            on_error(exc)
        return None


@traced
def check_resolution(context: Context) -> None:
    """检查控制器分辨率是否为推荐 16:9。"""
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        resolution = context.tasker.controller.resolution
        if resolution[1] > resolution[0]:
            resolution = (resolution[1], resolution[0])
        if abs((resolution[0] / resolution[1]) - TARGET_ASPECT_RATIO) > ASPECT_RATIO_TOLERANCE_SCREENSHOT:
            logger.error(f"[trace_id={trace_id}] 你可能正在使用非推荐的分辨率！")
            logger.error(f"[trace_id={trace_id}] 推荐使用的分辨率：{RECOMMENDED_RESOLUTION[0]}x{RECOMMENDED_RESOLUTION[1]}")
            logger.error(f"[trace_id={trace_id}] 当前使用的分辨率：{resolution[0]}x{resolution[1]}")
    except INFRA_EXCEPTIONS:
        logger.exception(f"[trace_id={trace_id}] 检查分辨率异常")
