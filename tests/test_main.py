"""agent/main.py 单元测试。"""

import json
import os
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from main import read_interface_version


@pytest.fixture
def temp_root() -> Generator[Path, None, None]:
    """提供临时项目根目录。"""
    with TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture(autouse=True)
def clear_project_root_env() -> Generator[None, None, None]:
    """清理 PROJECT_ROOT 环境变量，避免测试间相互影响。"""
    old = os.environ.pop("PROJECT_ROOT", None)
    yield
    if old is not None:
        os.environ["PROJECT_ROOT"] = old


def test_read_interface_version_returns_debug_when_assets_exists(temp_root: Path) -> None:
    """当 assets/interface.json 存在时，返回 DEBUG。"""
    assets_dir = temp_root / "assets"
    assets_dir.mkdir()
    (assets_dir / "interface.json").write_text("{}", encoding="utf-8")

    with patch("main.get_project_root", return_value=temp_root):
        assert read_interface_version() == "DEBUG"


def test_read_interface_version_reads_version(temp_root: Path) -> None:
    """从 interface.json 读取 version 字段。"""
    (temp_root / "interface.json").write_text(
        json.dumps({"version": "1.2.3"}), encoding="utf-8"
    )

    with patch("main.get_project_root", return_value=temp_root):
        assert read_interface_version() == "1.2.3"


def test_read_interface_version_unknown_when_missing(temp_root: Path) -> None:
    """当 interface.json 不存在时，返回 unknown。"""
    with patch("main.get_project_root", return_value=temp_root):
        assert read_interface_version() == "unknown"


def test_read_interface_version_unknown_on_parse_error(temp_root: Path) -> None:
    """当 interface.json 解析失败时，返回 unknown 且不抛异常。"""
    (temp_root / "interface.json").write_text("not-json", encoding="utf-8")

    with patch("main.get_project_root", return_value=temp_root):
        assert read_interface_version() == "unknown"
