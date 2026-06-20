"""infrastructure.common 模块的单元测试。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest

from infrastructure.common import (
    clear_json_cache,
    default_error_handler,
    get_project_root,
    load_json,
    read_json_cached,
    traced,
    write_json_safe,
)
from utils import root as utils_root


@pytest.fixture(autouse=True)
def _clear_json_cache_after_test() -> Generator[None, None, None]:
    """每个用例结束后清理 JSON 缓存，避免相互影响。"""
    yield
    clear_json_cache()


class TestGetProjectRoot:
    """get_project_root 优先级测试。"""

    def test_param_injection(self) -> None:
        """函数参数优先级最高。"""
        injected = Path("/tmp/injected_root")
        assert get_project_root(injected) == injected

    def test_env_var_injection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量 PROJECT_ROOT 优先级次之。"""
        env_root = "/tmp/env_root"
        monkeypatch.setenv("PROJECT_ROOT", env_root)
        assert get_project_root() == Path(env_root)

    def test_default_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无参数且无环境变量时回退到 utils.root。"""
        monkeypatch.delenv("PROJECT_ROOT", raising=False)
        assert get_project_root() == utils_root


class TestReadJsonCached:
    """read_json_cached 缓存行为测试。"""

    def test_cache_hit(self) -> None:
        """多次读取同一文件应命中缓存。"""
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "data.json"
            file_path.write_text('{"key": 1}', encoding="utf-8")

            first = read_json_cached(file_path)
            second = read_json_cached(file_path)
            assert first is second
            assert read_json_cached.cache_info().hits >= 1

    def test_clear_cache(self) -> None:
        """clear_json_cache 应清空缓存。"""
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "data.json"
            file_path.write_text('{"key": 1}', encoding="utf-8")

            read_json_cached(file_path)
            before = read_json_cached.cache_info().currsize
            assert before >= 1

            clear_json_cache()
            after = read_json_cached.cache_info().currsize
            assert after == 0


class TestLoadJson:
    """load_json 深层拷贝测试。"""

    def test_returns_deep_copy(self) -> None:
        """修改返回的 dict 不应影响缓存中的原始数据。"""
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "data.json"
            original: dict[str, Any] = {"nested": {"key": "value"}}
            write_json_safe(file_path, original)

            first = load_json(file_path)
            second = load_json(file_path)
            assert first == second
            assert first is not second

            first["nested"]["key"] = "changed"
            third = load_json(file_path)
            assert third["nested"]["key"] == "value"


class TestWriteJsonSafe:
    """write_json_safe 写入格式测试。"""

    def test_ensure_ascii_false_and_indent_four(self) -> None:
        """验证中文不转义且使用 4 空格缩进。"""
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "out.json"
            data = {"msg": "中文", "list": [1, 2]}
            write_json_safe(file_path, data)

            text = file_path.read_text(encoding="utf-8")
            assert "中文" in text
            assert "\\u" not in text
            assert "\n" in text
            assert '    "msg"' in text
            assert json.loads(text) == data


class FakeContext:
    """带 trace_id 的模拟上下文。"""

    trace_id = "trace-123"


class TestTraced:
    """traced 装饰器行为测试。"""

    def test_extract_trace_id_from_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """自动从位置参数中查找 trace_id 属性。"""
        mock_logger = MagicMock()
        monkeypatch.setattr("infrastructure.common.logger", mock_logger)

        @traced
        def sample(ctx: object) -> int:
            return 42

        assert sample(FakeContext()) == 42
        assert mock_logger.info.call_count == 2
        start_msg = mock_logger.info.call_args_list[0][0][0]
        end_msg = mock_logger.info.call_args_list[1][0][0]
        assert "[trace_id=trace-123]" in start_msg
        assert "sample 开始" in start_msg
        assert "[trace_id=trace-123]" in end_msg
        assert "sample 完成" in end_msg

    def test_extract_trace_id_from_second_arg_for_bound_method(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """类方法中 self 没有 trace_id 时，应从第二个参数 context 提取。"""
        mock_logger = MagicMock()
        monkeypatch.setattr("infrastructure.common.logger", mock_logger)

        class SampleAction:
            @traced
            def run(self, ctx: object) -> int:
                return 42

        assert SampleAction().run(FakeContext()) == 42
        start_msg = mock_logger.info.call_args_list[0][0][0]
        assert "[trace_id=trace-123]" in start_msg

    def test_manual_trace_id_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """manual 模式下从 kwargs 读取 trace_id。"""
        mock_logger = MagicMock()
        monkeypatch.setattr("infrastructure.common.logger", mock_logger)

        @traced(trace_id_source="manual")
        def sample_manual(*, trace_id: str, value: int) -> int:
            return value

        assert sample_manual(trace_id="manual-id", value=5) == 5
        start_msg = mock_logger.info.call_args_list[0][0][0]
        assert "[trace_id=manual-id]" in start_msg

    def test_manual_default_trace_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """manual 模式下未传 trace_id 时使用 default_trace_id。"""
        mock_logger = MagicMock()
        monkeypatch.setattr("infrastructure.common.logger", mock_logger)

        @traced(trace_id_source="manual", default_trace_id="AGENT")
        def sample_agent(value: int) -> int:
            return value

        assert sample_agent(value=5) == 5
        start_msg = mock_logger.info.call_args_list[0][0][0]
        assert "[trace_id=AGENT]" in start_msg

    def test_exception_propagates_and_still_logs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """异常由被装饰函数本身抛出，traced 只负责入口/出口日志。"""
        mock_logger = MagicMock()
        monkeypatch.setattr("infrastructure.common.logger", mock_logger)

        @traced
        def boom(ctx: object) -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            boom(FakeContext())

        assert mock_logger.info.call_count == 1  # 只有入口日志，没有完成日志


class TestDefaultErrorHandler:
    """default_error_handler 行为测试。"""

    def test_call_does_not_raise(self) -> None:
        """调用 default_error_handler 不抛异常。"""
        default_error_handler(ValueError("any"))
