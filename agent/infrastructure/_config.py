"""基础设施共享配置：根路径、JSON 工具、logo 路径。

作为 agent/utils/ 与 agent/infrastructure/ 的共享根基模块，
避免两者之间产生循环导入依赖。
"""

import json as _json
from pathlib import Path

# 项目根目录（模块级求值，测试时有副作用风险，建议通过 get_project_root() 动态获取）
root: Path = Path(__file__).resolve().parent.parent.parent

# JSON 工具别名
jL = _json.load
jD = _json.dump

# Logo 路径
logo: Path = (root / "docs" / "imgs" / "logo.png").absolute()
