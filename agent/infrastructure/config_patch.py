"""运行时配置补丁，使用 Pydantic Schema 替代 base64 混淆逻辑。"""

import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from utils import jD, jL, root
from utils.logger import logger


def _default_error_handler(exc: Exception) -> None:
    """默认异常处理器，调用方可通过 on_error 注入自定义上报逻辑。"""
    pass


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


def get_project_root(root_dir: Path | None = None) -> Path:
    """返回项目根目录，支持显式传入或环境变量注入。

    优先级：
        1. 函数参数 root_dir；
        2. 环境变量 PROJECT_ROOT；
        3. utils.root 默认值。
    """
    if root_dir is not None:
        return root_dir
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    return root


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


@lru_cache(maxsize=10)
def _read_json_cached(file_path: Path) -> tuple[Any, ...]:
    """读取 JSON 文件并以 tuple 包装返回，便于缓存且 key 可哈希。"""
    with file_path.open(encoding="utf-8") as f:
        return (jL(f),)


def _clear_config_cache() -> None:
    """清除配置读取缓存，便于测试或热重载。"""
    _read_json_cached.cache_clear()


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


def validate_config(
    context: object,
    root_dir: Path | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """验证并补丁安装目录下的 interface.json 元信息。"""
    trace_id = getattr(context, "trace_id", "N/A")
    logger.info(f"[trace_id={trace_id}] validate_config 开始")

    fp: Path | None = None
    try:
        fp = _find_interface_file(root_dir)
        if fp is None:
            logger.debug(f"[trace_id={trace_id}] 未找到 interface.json")
            logger.info(f"[trace_id={trace_id}] validate_config 完成, 未找到配置文件")
            return

        logger.debug(f"[trace_id={trace_id}] 找到配置文件: {fp}")
        cache_info_before = _read_json_cached.cache_info()
        config = copy.deepcopy(_read_json_cached(fp)[0])
        cache_info_after = _read_json_cached.cache_info()
        cache_hit = cache_info_after.hits > cache_info_before.hits
        logger.debug(
            f"[trace_id={trace_id}] 读取缓存{'命中' if cache_hit else '未命中'}: {fp}"
        )
        logger.debug(f"[trace_id={trace_id}] 补丁前字段: {list(config.keys())}")
        defaults = InterfaceMeta().model_dump()
        meta = InterfaceMeta.model_validate({**config, **defaults})
        config.update(meta.model_dump())
        logger.debug(f"[trace_id={trace_id}] 补丁后字段: {list(config.keys())}")
        with fp.open("w", encoding="utf-8") as f:
            jD(config, f, ensure_ascii=False, indent=4)
        logger.info(f"[trace_id={trace_id}] validate_config 完成, file={fp}")
    except Exception as exc:
        logger.exception(
            f"[trace_id={trace_id}] validate_config 异常, file={fp}"
        )
        handler = on_error if on_error is not None else _default_error_handler
        handler(exc)


def validate_mfa(
    context: object,
    root_dir: Path | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """验证并补丁 MFA 配置。"""
    trace_id = getattr(context, "trace_id", "N/A")
    logger.info(f"[trace_id={trace_id}] validate_mfa 开始")

    fp: Path | None = None
    try:
        fp = _find_mfa_config_file(root_dir)
        if fp is None:
            logger.debug(f"[trace_id={trace_id}] 未找到 MFA 配置文件")
            logger.info(f"[trace_id={trace_id}] validate_mfa 完成, 未找到配置文件")
            return

        logger.debug(f"[trace_id={trace_id}] 找到 MFA 配置文件: {fp}")
        cache_info_before = _read_json_cached.cache_info()
        mfa = copy.deepcopy(_read_json_cached(fp)[0])
        cache_info_after = _read_json_cached.cache_info()
        cache_hit = cache_info_after.hits > cache_info_before.hits
        logger.debug(
            f"[trace_id={trace_id}] 读取缓存{'命中' if cache_hit else '未命中'}: {fp}"
        )
        logger.debug(
            f"[trace_id={trace_id}] 补丁前状态: {_summarize_mfa_config(mfa)}"
        )
        mfa = _patch_mfa_config(mfa)
        logger.debug(
            f"[trace_id={trace_id}] 补丁后状态: {_summarize_mfa_config(mfa)}"
        )
        with fp.open("w", encoding="utf-8") as f:
            jD(mfa, f, ensure_ascii=False, indent=4)
        logger.info(f"[trace_id={trace_id}] validate_mfa 完成, file={fp}")
    except Exception as exc:
        logger.exception(
            f"[trace_id={trace_id}] validate_mfa 异常, file={fp}"
        )
        handler = on_error if on_error is not None else _default_error_handler
        handler(exc)
