"""OCR 识别相关基础设施。"""

from typing import Iterable

from maa.context import Context
from maa.define import RectType
from numpy import ndarray

from utils.logger import logger


def fast_ocr(
    context: Context,
    expected: str | list[str],
    roi: tuple[int, int, int, int],
    absolutely: bool = False,
    screenshot_refresh: bool = True,
) -> RectType | None:
    """重新截图并进行 OCR 识别。"""
    if screenshot_refresh:
        context.tasker.controller.post_screencap().wait()
    if not isinstance(expected, Iterable):
        expected = [expected]

    reco_detail = context.run_recognition(
        "custom_ocr",
        context.tasker.controller.cached_image,
        {
            "custom_ocr": {
                "recognition": {
                    "type": "OCR",
                    "param": {"expected": expected, "roi": roi},
                }
            }
        },
    )
    if reco_detail is None:
        return None

    if reco_detail.hit is False or reco_detail.best_result is None:
        return None

    if not absolutely:
        logger.debug(f"OCR 识别成功: {reco_detail.best_result.text}")
        return reco_detail.best_result.box

    filtered_texts = [
        res.text
        for res in reco_detail.filtered_results
    ]

    result = None
    logger.debug(f"OCR 绝对匹配尝试: {expected} in {filtered_texts}")
    for target in expected:
        if target in filtered_texts:
            result = next(
                res
                for res in reco_detail.filtered_results
                if res.text == target
            )
            logger.debug(
                f"OCR 绝对匹配成功: {target} in {reco_detail.filtered_results} with {result}"
            )
            break

    if result is not None:
        logger.debug(f"OCR 绝对匹配成功: {expected}")
        return result.box
    logger.debug(f"{expected} 绝对匹配失败：{reco_detail.filtered_results}")
    return None


def parse_digits(source_text: str) -> int | None:
    """从 OCR 文本中提取第一个连续数字。"""
    import re
    num_match = re.search(r"\d+", source_text)
    if not num_match:
        return None
    try:
        return int(num_match.group())
    except ValueError:
        return None


RoiLike = tuple[int, int, int, int] | list[int]


def read_numbers(
    context: Context,
    image: ndarray,
    rois: Iterable[RoiLike],
    text_modifier=lambda x: x,
) -> list[int | None]:
    """在多个 ROI 上批量读取纯数字，使用同一张图片避免重复截图。"""
    return [read_number(context, image, roi, text_modifier) for roi in rois]


def read_number(
    context: Context,
    image: ndarray,
    roi: RoiLike,
    text_modifier=lambda x: x,
) -> int | None:
    """在指定 ROI 内读取纯数字。"""
    reco_detail = context.run_recognition(
        "custom_ocr", image, {"custom_ocr": {"roi": roi}}
    )

    if reco_detail is None or not reco_detail.hit:
        logger.warning(f"ROI{roi} 未识别到任何文本")
        return None

    source_text = str(reco_detail.best_result.text).strip()
    logger.debug(f"ROI{roi} 原始识别文本：{source_text}")

    modified_text = text_modifier(source_text)
    logger.debug(f"ROI{roi} 修改后识别文本：{modified_text}")

    number = parse_digits(modified_text)
    if number is None:
        logger.warning(
            f"ROI{roi} 未提取到有效数字，修改后文本：{modified_text}"
        )
        return None

    logger.info(f"ROI{roi} 解析到数字:{number}")
    return number
