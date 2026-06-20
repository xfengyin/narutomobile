"""agent/custom/action.py 单元测试。"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from custom.action import (
    CounterIncrement,
    CleanupMaafwBakLogs,
    CleanupOnErrorImg,
    CleanupVisionImg,
    CleanupCustomImg,
    CleanupCustomLog,
    NonlinearSwipe,
    _get_debug_folder,
)
from core.constants import DEFAULT_KEEP_LOG_COUNT
from utils import counter


@pytest.fixture(autouse=True)
def _reset_counter() -> None:
    """每个用例前清空计数器，避免相互影响。"""
    counter.counter.reset()


def test_get_debug_folder_uses_project_root() -> None:
    """_get_debug_folder 应使用 get_project_root 而不是硬编码路径。"""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        with patch("custom.action.get_project_root", return_value=root):
            assert _get_debug_folder() == root / "debug"


class TestCounterIncrement:
    """计数器自增动作测试。"""

    def test_counter_increments_by_task_id(self) -> None:
        """按 task_id 自增计数器。"""
        action = CounterIncrement()
        argv = MagicMock()
        argv.task_detail.task_id = "task-001"

        action.run(MagicMock(), argv)
        action.run(MagicMock(), argv)

        assert counter.counter.get_count("task-001") == 2


class TestNonlinearSwipe:
    """非线性滑动动作测试。"""

    def test_swipe_with_default_params(self) -> None:
        """无参数时使用默认值调用 nonlinear_swipe。"""
        action = NonlinearSwipe()
        argv = MagicMock()
        argv.custom_action_param = ""
        context = MagicMock()

        with patch("custom.action.nonlinear_swipe") as mock_swipe:
            result = action.run(context, argv)
            assert result.success is True
            mock_swipe.assert_called_once_with(
                context=context,
                start_x=0,
                start_y=0,
                end_x=0,
                end_y=0,
                duration=150,
                end_hold=False,
                after_swipe_delay=300,
                steps=5,
            )

    def test_swipe_with_custom_params(self) -> None:
        """解析自定义参数并调用 nonlinear_swipe。"""
        action = NonlinearSwipe()
        argv = MagicMock()
        argv.custom_action_param = json.dumps(
            {"start_x": 100, "start_y": 200, "end_x": 300, "end_y": 400, "steps": 10}
        )

        with patch("custom.action.nonlinear_swipe") as mock_swipe:
            result = action.run(MagicMock(), argv)
            assert result.success is True
            call_kwargs = mock_swipe.call_args.kwargs
            assert call_kwargs["start_x"] == 100
            assert call_kwargs["end_y"] == 400
            assert call_kwargs["steps"] == 10

    def test_swipe_failure_returns_false(self) -> None:
        """nonlinear_swipe 抛异常时返回失败。"""
        action = NonlinearSwipe()
        argv = MagicMock()
        argv.custom_action_param = "{invalid-json"

        result = action.run(MagicMock(), argv)
        assert result.success is False


class TestCleanupMaafwBakLogs:
    """maafw 备份日志清理动作测试。"""

    def test_uses_default_keep_count(self) -> None:
        """未传参时使用默认保留数量。"""
        action = CleanupMaafwBakLogs()
        argv = MagicMock()
        argv.custom_action_param = ""

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            debug = root / "debug"
            debug.mkdir()
            with patch("custom.action._get_debug_folder", return_value=debug), \
                 patch("custom.action.cleanup_maafw_bak_logs") as mock_cleanup:
                result = action.run(MagicMock(), argv)
                assert result.success is True
                mock_cleanup.assert_called_once_with(debug, DEFAULT_KEEP_LOG_COUNT)

    def test_uses_custom_keep_count(self) -> None:
        """解析自定义保留数量。"""
        action = CleanupMaafwBakLogs()
        argv = MagicMock()
        argv.custom_action_param = json.dumps({"save_log_count": 5})

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            debug = root / "debug"
            debug.mkdir()
            with patch("custom.action._get_debug_folder", return_value=debug), \
                 patch("custom.action.cleanup_maafw_bak_logs") as mock_cleanup:
                result = action.run(MagicMock(), argv)
                assert result.success is True
                mock_cleanup.assert_called_once_with(debug, 5)

    def test_skips_when_debug_folder_missing(self) -> None:
        """debug 目录不存在时直接返回成功。"""
        action = CleanupMaafwBakLogs()
        argv = MagicMock()
        argv.custom_action_param = ""

        with TemporaryDirectory() as tmp:
            debug = Path(tmp) / "debug"
            with patch("custom.action._get_debug_folder", return_value=debug):
                result = action.run(MagicMock(), argv)
                assert result.success is True


class TestCleanupImageActions:
    """图片清理动作测试。"""

    @pytest.mark.parametrize(
        "action_class, expected_kind",
        [
            (CleanupOnErrorImg, "on_error"),
            (CleanupVisionImg, "vision"),
            (CleanupCustomImg, "custom"),
        ],
        ids=["on_error", "vision", "custom"],
    )
    def test_cleanup_image_kinds(
        self, action_class: type, expected_kind: str
    ) -> None:
        """各图片清理动作传入正确的 kind。"""
        action = action_class()
        argv = MagicMock()

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            debug = root / "debug"
            debug.mkdir()
            with patch("custom.action._get_debug_folder", return_value=debug), \
                 patch("custom.action.compute_cleanup_base_time", return_value=0), \
                 patch("custom.action.clean_images_in_dir") as mock_clean:
                result = action.run(MagicMock(), argv)
                assert result.success is True
                mock_clean.assert_called_once_with(debug, expected_kind, 0)


class TestCleanupCustomLog:
    """自定义日志清理动作测试。"""

    def test_cleanup_custom_log(self) -> None:
        """调用 clean_logs_in_dir 并传入 custom kind。"""
        action = CleanupCustomLog()
        argv = MagicMock()

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            debug = root / "debug"
            debug.mkdir()
            with patch("custom.action._get_debug_folder", return_value=debug), \
                 patch("custom.action.compute_cleanup_base_time", return_value=0), \
                 patch("custom.action.clean_logs_in_dir") as mock_clean:
                result = action.run(MagicMock(), argv)
                assert result.success is True
                mock_clean.assert_called_once_with(debug, "custom", 0)
