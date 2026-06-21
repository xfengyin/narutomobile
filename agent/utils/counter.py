"""向后兼容重导出层：counter 核心实现已迁移至 agent/infrastructure/counter.py。

旧代码导入方式（仍可用）：
    from utils.counter import counter

推荐新代码直接导入：
    from agent.infrastructure.counter import counter
"""

# === 向后兼容：保留 Counter 类（用于类型注解等场景）===
class Counter:
    """简单计数器，按 key 统计执行次数。"""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def increment(self, key: str, amount: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + amount

    def get_count(self, key: str) -> int:
        return self.counts.get(key, 0)

    def reset(self, key: str | None = None) -> None:
        if key is not None:
            self.counts.pop(key, None)
        else:
            self.counts.clear()


# === 重导出 infrastructure 中的单例（确保 from utils.counter import counter === infrastructure 的单例）===
from agent.infrastructure.counter import counter  # noqa: E402

__all__ = ["Counter", "counter"]
