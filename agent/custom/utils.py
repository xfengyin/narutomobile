"""向后兼容的代理模块：原功能已迁移至 agent/infrastructure/。"""

from infrastructure.cleanup import (
    clean_images_in_dir,
    clean_logs_in_dir,
    cleanup_maafw_bak_logs,
)
from infrastructure.config_patch import validate_config, validate_mfa
from infrastructure.input import click, fast_swipe, nonlinear_swipe, wait_for_freezes
from infrastructure.ocr import fast_ocr
from infrastructure.screenshot import check_resolution, save_screenshot

__all__ = [
    "click",
    "fast_ocr",
    "fast_swipe",
    "nonlinear_swipe",
    "save_screenshot",
    "validate_config",
    "validate_mfa",
    "wait_for_freezes",
    "check_resolution",
    "cleanup_maafw_bak_logs",
    "clean_images_in_dir",
    "clean_logs_in_dir",
]
