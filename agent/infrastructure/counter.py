"""计数器基础设施：记录各操作类型的执行次数。"""


class Counter:
    """简单计数器，按 key 统计执行次数。"""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def increment(self, key: str, amount: int = 1) -> None:
        """增加指定 key 的计数。"""
        self.counts[key] = self.counts.get(key, 0) + amount

    def get_count(self, key: str) -> int:
        """获取指定 key 的当前计数。"""
        return self.counts.get(key, 0)

    def reset(self, key: str | None = None) -> None:
        """重置计数器。key 为 None 时重置所有。"""
        if key is not None:
            self.counts.pop(key, None)
        else:
            self.counts.clear()


# 全局单例
counter = Counter()
