"""日志与图片清理基础设施。"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from agent.core.constants import DEFAULT_BASE_TIME, DEFAULT_KEEP_LOG_COUNT, IMAGE_EXTENSIONS
from infrastructure.common import traced
from utils.logger import logger


@dataclass
class CleanupResult:
    """清理操作结果统计。"""

    scanned: int = 0
    deleted: int = 0
    skipped: int = 0
    errors: int = 0


def extract_datetime_from_log_name(filename: str) -> datetime | None:
    """从 maafw.bak.*.log 文件名中提取 datetime。"""
    try:
        middle = filename.replace("maafw.bak.", "").replace(".log", "")
        if "-" in middle:
            date_part, time_part = middle.split("-", maxsplit=1)
            year, month, day = date_part.split(".")
            time_components = time_part.split(".")
            if len(time_components) == 4:
                hour, minute, second, millisecond = time_components
            elif len(time_components) == 3:
                hour, minute, sec_ms = time_components
                if "." in sec_ms:
                    second, millisecond = sec_ms.rsplit(".", maxsplit=1)
                else:
                    second = sec_ms
                    millisecond = "0"
            else:
                return None
            microsecond = int(millisecond.ljust(6, "0")[:6])
            return datetime(
                int(year),
                int(month),
                int(day),
                int(hour),
                int(minute),
                int(second),
                microsecond,
            )
        else:
            date_str = middle.rstrip(".")
            parts = date_str.split(".")
            if len(parts) == 3:
                year, month, day = parts
                return datetime(int(year), int(month), int(day), 23, 59, 59, 999999)
            return None
    except Exception:
        return None


def extract_datetime_from_image_name(filename: str) -> datetime | None:
    """从图片文件名中提取 datetime。"""
    try:
        stem = filename.rsplit(".", maxsplit=1)[0]
        base = stem.split("_", maxsplit=1)[0]
        date_part, time_part = base.split("-", maxsplit=1)
        year, month, day = date_part.split(".")
        time_components = time_part.split(".")
        if len(time_components) == 4:
            hour, minute, second, millisecond = time_components
        elif len(time_components) == 3:
            hour, minute, sec_ms = time_components
            if "." in sec_ms:
                second, millisecond = sec_ms.rsplit(".", maxsplit=1)
            else:
                second = sec_ms
                millisecond = "0"
        else:
            return None
        microsecond = int(millisecond.ljust(6, "0")[:6])
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
            microsecond,
        )
    except Exception:
        return None


@traced
def compute_cleanup_base_time(
    debug_folder: Path,
    keep_count: int = DEFAULT_KEEP_LOG_COUNT,
    on_error: Callable[[Exception], None] | None = None,
) -> datetime:
    """计算图片/日志清理应使用的基准时间，不执行删除。"""
    trace_id = "N/A"
    try:
        log_files = list(debug_folder.glob("maafw.bak.*.log"))
        logs_with_time = [
            (dt, path)
            for path in log_files
            if (dt := extract_datetime_from_log_name(path.name)) is not None
        ]
        if not logs_with_time:
            return DEFAULT_BASE_TIME

        logs_with_time.sort(key=lambda x: x[0], reverse=True)
        if len(logs_with_time) <= keep_count:
            return DEFAULT_BASE_TIME
        return logs_with_time[keep_count][0]
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] compute_cleanup_base_time 异常")
        if on_error is not None:
            on_error(exc)
        return DEFAULT_BASE_TIME


@traced
def cleanup_maafw_bak_logs(
    debug_folder: Path,
    keep_count: int = DEFAULT_KEEP_LOG_COUNT,
    on_error: Callable[[Exception], None] | None = None,
) -> datetime:
    """清理旧的 maafw.bak.*.log 文件，保留最新的 keep_count 个。"""
    trace_id = "N/A"
    try:
        log_files = list(debug_folder.glob("maafw.bak.*.log"))
        logger.info(f"[trace_id={trace_id}] [日志清理] 找到日志总数: {len(log_files)}")
        if not log_files:
            logger.info(f"[trace_id={trace_id}] [日志清理] 无符合格式的日志，跳过")
            return DEFAULT_BASE_TIME

        logs_with_time = []
        for log_path in log_files:
            dt = extract_datetime_from_log_name(log_path.name)
            if dt:
                logs_with_time.append((dt, log_path))
            else:
                logger.warning(f"[trace_id={trace_id}] [日志清理] 无法解析日志时间,跳过: {log_path.name}")

        if not logs_with_time:
            logger.info(f"[trace_id={trace_id}] [日志清理] 所有日志均无法解析时间,跳过")
            return DEFAULT_BASE_TIME

        logs_with_time.sort(key=lambda x: x[0], reverse=True)
        to_delete_logs = logs_with_time[keep_count:]

        if not to_delete_logs:
            logger.info(f"[trace_id={trace_id}] [日志清理] 没有需要删除的日志")
            return DEFAULT_BASE_TIME

        logger.info(f"[trace_id={trace_id}] [日志清理] 待删除旧日志: {len(to_delete_logs)} 个")
        for dt, log_path in to_delete_logs:
            try:
                log_path.unlink()
                logger.info(f"[trace_id={trace_id}] [日志清理] 已删除: {log_path.name} (时间 {dt})")
            except Exception as e:
                logger.error(f"[trace_id={trace_id}] [日志清理] 删除失败 {log_path.name}: {e}")

        deleted_latest = to_delete_logs[0][0]
        logger.info(f"[trace_id={trace_id}] [日志清理] 被删除日志中最晚时间: {deleted_latest}")
        return deleted_latest
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] cleanup_maafw_bak_logs 异常")
        if on_error is not None:
            on_error(exc)
        return DEFAULT_BASE_TIME


@traced
def clean_images_in_dir(
    debug_folder: Path,
    sub_dir: str,
    base_time: datetime,
    on_error: Callable[[Exception], None] | None = None,
) -> CleanupResult:
    """清理指定子目录下图片时间早于 base_time 的文件。"""
    trace_id = "N/A"
    result = CleanupResult()
    try:
        target_dir = debug_folder / sub_dir
        if not target_dir.exists():
            logger.info(f"[trace_id={trace_id}] [图片清理] 目录不存在,跳过: {target_dir}")
            return result

        img_files = [
            f
            for f in target_dir.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        ]
        result.scanned = len(img_files)
        if result.scanned == 0:
            logger.info(f"[trace_id={trace_id}] [图片清理] {sub_dir} 目录下无图片文件,跳过")
            return result

        to_delete = []
        for img_path in img_files:
            img_dt = extract_datetime_from_image_name(img_path.name)
            if img_dt is None:
                result.skipped += 1
                logger.warning(f"[trace_id={trace_id}] [图片清理] 无法解析图片时间,跳过: {img_path.name}")
                continue
            if img_dt < base_time:
                to_delete.append((img_dt, img_path))

        for img_dt, img_path in to_delete:
            try:
                img_path.unlink()
                result.deleted += 1
                logger.info(f"[trace_id={trace_id}] [图片清理] 删除图片: {img_path.name} (时间 {img_dt})")
            except Exception as e:
                result.errors += 1
                logger.error(f"[trace_id={trace_id}] [图片清理] 删除失败 {img_path.name}: {e}")

        logger.info(
            f"[trace_id={trace_id}] [图片清理] {sub_dir} 目录下共有 {result.scanned} 张图片,"
            f"其中时间早于 {base_time} 的有 {len(to_delete)} 张,实际删除了 {result.deleted} 张"
        )
        return result
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] clean_images_in_dir 异常")
        if on_error is not None:
            on_error(exc)
        return result


@traced
def clean_logs_in_dir(
    debug_folder: Path,
    sub_dir: str,
    base_time: datetime,
    on_error: Callable[[Exception], None] | None = None,
) -> CleanupResult:
    """清理指定子目录下日期早于 base_time 的 YYYY-MM-DD.log 文件。"""
    trace_id = "N/A"
    result = CleanupResult()
    try:
        target_dir = debug_folder / sub_dir
        if not target_dir.exists():
            logger.info(f"[trace_id={trace_id}] [日志清理] 目录不存在,跳过: {target_dir}")
            return result

        log_files = list(target_dir.glob("*.log"))
        result.scanned = len(log_files)
        if result.scanned == 0:
            logger.info(f"[trace_id={trace_id}] [日志清理] {sub_dir} 目录下无日志文件,跳过")
            return result

        base_date = base_time.date()
        to_delete = []
        for log_path in log_files:
            log_date = _extract_date_from_log_name(log_path.name)
            if log_date is None:
                result.skipped += 1
                logger.warning(f"[trace_id={trace_id}] [日志清理] 无法解析日志日期,跳过: {log_path.name}")
                continue
            if log_date < base_date:
                to_delete.append((log_date, log_path))

        for log_date, log_path in to_delete:
            try:
                log_path.unlink()
                result.deleted += 1
                logger.info(f"[trace_id={trace_id}] [日志清理] 删除日志: {log_path.name} (日期 {log_date})")
            except Exception as e:
                result.errors += 1
                logger.error(f"[trace_id={trace_id}] [日志清理] 删除失败 {log_path.name}: {e}")

        logger.info(
            f"[trace_id={trace_id}] [日志清理] {sub_dir} 目录下共有 {result.scanned} 个日志文件,"
            f"其中日期早于 {base_date} 的有 {len(to_delete)} 个,实际删除了 {result.deleted} 个"
        )
        return result
    except Exception as exc:
        logger.exception(f"[trace_id={trace_id}] clean_logs_in_dir 异常")
        if on_error is not None:
            on_error(exc)
        return result


def _extract_date_from_log_name(filename: str) -> date | None:
    """从 YYYY-MM-DD.log 文件名中提取日期。"""
    try:
        date_str = filename.replace(".log", "")
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None
