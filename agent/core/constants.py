"""基础设施级常量，避免魔法数字散落在业务代码中。"""

from datetime import datetime


# === Resolution & Display ===
TARGET_ASPECT_RATIO = 16.0 / 9.0
ASPECT_RATIO_TOLERANCE_SCREENSHOT = 0.01  # 截图保存用容差
RECOMMENDED_RESOLUTION = (1920, 1080)

# === Log & File Cleanup ===
DEFAULT_KEEP_LOG_COUNT = 3
DEFAULT_BASE_TIME = datetime(2025, 5, 1, 0, 0, 0, 0)

# === Image Extensions ===
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

# === Action ROI ===
# 回流检测
RETURNING_CHECK_ROI = (0, 0, 195, 285)
# 忍界指引识别
NINJA_GUIDE_ROI = (0, 600, 212, 120)
# 功能列表默认 ROI（26, 60, 404, 616）
NINJA_GUIDE_LIST_DEFAULT = (26, 60, 404, 616)
# 功能列表非回归账号 ROI
NINJA_GUIDE_LIST_NON_RETURNING = (0, 66, 219, 627)
# 功能列表回归账号 ROI
NINJA_GUIDE_LIST_RETURNING = (209, 88, 200, 580)
# 前往按钮 ROI
GO_BUTTON_ROI = (834, 539, 287, 149)

# === Swipe Coordinates ===
# 非回归账号滑动坐标（向上滑）
SWIPE_NON_RETURNING_START = (70, 600)
SWIPE_NON_RETURNING_END = (70, 300)
# 回归账号滑动坐标（向上滑）
SWIPE_RETURNING_START = (300, 600)
SWIPE_RETURNING_END = (300, 300)

# === Timing ===
WAIT_FOR_FREEZES_MS = 300
MAX_SWEEP_ATTEMPTS = 20

# === Nonlinear Swipe Default Params ===
NONLINEAR_SWIPE_DEFAULT_DURATION = 150
NONLINEAR_SWIPE_DEFAULT_AFTER_DELAY = 300
NONLINEAR_SWIPE_DEFAULT_STEPS = 5
