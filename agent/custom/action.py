import json
from time import sleep
from typing import Optional
from pathlib import Path

from maa.agent.agent_server import AgentServer, TaskDetail
from maa.custom_action import CustomAction
from maa.context import Context
from maa.define import RectType

from utils.logger import logger
from utils.counter import counter
from core.constants import DEFAULT_KEEP_LOG_COUNT
from infrastructure.cleanup import (
    clean_images_in_dir,
    clean_logs_in_dir,
    cleanup_maafw_bak_logs,
    compute_cleanup_base_time,
)
from infrastructure.common import INFRA_EXCEPTIONS, get_project_root, traced
from infrastructure.config_patch import validate_config, validate_mfa
from infrastructure.input import click, nonlinear_swipe, wait_for_freezes
from infrastructure.ocr import fast_ocr
from infrastructure.screenshot import check_resolution, save_screenshot
from infrastructure.swipe_search import SwipeSearch, SwipeSearchStep, scroll_to_top


def _get_debug_folder() -> Path:
    """获取项目 debug 目录。"""
    return get_project_root() / "debug"


@AgentServer.custom_action("StopTaskList")
class StopTaskList(CustomAction):
    """
    停止当前任务以及后续任务列表
    """

    @traced
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        context.tasker.post_stop()
        return CustomAction.RunResult(success=False)


@AgentServer.custom_action("Screenshot")
class Screenshot(CustomAction):
    """
    自定义截图动作，保存当前屏幕截图到指定目录。

    参数格式:
    {
        "save_dir": "保存截图的目录路径"
    }
    """

    @traced
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        save_screenshot(context)
        task_detail: TaskDetail = context.tasker.get_task_detail(
            argv.task_detail.task_id
        )  # type: ignore
        logger.debug(
            f"task_id: {task_detail.task_id}, task_entry: {task_detail.entry}, status: {task_detail.status._status}"
        )

        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("RetryFailed")
class RetryFailed(CustomAction):
    """
    重试失败
    """

    @traced
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        check_resolution(context)
        save_screenshot(context)
        validate_config(context)
        validate_mfa(context)
        return CustomAction.RunResult(success=True)


# 保留旧名称的向后兼容别名
RetryFaild = RetryFailed


@AgentServer.custom_action("GoIntoEntry")
class GoIntoEntry(CustomAction):
    """
    从主界面获取功能入口
    参数:
    {
        "template": "功能入口的匹配模板"
    }
    """

    @traced
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        target = json.loads(argv.custom_action_param).get("template", "")
        if not isinstance(target, str) and not isinstance(target, list):
            logger.error(f"目标格式错误: {target}")
            context.tasker.post_stop()
            return CustomAction.RunResult(success=False)
        # 检查目标是否为空字符串或空列表
        if (isinstance(target, str) and not target.strip()) or (
            isinstance(target, list) and len(target) == 0
        ):
            logger.error(f"目标为空: {target}")
            context.tasker.post_stop()
            return CustomAction.RunResult(success=False)

        box = self._search_entry(context, target)
        if box is not None:
            logger.info("识别到功能入口")
            click(context, *box)
            return CustomAction.RunResult(success=True)

        logger.error("获取功能入口失败")
        return CustomAction.RunResult(success=False)

    def _search_entry(
        self, context: Context, template: str | list[str]
    ) -> Optional[RectType]:
        """在主界面左右滑动查找功能入口。"""

        def recognizer() -> Optional[RectType]:
            reco_detail = context.run_recognition(
                "click_entry",
                context.tasker.controller.cached_image,
                {
                    "click_entry": {
                        "recognition": {
                            "param": {
                                "template": template,
                            }
                        }
                    }
                },
            )
            if reco_detail is None or not reco_detail.hit:
                logger.info("未识别到功能入口")
                return None
            if reco_detail.best_result is None:
                logger.warning("识别到功能入口但解析失败(best_result为空)")
                return None
            return reco_detail.best_result.box  # type: ignore

        def swipe_right() -> None:
            context.run_task("main_screen_swipe_to_right")
            context.tasker.controller.post_screencap().wait()

        def swipe_left() -> None:
            context.run_task("main_screen_swipe_to_left")
            context.tasker.controller.post_screencap().wait()

        search = SwipeSearch(
            context=context,
            recognizer=recognizer,
            steps=[
                SwipeSearchStep(name="右滑", swipe_action=swipe_right),
                SwipeSearchStep(name="右滑", swipe_action=swipe_right),
                SwipeSearchStep(name="左滑", swipe_action=swipe_left),
                SwipeSearchStep(name="左滑", swipe_action=swipe_left),
            ],
            max_attempts=4,
        )
        return search.search()


@AgentServer.custom_action("GoIntoEntryByGuide")
class GoIntoEntryByGuide(CustomAction):
    """
    从忍界指引进入特定功能
    """

    _RETURNING_CHECK_ROI = (0, 0, 195, 285)
    _RETURNING_GUIDE_ROI = (0, 600, 212, 120)
    _GO_BUTTON_ROI = (834, 539, 287, 149)

    @traced
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        enter_name = json.loads(argv.custom_action_param).get("entry_name", "")
        if enter_name == "":
            logger.error("功能入口名称不能为空!")
            context.tasker.post_stop()
            return CustomAction.RunResult(success=False)

        if not isinstance(enter_name, str) and not isinstance(enter_name, list):
            logger.error(f"输入错误: {enter_name}")
            context.tasker.post_stop()
            return CustomAction.RunResult(success=False)
        if isinstance(enter_name, str):
            enter_name = [enter_name]

        guide_config = self._detect_guide_config(context)
        if guide_config is None:
            return CustomAction.RunResult(success=False)

        wait_for_freezes(context, 300)
        if context.tasker.stopping:
            logger.info("任务停止，提前退出")
            return CustomAction.RunResult(success=False)

        # 如果等级较低还有东西没解锁就会聚焦到这里，需要先划到最顶上
        logger.info("滑动到最顶端")
        scrolled = scroll_to_top(
            context=context,
            recognizer=lambda: bool(
                fast_ocr(
                    context,
                    expected=["天赋"],
                    roi=guide_config.list_roi,
                    absolutely=True,
                )
            ),
            swipe_action=lambda: nonlinear_swipe(
                context,
                start_x=guide_config.end[0],
                start_y=guide_config.end[1],
                end_x=guide_config.start[0],
                end_y=guide_config.start[1],
                end_hold=False,
            ),
        )
        if not scrolled:
            logger.error("滑动到最顶端失败")
            return CustomAction.RunResult(success=False)

        box = self._search_entry_in_guide(context, enter_name, guide_config)
        if box is None:
            return CustomAction.RunResult(success=False)

        click(context, *box)
        sleep(0.5)

        box = fast_ocr(context, ["前往"], self._GO_BUTTON_ROI)
        if box is None:
            return CustomAction.RunResult(success=False)
        click(context, *box)
        return CustomAction.RunResult(success=True)

    def _detect_guide_config(
        self, context: Context
    ) -> "_GuideConfig | None":
        """检测是否为回归账号并返回对应的滑动配置。"""
        if context.tasker.stopping:
            logger.info("任务停止，提前退出")
            return None

        box = fast_ocr(
            context=context, expected=["回流"], roi=self._RETURNING_CHECK_ROI
        )
        if box is None:
            logger.debug("该账号不为回归账号")
            return _GuideConfig(
                start=[70, 600],
                end=[70, 300],
                list_roi=(0, 66, 219, 627),
            )

        logger.debug("该账号为回归账号")
        guide_box = fast_ocr(
            context, expected=["忍界指引"], roi=self._RETURNING_GUIDE_ROI
        )
        if guide_box is None:
            return None

        click(context, *guide_box)
        return _GuideConfig(
            start=[300, 600],
            end=[300, 300],
            list_roi=(209, 88, 200, 580),
        )

    def _search_entry_in_guide(
        self,
        context: Context,
        enter_name: list[str],
        guide_config: "_GuideConfig",
    ) -> Optional[RectType]:
        """在忍界指引列表中滑动查找功能入口。"""
        logger.info(f"开始查找功能入口: {enter_name}")

        def recognizer() -> Optional[RectType]:
            return fast_ocr(
                context,
                expected=enter_name,
                roi=guide_config.list_roi,
                absolutely=True,
            )

        def swipe_down() -> None:
            nonlinear_swipe(
                context,
                start_x=guide_config.start[0],
                start_y=guide_config.start[1],
                end_x=guide_config.end[0],
                end_y=guide_config.end[1],
            )

        search = SwipeSearch(
            context=context,
            recognizer=recognizer,
            steps=[SwipeSearchStep(name="下滑", swipe_action=swipe_down)],
            max_attempts=20,
        )
        return search.search()


class _GuideConfig:
    """忍界指引滑动配置。"""

    def __init__(
        self,
        start: list[int],
        end: list[int],
        list_roi: tuple[int, int, int, int],
    ) -> None:
        self.start = start
        self.end = end
        self.list_roi = list_roi


@AgentServer.custom_action("CounterIncrement")
class CounterIncrement(CustomAction):
    """
    计数器自增动作
    """

    @traced
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        task_id = argv.task_detail.task_id
        counter.increment(task_id)
        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("NonlinearSwipe")
class NonlinearSwipe(CustomAction):
    """
    调用非线性滑动
    """

    @traced
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        swipe_params = {
            "start_x": 0,
            "start_y": 0,
            "end_x": 0,
            "end_y": 0,
            "end_hold": False,
            "duration": 150,
            "after_swipe_delay": 300,
            "steps": 5,
        }

        try:
            if argv.custom_action_param:
                swipe_params.update(json.loads(argv.custom_action_param))

            nonlinear_swipe(
                context=context,
                start_x=int(swipe_params["start_x"]),
                start_y=int(swipe_params["start_y"]),
                end_x=int(swipe_params["end_x"]),
                end_y=int(swipe_params["end_y"]),
                duration=int(swipe_params["duration"]),
                end_hold=bool(swipe_params["end_hold"]),
                after_swipe_delay=int(swipe_params["after_swipe_delay"]),
                steps=int(swipe_params["steps"]),
            )
            return CustomAction.RunResult(success=True)

        except (json.JSONDecodeError,) + INFRA_EXCEPTIONS as e:
            logger.error(f"非线性滑动执行失败: {str(e)}")
            return CustomAction.RunResult(success=False)


class CleanupAction(CustomAction):
    """清理动作基类，统一处理 debug 目录检查与异常捕获。"""

    _missing_log_message: str = "[清理] debug文件夹不存在,跳过"
    _error_log_message: str = "清理执行异常"

    def _execute(
        self, debug_folder: Path, argv: CustomAction.RunArg
    ) -> None:
        """子类实现具体的清理逻辑。"""
        raise NotImplementedError

    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        try:
            debug_folder = _get_debug_folder()
            if not debug_folder.exists():
                logger.info(self._missing_log_message)
                return CustomAction.RunResult(success=True)

            self._execute(debug_folder, argv)
            return CustomAction.RunResult(success=True)
        except INFRA_EXCEPTIONS as e:
            logger.error(f"{self._error_log_message}: {e}")
            return CustomAction.RunResult(success=False)


@AgentServer.custom_action("CleanupMaafwBakLogs")
class CleanupMaafwBakLogs(CleanupAction):
    """清理 maafw 备份日志。"""

    _missing_log_message = "[日志清理] debug文件夹不存在,跳过"
    _error_log_message = "日志清理执行异常"

    def _execute(
        self, debug_folder: Path, argv: CustomAction.RunArg
    ) -> None:
        keep_count = DEFAULT_KEEP_LOG_COUNT
        if argv.custom_action_param:
            param_dict = json.loads(argv.custom_action_param)
            count_val = param_dict.get("save_log_count", "")
            if count_val and str(count_val).isdigit():
                keep_count = int(count_val)

        cleanup_maafw_bak_logs(debug_folder, keep_count)


@AgentServer.custom_action("CleanupOnErrorImg")
class CleanupOnErrorImg(CleanupAction):
    """清理 on_error 图片。"""

    _missing_log_message = "[图片清理] debug文件夹不存在,跳过"
    _error_log_message = "on_error 图片清理异常"

    def _execute(self, debug_folder: Path, argv: CustomAction.RunArg) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_images_in_dir(debug_folder, "on_error", base_time)


@AgentServer.custom_action("CleanupVisionImg")
class CleanupVisionImg(CleanupAction):
    """清理 vision 图片。"""

    _missing_log_message = "[图片清理] debug文件夹不存在,跳过"
    _error_log_message = "vision 图片清理异常"

    def _execute(self, debug_folder: Path, argv: CustomAction.RunArg) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_images_in_dir(debug_folder, "vision", base_time)


@AgentServer.custom_action("CleanupCustomImg")
class CleanupCustomImg(CleanupAction):
    """清理 custom 图片。"""

    _missing_log_message = "[图片清理] debug文件夹不存在,跳过"
    _error_log_message = "custom 图片清理异常"

    def _execute(self, debug_folder: Path, argv: CustomAction.RunArg) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_images_in_dir(debug_folder, "custom", base_time)


@AgentServer.custom_action("CleanupCustomLog")
class CleanupCustomLog(CleanupAction):
    """清理 custom 日志。"""

    _missing_log_message = "[custom日志清理] debug文件夹不存在,跳过"
    _error_log_message = "自定义日志清理异常"

    def _execute(self, debug_folder: Path, argv: CustomAction.RunArg) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_logs_in_dir(debug_folder, "custom", base_time)
