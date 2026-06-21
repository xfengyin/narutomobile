"""运行时配置补丁，使用 Pydantic Schema 替代 base64 混淆逻辑。"""

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from infrastructure.common import (
    INFRA_EXCEPTIONS,
    get_project_root,
    load_json,
    traced,
    write_json_safe,
)
from utils.logger import logger


# 配置补丁层关心的异常：文件 IO、JSON 解析、Pydantic 校验等。
CONFIG_EXCEPTIONS: tuple[type[Exception], ...] = INFRA_EXCEPTIONS + (ValidationError,)


class InterfaceMeta(BaseModel):
    """interface.json 的元信息字段。"""

    name: str = "MaaAutoNaruto"
    github: str = "https://github.com/duorua/narutomobile"
    mirrorchyan_rid: str = "MaaAutoNaruto"


class MfaAutoUpdateConfig(BaseModel):
    """MFA 自动更新相关配置。"""

    download_source_index: int = Field(default=0, alias="DownloadSourceIndex")
    enable_auto_update_resource: bool = Field(
        default=True, alias="EnableAutoUpdateResource"
    )
    enable_auto_update_mfa: bool = Field(default=True, alias="EnableAutoUpdateMFA")


def _find_interface_file(root_dir: Path | None = None) -> Path | None:
    """定位安装目录下的 interface.json。"""
    project_root = get_project_root(root_dir)
    if len(list(project_root.glob("*.exe"))) == 0:
        return None
    try:
        return next(p for p in project_root.glob("*.json") if p.name.startswith("in"))
    except StopIteration:
        return None


def _find_mfa_config_file(root_dir: Path | None = None) -> Path | None:
    """定位 MFA 配置文件。"""
    project_root = get_project_root(root_dir)
    fps = [
        p
        for p in (project_root / "config").glob("*.json")
        if p.name.startswith("c")
    ]
    return fps[0] if fps else None


def _patch_mfa_config(mfa: dict[str, Any]) -> dict[str, Any]:
    """应用 MFA 配置补丁，保持与历史行为一致。

    历史行为：
    - 当 DownloadCDK 为空时，强制 DownloadSourceIndex 为 0；
    - 始终强制 EnableAutoUpdateResource 与 EnableAutoUpdateMFA 为 True。
    """
    defaults = MfaAutoUpdateConfig().model_dump(by_alias=True)
    if mfa.get("DownloadCDK", "") != "":
        defaults.pop("DownloadSourceIndex", None)
    else:
        mfa["DownloadSourceIndex"] = 0

    mfa.update(defaults)
    return mfa


def _summarize_mfa_config(mfa: dict[str, Any]) -> dict[str, Any]:
    """返回 MFA 配置摘要，过滤敏感字段（如 CDK）。"""
    sensitive_keys = {"DownloadCDK"}
    return {k: v for k, v in mfa.items() if k not in sensitive_keys}


@traced
def validate_config(
    context: object,
    root_dir: Path | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """验证并补丁安装目录下的 interface.json 元信息。"""
    trace_id = getattr(context, "trace_id", "N/A")
    fp: Path | None = None
    try:
        fp = _find_interface_file(root_dir)
        if fp is None:
            logger.debug(f"[trace_id={trace_id}] 未找到 interface.json")
            return

        logger.debug(f"[trace_id={trace_id}] 找到配置文件: {fp}")
        config: dict[str, Any] = load_json(fp)
        logger.debug(f"[trace_id={trace_id}] 补丁前字段: {list(config.keys())}")
        defaults = InterfaceMeta().model_dump()
        meta = InterfaceMeta.model_validate({**config, **defaults})
        config.update(meta.model_dump())
        logger.debug(f"[trace_id={trace_id}] 补丁后字段: {list(config.keys())}")
        write_json_safe(fp, config)
    except CONFIG_EXCEPTIONS as exc:
        logger.exception(f"[trace_id={trace_id}] validate_config 异常, file={fp}")
        if on_error is not None:
            on_error(exc)


@traced
def validate_mfa(
    context: object,
    root_dir: Path | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """验证并补丁 MFA 配置。"""
    trace_id = getattr(context, "trace_id", "N/A")
    fp: Path | None = None
    try:
        fp = _find_mfa_config_file(root_dir)
        if fp is None:
            logger.debug(f"[trace_id={trace_id}] 未找到 MFA 配置文件")
            return

        logger.debug(f"[trace_id={trace_id}] 找到 MFA 配置文件: {fp}")
        mfa: dict[str, Any] = load_json(fp)
        logger.debug(f"[trace_id={trace_id}] 补丁前状态: {_summarize_mfa_config(mfa)}")
        mfa = _patch_mfa_config(mfa)
        logger.debug(f"[trace_id={trace_id}] 补丁后状态: {_summarize_mfa_config(mfa)}")
        write_json_safe(fp, mfa)
    except CONFIG_EXCEPTIONS as exc:
        logger.exception(f"[trace_id={trace_id}] validate_mfa 异常, file={fp}")
        if on_error is not None:
            on_error(exc)
