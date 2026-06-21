"""pytest 全局 mock 配置，在测试收集前执行。"""

import sys
from types import ModuleType
from typing import Any, Callable
from unittest.mock import MagicMock


def _create_package(name: str) -> ModuleType:
    """创建并注册一个空包，用于 mock 未安装的依赖。"""
    module = ModuleType(name)
    module.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = module
    return module


def _create_submodule(parent: ModuleType, name: str) -> ModuleType:
    """在父包下创建子模块。"""
    submodule = ModuleType(f"{parent.__name__}.{name}")
    submodule.__path__ = []  # type: ignore[attr-defined]
    setattr(parent, name, submodule)
    sys.modules[submodule.__name__] = submodule
    return submodule


class _MockRunArg:
    """模拟 CustomAction/Recognition 的运行参数。"""

    custom_action_param: str = ""
    custom_recognition_param: str = ""

    def __init__(self) -> None:
        self.task_detail = MagicMock()
        self.task_detail.task_id = "task-001"


class _MockRunResult:
    """模拟动作执行结果。"""

    def __init__(self, success: bool = True) -> None:
        self.success = success


class _MockAnalyzeResult:
    """模拟识别执行结果。"""

    def __init__(self, box: object = None, detail: dict | None = None) -> None:
        self.box = box
        self.detail = detail or {}


class _MockCustomAction:
    """可继承的 CustomAction 模拟基类。"""

    RunArg = _MockRunArg
    RunResult = _MockRunResult


class _MockCustomRecognition:
    """可继承的 CustomRecognition 模拟基类。"""

    AnalyzeArg = _MockRunArg
    AnalyzeResult = _MockAnalyzeResult


class _MockAgentServer:
    """模拟 AgentServer 装饰器。"""

    @staticmethod
    def custom_action(name: str) -> Callable[..., Any]:
        """直接返回被装饰类本身。"""
        def decorator(cls: type) -> type:
            return cls
        return decorator

    @staticmethod
    def custom_recognition(name: str) -> Callable[..., Any]:
        """直接返回被装饰类本身。"""
        def decorator(cls: type) -> type:
            return cls
        return decorator

    @staticmethod
    def tasker_sink() -> Callable[..., Any]:
        """直接返回被装饰类本身。"""
        def decorator(cls: type) -> type:
            return cls
        return decorator


# 会话级别 mock maa 相关模块，避免导入真实依赖
if "maa" not in sys.modules:
    maa = _create_package("maa")

    maa.agent = _create_submodule(maa, "agent")  # type: ignore[attr-defined]
    maa.agent.agent_server = _create_submodule(maa.agent, "agent_server")  # type: ignore[attr-defined]
    maa.agent.agent_server.AgentServer = _MockAgentServer  # type: ignore[attr-defined]
    maa.agent.agent_server.TaskDetail = MagicMock()  # type: ignore[attr-defined]

    maa.context = _create_submodule(maa, "context")  # type: ignore[attr-defined]
    maa.context.Context = MagicMock()  # type: ignore[attr-defined]

    maa.custom_action = _create_submodule(maa, "custom_action")  # type: ignore[attr-defined]
    maa.custom_action.CustomAction = _MockCustomAction  # type: ignore[attr-defined]

    maa.custom_recognition = _create_submodule(maa, "custom_recognition")  # type: ignore[attr-defined]
    maa.custom_recognition.CustomRecognition = _MockCustomRecognition  # type: ignore[attr-defined]

    maa.define = _create_submodule(maa, "define")  # type: ignore[attr-defined]
    maa.define.Rect = lambda *args, **kwargs: args  # type: ignore[attr-defined]
    maa.define.RectType = MagicMock()  # type: ignore[attr-defined]

    maa.toolkit = _create_submodule(maa, "toolkit")  # type: ignore[attr-defined]
    maa.toolkit.Toolkit = MagicMock()  # type: ignore[attr-defined]

    maa.tasker = _create_submodule(maa, "tasker")  # type: ignore[attr-defined]
    maa.tasker.Tasker = MagicMock()  # type: ignore[attr-defined]
    maa.tasker.TaskerEventSink = MagicMock()  # type: ignore[attr-defined]

    maa.event_sink = _create_submodule(maa, "event_sink")  # type: ignore[attr-defined]
    maa.event_sink.NotificationType = MagicMock()  # type: ignore[attr-defined]

    numpy = _create_package("numpy")
    numpy.ndarray = MagicMock()  # type: ignore[attr-defined]

    PIL = _create_package("PIL")
    PIL.Image = MagicMock()  # type: ignore[attr-defined]
