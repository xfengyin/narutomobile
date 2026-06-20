# -*- coding: utf-8 -*-

# M9A
# https://github.com/MAA1999/M9A
# AGPL-3.0 License

import os
import sys
from pathlib import Path
from typing import Callable


# utf-8
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

# 获取当前 main.py 路径并设置上级目录为工作目录
current_file_path = Path(__file__).resolve()
current_script_dir = current_file_path.parent
project_root_dir = current_script_dir.parent

# 更改 CWD 到项目根目录
if Path.cwd() != project_root_dir:
    os.chdir(project_root_dir)
print(f"set cwd: {Path.cwd()}")

# 将脚本自身的目录添加到 sys.path，以便导入 utils、maa 等模块
if current_script_dir.__str__() not in sys.path:
    sys.path.insert(0, current_script_dir.__str__())

from infrastructure.common import get_project_root, load_json, traced  # noqa: E402
from utils.logger import logger  # noqa: E402

VENV_NAME = ".venv"
VENV_DIR = get_project_root(project_root_dir) / VENV_NAME


### 配置相关 ###
def read_interface_version(interface_file_name: str = "./interface.json") -> str:
    """读取 interface.json 版本，若存在 assets/interface.json 则判定为 DEBUG 模式。"""
    root = get_project_root(project_root_dir)
    interface_path = root / interface_file_name
    assets_interface_path = root / "assets" / interface_file_name

    if not (assets_interface_path.exists() or interface_path.exists()):
        logger.error("未找到 interface.json")
        return "unknown"

    if assets_interface_path.exists():
        return "DEBUG"

    try:
        interface_data = load_json(interface_path)
        return interface_data.get("version", "unknown")
    except Exception:
        logger.exception(f"读取 interface.json 版本失败：{interface_path}")
        return "unknown"


### 核心业务 ###
@traced(trace_id_source="manual", default_trace_id="AGENT")
def agent(
    is_dev_mode: bool = False,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """启动 MAA AgentServer。"""
    trace_id = "AGENT"
    try:
        if is_dev_mode:
            from utils.logger import change_console_level

            change_console_level("DEBUG")
            logger.info(f"[trace_id={trace_id}] 开发模式:日志等级已设置为 DEBUG")

        try:
            from maa.agent.agent_server import AgentServer
            from maa.toolkit import Toolkit

            # 导入 custom 模块以注册自定义动作/识别器，此行不能删
            import custom  # noqa: F401
        except ImportError as e:
            logger.error(e)
            logger.error("Failed to import modules")
            logger.error("Please try to run dependency deployment script first")
            logger.error("导入模块失败！")
            logger.error("请先尝试运行依赖部署脚本")
            return

        Toolkit.init_option("./")

        if len(sys.argv) < 2:
            logger.error(f"[trace_id={trace_id}] 缺少必要的 socket_id 参数")
            return

        socket_id = sys.argv[-1]
        logger.info(f"[trace_id={trace_id}] socket_id: {socket_id}")

        AgentServer.start_up(socket_id)
        logger.info(f"[trace_id={trace_id}] AgentServer 启动")
        AgentServer.join()
        AgentServer.shut_down()
        logger.info(f"[trace_id={trace_id}] AgentServer 关闭")
    except ImportError as e:
        logger.error(f"[trace_id={trace_id}] 导入模块失败: {e}")
        logger.error("考虑重新配置环境")
        if on_error is not None:
            on_error(e)
        sys.exit(1)
    except Exception as e:
        logger.exception(f"[trace_id={trace_id}] agent 运行过程中发生异常: {e}")
        if on_error is not None:
            on_error(e)
        raise


### 程序入口 ###
@traced(trace_id_source="manual", default_trace_id="MAIN")
def main() -> None:
    """程序入口。"""
    trace_id = "MAIN"
    current_version = read_interface_version()
    is_dev_mode = current_version.upper() == "DEBUG"

    if is_dev_mode:
        os.chdir(Path("./assets"))
        logger.info(f"[trace_id={trace_id}] set cwd: {os.getcwd()}")

    agent(is_dev_mode=is_dev_mode)


if __name__ == "__main__":
    main()
