# test.py
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent"))


# 空Context
class blankContext:
    pass


if __name__ == "__main__":
    from agent.custom.utils import cleanup_debug_logs

    context = blankContext()
    cleanup_debug_logs(context, keep_count=3)
