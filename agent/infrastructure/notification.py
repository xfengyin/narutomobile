"""桌面通知基础设施。"""

from notifypy import Notify

from utils import logo


def send_notification(title: str = "系统通知", msg: str = "这是一条测试消息") -> None:
    """发送桌面通知。"""
    Notify(title, msg, "MaaAutoNaruto", str(logo)).send()
