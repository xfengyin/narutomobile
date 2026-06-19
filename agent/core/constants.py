"""基础设施级常量，避免魔法数字散落在业务代码中。"""

from datetime import datetime
from pathlib import Path

# 分辨率与显示
TARGET_ASPECT_RATIO = 16.0 / 9.0
ASPECT_RATIO_TOLERANCE_DEV = 0.02  # 开发/提示用容差
ASPECT_RATIO_TOLERANCE_SCREENSHOT = 0.01  # 截图保存用容差
RECOMMENDED_RESOLUTION = (1920, 1080)

# 日志与文件清理
DEFAULT_KEEP_LOG_COUNT = 3
DEFAULT_BASE_TIME = datetime(2025, 5, 1, 0, 0, 0, 0)
LOG_RETENTION_DAYS = 14  # loguru 默认保留两周

# 图片扩展名集合
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

# 项目根目录由调用方传入，避免模块级副作用
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
