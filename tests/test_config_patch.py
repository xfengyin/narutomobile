"""config_patch 模块的单元测试。"""

import json
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

from infrastructure.common import clear_json_cache, read_json_cached
from infrastructure.config_patch import (
    InterfaceMeta,
    MfaAutoUpdateConfig,
    _find_interface_file,
    _find_mfa_config_file,
    _patch_mfa_config,
    get_project_root,
    validate_config,
    validate_mfa,
)


@pytest.fixture(autouse=True)
def clear_cache_after_test() -> Generator[None, None, None]:
    """每个测试用例结束后清理配置缓存，避免相互影响。"""
    yield
    clear_json_cache()


class TestInterfaceMeta:
    """InterfaceMeta 默认值与字段补齐测试。"""

    def test_default_values(self) -> None:
        """验证 InterfaceMeta 默认值符合预期。"""
        meta = InterfaceMeta()
        assert meta.name == "MaaAutoNaruto"
        assert meta.github == "https://github.com/duorua/narutomobile"
        assert meta.mirrorchyan_rid == "MaaAutoNaruto"

    def test_fill_missing_fields(self) -> None:
        """验证缺失字段会被默认值补齐。"""
        meta = InterfaceMeta.model_validate({})
        assert meta.name == "MaaAutoNaruto"
        assert meta.github == "https://github.com/duorua/narutomobile"
        assert meta.mirrorchyan_rid == "MaaAutoNaruto"

    def test_partial_fields(self) -> None:
        """验证部分缺失字段仅补齐缺失项。"""
        meta = InterfaceMeta.model_validate({"name": "CustomName"})
        assert meta.name == "CustomName"
        assert meta.github == "https://github.com/duorua/narutomobile"
        assert meta.mirrorchyan_rid == "MaaAutoNaruto"


class TestMfaAutoUpdateConfig:
    """MfaAutoUpdateConfig 模型验证与别名测试。"""

    def test_default_values_and_aliases(self) -> None:
        """验证默认值与别名序列化。"""
        cfg = MfaAutoUpdateConfig()
        data = cfg.model_dump(by_alias=True)
        assert data["DownloadSourceIndex"] == 0
        assert data["EnableAutoUpdateResource"] is True
        assert data["EnableAutoUpdateMFA"] is True

    def test_alias_parsing(self) -> None:
        """验证可通过别名反序列化。"""
        raw = {
            "DownloadSourceIndex": 2,
            "EnableAutoUpdateResource": False,
            "EnableAutoUpdateMFA": False,
        }
        cfg = MfaAutoUpdateConfig.model_validate(raw)
        assert cfg.download_source_index == 2
        assert cfg.enable_auto_update_resource is False
        assert cfg.enable_auto_update_mfa is False


class TestGetProjectRoot:
    """get_project_root 优先级测试。"""

    def test_param_injection(self) -> None:
        """函数参数优先级最高。"""
        expected = Path("/tmp/injected")
        assert get_project_root(expected) == expected

    def test_env_var_injection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量 PROJECT_ROOT 优先级次之。"""
        env_path = "/tmp/env_root"
        monkeypatch.setenv("PROJECT_ROOT", env_path)
        result = get_project_root()
        assert result == Path(env_path)

    def test_default_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无参数且无环境变量时回退到 utils.root。"""
        monkeypatch.delenv("PROJECT_ROOT", raising=False)
        result = get_project_root()
        assert result.exists()


class TestFindInterfaceFile:
    """_find_interface_file 路径定位测试。"""

    def test_no_exe_returns_none(self) -> None:
        """无 exe 文件时返回 None。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            (root_dir / "interface.json").write_text("{}", encoding="utf-8")
            assert _find_interface_file(root_dir) is None

    def test_exe_no_interface_json_returns_none(self) -> None:
        """有 exe 但无 interface.json 时返回 None。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            (root_dir / "app.exe").write_text("", encoding="utf-8")
            (root_dir / "other.json").write_text("{}", encoding="utf-8")
            assert _find_interface_file(root_dir) is None

    def test_exe_and_interface_json_returns_path(self) -> None:
        """有 exe 且存在以 in 开头的 json 文件时返回路径。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            (root_dir / "app.exe").write_text("", encoding="utf-8")
            target = root_dir / "interface.json"
            target.write_text("{}", encoding="utf-8")
            assert _find_interface_file(root_dir) == target


class TestFindMfaConfigFile:
    """_find_mfa_config_file 路径定位测试。"""

    def test_config_dir_missing_returns_none(self) -> None:
        """config 目录不存在时返回 None。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            assert _find_mfa_config_file(root_dir) is None

    def test_config_dir_no_c_file_returns_none(self) -> None:
        """config 目录存在但没有以 c 开头的 json 文件时返回 None。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            config_dir = root_dir / "config"
            config_dir.mkdir()
            (config_dir / "other.json").write_text("{}", encoding="utf-8")
            assert _find_mfa_config_file(root_dir) is None

    def test_config_dir_with_c_file_returns_path(self) -> None:
        """config 目录存在以 c 开头的 json 文件时返回路径。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            config_dir = root_dir / "config"
            config_dir.mkdir()
            target = config_dir / "config.json"
            target.write_text("{}", encoding="utf-8")
            assert _find_mfa_config_file(root_dir) == target


class TestPatchMfaConfig:
    """_patch_mfa_config 补丁逻辑测试。"""

    def test_empty_cdk_forces_download_source_index_zero(self) -> None:
        """空 CDK 时强制 DownloadSourceIndex 为 0。"""
        mfa: dict[str, Any] = {"DownloadCDK": ""}
        result = _patch_mfa_config(mfa)
        assert result["DownloadSourceIndex"] == 0

    def test_empty_cdk_variations(self) -> None:
        """CDK 缺失或为空字符串均强制 DownloadSourceIndex 为 0。"""
        assert _patch_mfa_config({})["DownloadSourceIndex"] == 0
        assert _patch_mfa_config({"DownloadCDK": ""})["DownloadSourceIndex"] == 0

    def test_non_empty_cdk_preserves_download_source_index(self) -> None:
        """非空 CDK 时保留原有 DownloadSourceIndex。"""
        mfa: dict[str, Any] = {"DownloadCDK": "key", "DownloadSourceIndex": 3}
        result = _patch_mfa_config(mfa)
        assert result["DownloadSourceIndex"] == 3

    def test_enable_fields_forced_true(self) -> None:
        """两个 enable 字段始终强制为 True。"""
        mfa: dict[str, Any] = {
            "DownloadCDK": "",
            "EnableAutoUpdateResource": False,
            "EnableAutoUpdateMFA": False,
        }
        result = _patch_mfa_config(mfa)
        assert result["EnableAutoUpdateResource"] is True
        assert result["EnableAutoUpdateMFA"] is True


class TestValidateConfig:
    """validate_config 完整流程测试。"""

    def test_full_flow_patches_interface(self) -> None:
        """传入临时 root_dir 验证 interface.json 被正确补齐。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            (root_dir / "app.exe").write_text("", encoding="utf-8")
            interface_file = root_dir / "interface.json"
            original = {"version": "1.0.0"}
            interface_file.write_text(
                json.dumps(original, ensure_ascii=False), encoding="utf-8"
            )

            validate_config(object(), root_dir)

            content = json.loads(interface_file.read_text(encoding="utf-8"))
            assert content["name"] == "MaaAutoNaruto"
            assert content["github"] == "https://github.com/duorua/narutomobile"
            assert content["mirrorchyan_rid"] == "MaaAutoNaruto"
            assert content["version"] == "1.0.0"

    def test_missing_interface_file_returns_silently(self) -> None:
        """interface.json 不存在时不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            (root_dir / "app.exe").write_text("", encoding="utf-8")
            validate_config(object(), root_dir)

    def test_no_exe_returns_silently(self) -> None:
        """无 exe 文件时不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            validate_config(object(), root_dir)

    def test_invalid_json_caught(self) -> None:
        """JSON 解析错误被捕获，不向外抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            (root_dir / "app.exe").write_text("", encoding="utf-8")
            interface_file = root_dir / "interface.json"
            interface_file.write_text("not json", encoding="utf-8")

            validate_config(object(), root_dir)

    def test_invalid_json_invokes_on_error(self) -> None:
        """JSON 解析错误时会调用自定义 on_error 回调。"""
        errors: list[Exception] = []

        def handler(exc: Exception) -> None:
            errors.append(exc)

        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            (root_dir / "app.exe").write_text("", encoding="utf-8")
            interface_file = root_dir / "interface.json"
            interface_file.write_text("not json", encoding="utf-8")

            validate_config(object(), root_dir, on_error=handler)

        assert len(errors) == 1
        assert isinstance(errors[0], json.JSONDecodeError)


class TestValidateMfa:
    """validate_mfa 完整流程测试。"""

    def test_full_flow_patches_mfa(self) -> None:
        """传入临时 root_dir 验证 MFA 配置被正确补丁。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            config_dir = root_dir / "config"
            config_dir.mkdir()
            mfa_file = config_dir / "config.json"
            original: dict[str, Any] = {
                "DownloadCDK": "",
                "DownloadSourceIndex": 5,
                "EnableAutoUpdateResource": False,
                "EnableAutoUpdateMFA": False,
            }
            mfa_file.write_text(
                json.dumps(original, ensure_ascii=False), encoding="utf-8"
            )

            validate_mfa(object(), root_dir)

            content = json.loads(mfa_file.read_text(encoding="utf-8"))
            assert content["DownloadSourceIndex"] == 0
            assert content["EnableAutoUpdateResource"] is True
            assert content["EnableAutoUpdateMFA"] is True

    def test_missing_mfa_file_returns_silently(self) -> None:
        """MFA 配置文件不存在时不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            validate_mfa(object(), root_dir)

    def test_invalid_json_caught(self) -> None:
        """JSON 解析错误被捕获，不向外抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            config_dir = root_dir / "config"
            config_dir.mkdir()
            mfa_file = config_dir / "config.json"
            mfa_file.write_text("not json", encoding="utf-8")

            validate_mfa(object(), root_dir)

    def test_invalid_json_invokes_on_error(self) -> None:
        """JSON 解析错误时会调用自定义 on_error 回调。"""
        errors: list[Exception] = []

        def handler(exc: Exception) -> None:
            errors.append(exc)

        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp)
            config_dir = root_dir / "config"
            config_dir.mkdir()
            mfa_file = config_dir / "config.json"
            mfa_file.write_text("not json", encoding="utf-8")

            validate_mfa(object(), root_dir, on_error=handler)

        assert len(errors) == 1
        assert isinstance(errors[0], json.JSONDecodeError)


class TestReadJsonCached:
    """read_json_cached 缓存行为测试。"""

    def test_cache_hit(self) -> None:
        """多次读取同一文件应命中缓存。"""
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "data.json"
            file_path.write_text("{\"key\": 1}", encoding="utf-8")

            first = read_json_cached(file_path)
            second = read_json_cached(file_path)
            assert first == second
            assert read_json_cached.cache_info().hits >= 1

    def test_clear_cache(self) -> None:
        """clear_json_cache 应清空缓存。"""
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "data.json"
            file_path.write_text("{\"key\": 1}", encoding="utf-8")

            read_json_cached(file_path)
            before = read_json_cached.cache_info().currsize
            assert before >= 1

            clear_json_cache()
            after = read_json_cached.cache_info().currsize
            assert after == 0


class TestExceptionScenarios:
    """异常场景测试。"""

    def test_validate_config_no_crash_on_missing_file(self) -> None:
        """validate_config 在空目录下不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            validate_config(object(), Path(tmp))

    def test_validate_mfa_no_crash_on_missing_file(self) -> None:
        """validate_mfa 在空目录下不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            validate_mfa(object(), Path(tmp))
