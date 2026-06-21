"""OCR 识别相关基础设施。"""

import hashlib
from typing import Any, Callable, Iterable

from maa.context import Context
from maa.define import RectType
from numpy import ndarray

from infrastructure.common import traced
from utils.logger import logger


def _image_hash(image: ndarray) -> str:
    """计算图片的 MD5 hash，用于缓存 key。取中心区域降低 hash 计算开销。"""
    h, w = image.shape[:2]
    crop = image[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
    return hashlib.md5(crop.tobytes()).hexdigest()[:16]


_ocr_cache_store: dict[str, tuple[Any, ...]] = {}
_cache_hits = 0
_cache_misses = 0


def _make_cache_key(roi_hash: str, image_hash: str, expected_hash: str, roi: tuple[int, int, int, int] | tuple[int, ...]) -> str:
    """生成缓存 key。"""
    return f"{roi_hash}_{image_hash}_{expected_hash}_{roi}"


def ocr_with_cache(
    context: Context,
    image: ndarray,
    roi: tuple[int, int, int, int] | tuple[int, ...],
    expected: str | list[str] | None = None,
) -> tuple[Any, ...] | None:
    """执行 OCR 并使用缓存。返回 (reco_detail,) 或 None。"""
    if not isinstance(expected, Iterable):
        expected = [expected] if expected is not None else []
    expected_tuple = tuple(expected)

    roi_hash = hashlib.md5(str(roi).encode()).hexdigest()[:16]
    image_hash = _image_hash(image)
    expected_hash = hashlib.md5(str(expected_tuple).encode()).hexdigest()[:16]
    key = _make_cache_key(roi_hash, image_hash, expected_hash, roi)

    global _cache_hits, _cache_misses

    if key in _ocr_cache_store:
        _cache_hits += 1
        logger.debug(
            f"OCR 缓存命中: roi={roi}, image_hash={image_hash[:8]}, "
            f"total_hits={_cache_hits}, total_misses={_cache_misses}"
        )
        return _ocr_cache_store[key]

    _cache_misses += 1
    logger.debug(
        f"OCR 缓存未命中: roi={roi}, image_hash={image_hash[:8]}, "
        f"total_hits={_cache_hits}, total_misses={_cache_misses}"
    )

    reco_detail = context.run_recognition(
        "custom_ocr",
        image,
        {"custom_ocr": {"roi": roi, "expected": list(expected_tuple)}},
    )

    result = (reco_detail,)
    _ocr_cache_store[key] = result
    return result


def get_cache_stats() -> dict[str, int]:
    """获取缓存统计信息。"""
    global _cache_hits, _cache_misses
    return {
        "hits": _cache_hits,
        "misses": _cache_misses,
        "size": len(_ocr_cache_store),
    }


@traced
def fast_ocr(
    context: Context,
    expected: str | list[str],
    roi: tuple[int, int, int, int],
    absolutely: bool = False,
    screenshot_refresh: bool = True,
    on_error: Callable[[Exception], None] | None = None,
    cache: bool = True,
) -> RectType | None:
    """重新截图并进行 OCR 识别。

    Args:
        cache: 是否启用结果缓存，默认 True。
    """
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        if screenshot_refresh:
            context.tasker.controller.post_screencap().wait()
        if not isinstance(expected, Iterable):
            expected = [expected]

        if cache:
            image = context.tasker.controller.cached_image
            cached_result = ocr_with_cache(context, image, roi, expected)
            if cached_result is not None:
                reco_detail = cached_result[0]
            else:
                return None
        else:
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
            logger.debug(f"[trace_id={trace_id}] OCR 识别成功: {reco_detail.best_result.text}")
            return reco_detail.best_result.box

        filtered_texts = [
            res.text
            for res in reco_detail.filtered_results
        ]

        result = None
        logger.debug(f"[trace_id={trace_id}] OCR 绝对匹配尝试: {expected} in {filtered_texts}")
        for target in expected:
            if target in filtered_texts:
                result = next(
                    res
                    for res in reco_detail.filtered_results
                    if res.text == target
                )
                logger.debug(
                    f"[trace_id={trace_id}] OCR 绝对匹配成功: {target} in {reco_detail.filtered_results} with {result}"
                )
                break

        if result is not None:
            logger.debug(f"[trace_id={trace_id}] OCR 绝对匹配成功: {expected}")
            return result.box
        logger.debug(f"[trace_id={trace_id}] {expected} 绝对匹配失败：{reco_detail.filtered_results}")
        return None
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] fast_ocr 异常")
        if on_error is not None:
            on_error(exc)
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


@traced
def read_numbers(
    context: Context,
    image: ndarray,
    rois: Iterable[RoiLike],
    text_modifier=lambda x: x,
    on_error: Callable[[Exception], None] | None = None,
    cache: bool = True,
) -> list[int | None]:
    """在多个 ROI 上批量读取纯数字，使用同一张图片避免重复截图。

    Args:
        cache: 是否启用结果缓存，默认 True。
    """
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        return [read_number(context, image, roi, text_modifier, cache=cache) for roi in rois]
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] read_numbers 异常")
        if on_error is not None:
            on_error(exc)
        return []


@traced
def read_number(
    context: Context,
    image: ndarray,
    roi: RoiLike,
    text_modifier=lambda x: x,
    on_error: Callable[[Exception], None] | None = None,
    cache: bool = True,
) -> int | None:
    """在指定 ROI 内读取纯数字。

    Args:
        cache: 是否启用结果缓存，默认 True。
    """
    trace_id = getattr(context, "trace_id", "N/A")
    try:
        roi_tuple = tuple(roi) if not isinstance(roi, tuple) else roi

        if cache:
            cached_result = ocr_with_cache(context, image, roi_tuple, None)
            if cached_result is not None:
                reco_detail = cached_result[0]
            else:
                return None
        else:
            reco_detail = context.run_recognition(
                "custom_ocr", image, {"custom_ocr": {"roi": roi}}
            )

        if reco_detail is None or not reco_detail.hit:
            logger.warning(f"[trace_id={trace_id}] ROI{roi} 未识别到任何文本")
            return None

        source_text = str(reco_detail.best_result.text).strip()
        logger.debug(f"[trace_id={trace_id}] ROI{roi} 原始识别文本：{source_text}")

        modified_text = text_modifier(source_text)
        logger.debug(f"[trace_id={trace_id}] ROI{roi} 修改后识别文本：{modified_text}")

        number = parse_digits(modified_text)
        if number is None:
            logger.warning(
                f"[trace_id={trace_id}] ROI{roi} 未提取到有效数字，修改后文本：{modified_text}"
            )
            return None

        logger.info(f"[trace_id={trace_id}] ROI{roi} 解析到数字:{number}")
        return number
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] read_number 异常")
        if on_error is not None:
            on_error(exc)
        return None
