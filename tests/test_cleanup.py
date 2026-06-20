"""infrastructure.cleanup 模块的单元测试。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from agent.core.constants import DEFAULT_BASE_TIME
from infrastructure.cleanup import (
    CleanupResult,
    clean_images_in_dir,
    clean_logs_in_dir,
    cleanup_maafw_bak_logs,
    compute_cleanup_base_time,
    extract_datetime_from_image_name,
    extract_datetime_from_log_name,
)


class TestExtractDatetimeFromLogName:
    """extract_datetime_from_log_name 文件名解析测试。"""

    def test_valid_with_millisecond(self) -> None:
        """带毫秒的标准 maafw 日志名可解析。"""
        name = "maafw.bak.2025.06.20-12.34.56.789.log"
        dt = extract_datetime_from_log_name(name)
        assert dt == datetime(2025, 6, 20, 12, 34, 56, 789000)

    def test_valid_without_millisecond(self) -> None:
        """不带毫秒的日志名可解析。"""
        name = "maafw.bak.2025.06.20-12.34.56.log"
        dt = extract_datetime_from_log_name(name)
        assert dt == datetime(2025, 6, 20, 12, 34, 56, 0)

    def test_valid_date_only(self) -> None:
        """仅含日期的日志名默认时间为 23:59:59.999999。"""
        name = "maafw.bak.2025.06.20.log"
        dt = extract_datetime_from_log_name(name)
        assert dt == datetime(2025, 6, 20, 23, 59, 59, 999999)

    def test_invalid_wrong_prefix(self) -> None:
        """前缀不符合时返回 None。"""
        assert extract_datetime_from_log_name("other.2025.06.20.log") is None

    def test_invalid_time_components(self) -> None:
        """时间分量数量非法时返回 None。"""
        assert extract_datetime_from_log_name(
            "maafw.bak.2025.06.20-12.34.log"
        ) is None

    def test_invalid_non_numeric(self) -> None:
        """非数字日期时返回 None。"""
        assert extract_datetime_from_log_name(
            "maafw.bak.abc.def.ghi-12.34.56.789.log"
        ) is None


class TestExtractDatetimeFromImageName:
    """extract_datetime_from_image_name 文件名解析测试。"""

    def test_valid_with_millisecond(self) -> None:
        """带毫秒的图片名可解析。"""
        name = "2025.06.20-12.34.56.789.png"
        dt = extract_datetime_from_image_name(name)
        assert dt == datetime(2025, 6, 20, 12, 34, 56, 789000)

    def test_valid_without_millisecond(self) -> None:
        """不带毫秒的图片名可解析。"""
        name = "2025.06.20-12.34.56.jpg"
        dt = extract_datetime_from_image_name(name)
        assert dt == datetime(2025, 6, 20, 12, 34, 56, 0)

    def test_valid_with_suffix_before_extension(self) -> None:
        """扩展名前带下划线后缀时仍可解析。"""
        name = "2025.06.20-12.34.56.789_roi.png"
        dt = extract_datetime_from_image_name(name)
        assert dt == datetime(2025, 6, 20, 12, 34, 56, 789000)

    def test_invalid_time_components(self) -> None:
        """时间分量数量非法时返回 None。"""
        assert extract_datetime_from_image_name("2025.06.20-12.34.png") is None

    def test_invalid_no_datetime(self) -> None:
        """无法识别的文件名返回 None。"""
        assert extract_datetime_from_image_name("snapshot.png") is None


class TestComputeCleanupBaseTime:
    """compute_cleanup_base_time 基准时间计算测试。"""

    def _make_log(
        self, folder: Path, year: int, month: int, day: int
    ) -> Path:
        """在 folder 下创建一个 maafw.bak.YYYY.MM.DD.log 文件。"""
        name = f"maafw.bak.{year:04d}.{month:02d}.{day:02d}.log"
        path = folder / name
        path.write_text("log", encoding="utf-8")
        return path

    def test_empty_folder_returns_default(self) -> None:
        """无日志时返回 DEFAULT_BASE_TIME。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = compute_cleanup_base_time(Path(tmp))
            assert result == DEFAULT_BASE_TIME

    def test_logs_not_exceed_keep_count(self) -> None:
        """日志数量不超过 keep_count 时返回 DEFAULT_BASE_TIME。"""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._make_log(folder, 2025, 5, 3)
            self._make_log(folder, 2025, 5, 2)
            self._make_log(folder, 2025, 5, 1)
            result = compute_cleanup_base_time(folder, keep_count=3)
            assert result == DEFAULT_BASE_TIME

    def test_logs_exceed_keep_count(self) -> None:
        """日志数量超过 keep_count 时返回第 keep_count 个日志时间。"""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._make_log(folder, 2025, 5, 4)
            self._make_log(folder, 2025, 5, 3)
            self._make_log(folder, 2025, 5, 2)
            self._make_log(folder, 2025, 5, 1)
            self._make_log(folder, 2024, 12, 31)
            result = compute_cleanup_base_time(folder, keep_count=2)
            assert result == datetime(2025, 5, 2, 23, 59, 59, 999999)


class TestCleanupMaafwBakLogs:
    """cleanup_maafw_bak_logs 日志删除测试。"""

    def _make_log(
        self, folder: Path, year: int, month: int, day: int
    ) -> Path:
        """创建一个 maafw.bak.YYYY.MM.DD.log 文件。"""
        name = f"maafw.bak.{year:04d}.{month:02d}.{day:02d}.log"
        path = folder / name
        path.write_text("log", encoding="utf-8")
        return path

    def test_no_logs_returns_default(self) -> None:
        """无日志时返回 DEFAULT_BASE_TIME。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = cleanup_maafw_bak_logs(Path(tmp))
            assert result == DEFAULT_BASE_TIME

    def test_keep_all_logs(self) -> None:
        """日志数量不超过 keep_count 时不删除。"""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._make_log(folder, 2025, 5, 2)
            self._make_log(folder, 2025, 5, 1)
            result = cleanup_maafw_bak_logs(folder, keep_count=3)
            assert result == DEFAULT_BASE_TIME
            assert len(list(folder.glob("*.log"))) == 2

    def test_delete_old_logs(self) -> None:
        """删除旧日志并保留最新的 keep_count 个。"""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._make_log(folder, 2025, 5, 4)
            self._make_log(folder, 2025, 5, 3)
            self._make_log(folder, 2025, 5, 2)
            self._make_log(folder, 2025, 5, 1)

            result = cleanup_maafw_bak_logs(folder, keep_count=2)
            assert result == datetime(2025, 5, 2, 23, 59, 59, 999999)
            remaining = {p.name for p in folder.glob("*.log")}
            assert remaining == {
                "maafw.bak.2025.05.04.log",
                "maafw.bak.2025.05.03.log",
            }

    def test_unparseable_logs_are_skipped(self) -> None:
        """无法解析的日志被跳过，不会导致崩溃。"""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._make_log(folder, 2025, 5, 2)
            (folder / "maafw.bak.bad.log").write_text("log", encoding="utf-8")
            result = cleanup_maafw_bak_logs(folder, keep_count=2)
            assert result == DEFAULT_BASE_TIME


class TestCleanImagesInDir:
    """clean_images_in_dir 图片清理测试。"""

    def _make_image(
        self, folder: Path, name: str
    ) -> Path:
        """在 folder 下创建指定名称的图片文件。"""
        path = folder / name
        path.write_text("img", encoding="utf-8")
        return path

    def test_delete_old_images_and_skip_unparseable(self) -> None:
        """删除早于 base_time 的图片，跳过无法解析时间的图片。"""
        with tempfile.TemporaryDirectory() as tmp:
            debug_folder = Path(tmp)
            img_dir = debug_folder / "imgs"
            img_dir.mkdir()
            base_time = datetime(2025, 5, 1, 12, 0, 0, 0)

            self._make_image(
                img_dir, "2025.05.01-11.00.00.000.png"
            )
            self._make_image(
                img_dir, "2025.05.01-10.00.00.000.png"
            )
            self._make_image(
                img_dir, "2025.05.01-13.00.00.000.png"
            )
            self._make_image(img_dir, "bad.png")
            self._make_image(img_dir, "readme.txt")

            result = clean_images_in_dir(debug_folder, "imgs", base_time)
            assert result == CleanupResult(scanned=4, deleted=2, skipped=1)
            remaining = {p.name for p in img_dir.iterdir()}
            assert remaining == {
                "2025.05.01-13.00.00.000.png",
                "bad.png",
                "readme.txt",
            }

    def test_missing_dir_returns_empty_result(self) -> None:
        """子目录不存在时返回空结果且不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = clean_images_in_dir(
                Path(tmp), "not_exist", DEFAULT_BASE_TIME
            )
            assert result == CleanupResult()


class TestCleanLogsInDir:
    """clean_logs_in_dir 日志清理测试。"""

    def test_delete_old_daily_logs_and_skip_unparseable(self) -> None:
        """删除早于 base_time 日期的日志，跳过无法解析日期的日志。"""
        with tempfile.TemporaryDirectory() as tmp:
            debug_folder = Path(tmp)
            log_dir = debug_folder / "logs"
            log_dir.mkdir()
            base_time = datetime(2025, 5, 1, 12, 0, 0, 0)

            (log_dir / "2025-04-30.log").write_text("old", encoding="utf-8")
            (log_dir / "2025-05-01.log").write_text("same", encoding="utf-8")
            (log_dir / "2025-05-02.log").write_text("new", encoding="utf-8")
            (log_dir / "bad.log").write_text("bad", encoding="utf-8")

            result = clean_logs_in_dir(debug_folder, "logs", base_time)
            assert result == CleanupResult(scanned=4, deleted=1, skipped=1)
            remaining = {p.name for p in log_dir.iterdir()}
            assert remaining == {
                "2025-05-01.log",
                "2025-05-02.log",
                "bad.log",
            }

    def test_missing_dir_returns_empty_result(self) -> None:
        """子目录不存在时返回空结果且不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = clean_logs_in_dir(
                Path(tmp), "not_exist", DEFAULT_BASE_TIME
            )
            assert result == CleanupResult()


class _FakeGlobPath:
    """用于触发 compute_cleanup_base_time 异常的伪路径对象。"""

    def glob(self, pattern: str) -> Any:
        raise OSError("boom")


class TestCleanupExceptionHandling:
    """清理函数异常处理测试。"""

    def test_compute_cleanup_base_time_on_error(self) -> None:
        """compute_cleanup_base_time 异常时调用 on_error 且不崩溃。"""
        errors: list[Exception] = []
        result = compute_cleanup_base_time(
            cast(Path, _FakeGlobPath()), on_error=errors.append
        )
        assert result == DEFAULT_BASE_TIME
        assert len(errors) == 1
        assert isinstance(errors[0], OSError)
