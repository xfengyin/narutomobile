import json
from time import sleep
from typing import Optional, Tuple
from pathlib import Path

from maa.agent.agent_server import AgentServer, TaskDetail
from maa.custom_action import CustomAction
from maa.context import Context
from maa.define import RectType

from utils.logger import logger
from utils.counter import counter
from agent.core.constants import (
    DEFAULT_KEEP_LOG_COUNT,
    RETURNING_CHECK_ROI,
    NINJA_GUIDE_ROI,
    NINJA_GUIDE_LIST_DEFAULT,
    NINJA_GUIDE_LIST_NON_RETURNING,
    NINJA_GUIDE_LIST_RETURNING,
    GO_BUTTON_ROI,
    SWIPE_NON_RETURNING_START,
    SWIPE_NON_RETURNING_END,
    SWIPE_RETURNING_START,
    SWIPE_RETURNING_END,
    WAIT_FOR_FREEZES_MS,
    MAX_SWEEP_ATTEMPTS,
    NONLINEAR_SWIPE_DEFAULT_DURATION,
    NONLINEAR_SWIPE_DEFAULT_AFTER_DELAY,
    NONLINEAR_SWIPE_DEFAULT_STEPS,
)
from agent.core.pipeline_names import (
    CLICK_ENTRY,
    MAIN_SCREEN_SWIPE_TO_RIGHT,
)
from agent.infrastructure.cleanup import (
    clean_images_in_dir,
    clean_logs_in_dir,
    cleanup_maafw_bak_logs,
    compute_cleanup_base_time,
)
from agent.infrastructure.common import INFRA_EXCEPTIONS, get_project_root
from agent.infrastructure.config_patch import validate_config, validate_mfa
from agent.infrastructure.input import click, nonlinear_swipe, wait_for_freezes
from agent.infrastructure.ocr import fast_ocr
from agent.infrastructure.screenshot import check_resolution, save_screenshot


def _get_debug_folder() -> Path:
    """获取项目 debug 目录。"""
    return get_project_root() / "debug"


@AgentServer.custom_action("StopTaskList")
class StopTaskList(CustomAction):
    """
    停止当前任务以及后续任务列表
    """

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
class RetryFaild(CustomAction):
    """
    重试失败
    """

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


@AgentServer.custom_action("GoIntoEntry")
class GoIntoEntry(CustomAction):
    """
    从主界面获取功能入口
    参数:
    {
        "template": "功能入口的匹配模板"
    }
    """

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

        found, box = self.rec_entry(context, target)
        if found and box is not None:
            logger.info("识别到功能入口")
            click(context, *box)
            return CustomAction.RunResult(success=True)

        if context.tasker.stopping:
            logger.info("任务停止，提前退出")
            return CustomAction.RunResult(success=False)

        # 右滑两次
        for i in range(2):
            logger.info(f"右滑第{i + 1}次")
            context.run_task(MAIN_SCREEN_SWIPE_TO_RIGHT)
            context.tasker.controller.post_screencap().wait()
            found, box = self.rec_entry(context, target)
            if found and box is not None:
                logger.info("识别到功能入口")
                click(context, *box)
                return CustomAction.RunResult(success=True)
            if context.tasker.stopping:
                logger.info("任务停止，提前退出")
                return CustomAction.RunResult(success=False)

        # 左滑两次
        for i in range(2):
            logger.info(f"左滑第{i + 1}次")
            context.run_task("main_screen_swipe_to_left")
            context.tasker.controller.post_screencap().wait()
            found, box = self.rec_entry(context, target)
            if found and box is not None:
                logger.info("识别到功能入口")
                click(context, *box)
                return CustomAction.RunResult(success=True)
            if context.tasker.stopping:
                logger.info("任务停止，提前退出")
                return CustomAction.RunResult(success=False)

        logger.error("获取功能入口失败")
        return CustomAction.RunResult(success=False)

    def rec_entry(
        self, context: Context, template: str | list[str]
    ) -> Tuple[bool, Optional[RectType]]:
        reco_detail = context.run_recognition(
            CLICK_ENTRY,
            context.tasker.controller.cached_image,
            {
                CLICK_ENTRY: {
                    "recognition": {
                        "param": {
                            "template": template,
                        }
                    }
                },
            },
        )
        if reco_detail is None or not reco_detail.hit:
            logger.info("未识别到功能入口")
            return False, None

        if reco_detail.best_result is None:
            logger.warning("识别到功能入口但解析失败(best_result为空)")
            return False, None

        return True, reco_detail.best_result.box  # type: ignore


@AgentServer.custom_action("GoIntoEntryByGuide")
class GoIntoEntryByGuide(CustomAction):
    """
    从忍界指引进入特定功能
    """

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

        start = [0, 0]
        end = [0, 0]
        list_roi = NINJA_GUIDE_LIST_DEFAULT

        if context.tasker.stopping:
            logger.info("任务停止，提前退出")
            return CustomAction.RunResult(success=False)

        box = fast_ocr(context=context, expected=["回流"], roi=RETURNING_CHECK_ROI)
        if box is None:
            logger.debug("该账号不为回归账号")
            start = list(SWIPE_NON_RETURNING_START)
            end = list(SWIPE_NON_RETURNING_END)
            list_roi = NINJA_GUIDE_LIST_NON_RETURNING  # 防止识别到背景的排行榜
        else:
            logger.debug("该账号为回归账号")
            start = list(SWIPE_RETURNING_START)
            end = list(SWIPE_RETURNING_END)
            list_roi = NINJA_GUIDE_LIST_RETURNING
            box = fast_ocr(context, expected=["忍界指引"], roi=NINJA_GUIDE_ROI)
            if box is None:
                return CustomAction.RunResult(success=False)

            click(context, *box)

        wait_for_freezes(context, WAIT_FOR_FREEZES_MS)
        if context.tasker.stopping:
            logger.info("任务停止，提前退出")
            return CustomAction.RunResult(success=False)

        # 如果等级较低还有东西没解锁就会聚焦到这里
        # 此时需要先划到最顶上
        logger.info("滑动到最顶端")
        while True:
            if context.tasker.stopping:
                logger.info("任务停止，提前退出")
                return CustomAction.RunResult(success=False)

            if fast_ocr(
                context,
                expected=["天赋"],
                roi=list_roi,
                absolutely=True,
            ):
                break

            nonlinear_swipe(
                context,
                start_x=end[0],
                start_y=end[1],
                end_x=start[0],
                end_y=start[1],
                end_hold=False,
            )

        max_sweep_attempts = MAX_SWEEP_ATTEMPTS
        box = None
        logger.info(f"开始查找功能入口: {enter_name}")
        for _ in range(max_sweep_attempts):
            if context.tasker.stopping:
                logger.info("任务停止，提前退出")
                return CustomAction.RunResult(success=False)

            box = fast_ocr(context, expected=enter_name, roi=list_roi, absolutely=True)
            if box:
                logger.debug(f"识别到功能入口: {enter_name}")
                break

            logger.debug("未识别到功能入口，滑动页面")
            nonlinear_swipe(
                context,
                start_x=start[0],
                start_y=start[1],
                end_x=end[0],
                end_y=end[1],
            )

        if box is None:
            return CustomAction.RunResult(success=False)

        if context.tasker.stopping:
            logger.info("任务停止，提前退出")
            return CustomAction.RunResult(success=False)

        click(context, *box)
        sleep(0.5)

        box = fast_ocr(context, ["前往"], GO_BUTTON_ROI)
        if box is None:
            return CustomAction.RunResult(success=False)
        else:
            click(context, *box)
            return CustomAction.RunResult(success=True)


@AgentServer.custom_action("CounterIncrement")
class CounterIncrement(CustomAction):
    """
    计数器自增动作
    """

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
            "duration": NONLINEAR_SWIPE_DEFAULT_DURATION,
            "after_swipe_delay": NONLINEAR_SWIPE_DEFAULT_AFTER_DELAY,
            "steps": NONLINEAR_SWIPE_DEFAULT_STEPS,
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

        except Exception as e:
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
    """清理 on_error 类型截图。"""

    _missing_log_message = "[图片清理] debug文件夹不存在,跳过"
    _error_log_message = "on_error图片清理异常"

    def _execute(
        self, debug_folder: Path, argv: CustomAction.RunArg
    ) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_images_in_dir(debug_folder, "on_error", base_time)


@AgentServer.custom_action("CleanupVisionImg")
class CleanupVisionImg(CleanupAction):
    """清理 vision 类型截图。"""

    _missing_log_message = "[图片清理] debug文件夹不存在,跳过"
    _error_log_message = "vision图片清理异常"

    def _execute(
        self, debug_folder: Path, argv: CustomAction.RunArg
    ) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_images_in_dir(debug_folder, "vision", base_time)


@AgentServer.custom_action("CleanupCustomImg")
class CleanupCustomImg(CleanupAction):
    """清理 custom 类型截图。"""

    _missing_log_message = "[图片清理] debug文件夹不存在,跳过"
    _error_log_message = "custom图片清理异常"

    def _execute(
        self, debug_folder: Path, argv: CustomAction.RunArg
    ) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_images_in_dir(debug_folder, "custom", base_time)


@AgentServer.custom_action("CleanupCustomLog")
class CleanupCustomLog(CleanupAction):
    """清理 custom 类型日志。"""

    _missing_log_message = "[custom日志清理] debug文件夹不存在,跳过"
    _error_log_message = "自定义日志清理异常"

    def _execute(
        self, debug_folder: Path, argv: CustomAction.RunArg
    ) -> None:
        base_time = compute_cleanup_base_time(debug_folder)
        clean_logs_in_dir(debug_folder, "custom", base_time)
