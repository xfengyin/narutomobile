"""运行时配置补丁，使用 Pydantic Schema 替代 base64 混淆逻辑。"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from utils import jD, jL, root
from utils.logger import logger


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


def _find_interface_file() -> Path | None:
    """定位安装目录下的 interface.json。"""
    if len(list(root.glob("*.exe"))) == 0:
        return None
    try:
        return next(p for p in root.glob("*.json") if p.name.startswith("in"))
    except StopIteration:
        return None


def _find_mfa_config_file() -> Path | None:
    """定位 MFA 配置文件。"""
    fps = [p for p in (root / "config").glob("*.json") if p.name.startswith("c")]
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


def validate_config(context: object) -> None:
    """验证并补丁安装目录下的 interface.json 元信息。"""
    fp = _find_interface_file()
    if fp is None:
        return

    logger.info(f"验证配置文件: {fp}")
    config: dict[str, Any] = jL(fp.open(encoding="utf-8"))
    defaults = InterfaceMeta().model_dump()
    meta = InterfaceMeta.model_validate({**config, **defaults})
    config.update(meta.model_dump())
    jD(config, fp.open("w", encoding="utf-8"), ensure_ascii=False, indent=4)


def validate_mfa(context: object) -> None:
    """验证并补丁 MFA 配置。"""
    fp = _find_mfa_config_file()
    if fp is None:
        return

    mfa: dict[str, Any] = jL(fp.open(encoding="utf-8"))
    mfa = _patch_mfa_config(mfa)
    jD(mfa, fp.open("w", encoding="utf-8"), ensure_ascii=False, indent=4)
