import json
import re
from typing import Any, Dict, List, Optional, Tuple

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import Rect
from numpy import ndarray

from agent.core.game_constants import (
    ACCESSORY_TICKET_ROI,
    BONDS_TOKEN_ROI,
    BONDS_TOKEN_THRESHOLD,
    CARD_ORANGE,
    CARD_PURPLE,
    CARD_UNKNOWN,
    CARD_UNFLIPPED,
    CHALLENGE_BUTTONS,
    ENEMY_LIST_ROI,
    FLOWER_SEED_CONFIG,
    FLOWER_SEED_PREFIX,
    FLOWER_SEED_THRESHOLD,
    FLIP_CARD_ALL_DIAG,
    FLIP_CARD_GRID_SIZE,
    FLIP_CARD_MAIN_DIAG,
    FLIP_CARD_ROI_GRID,
    FLIP_CARD_SUB_DIAG,
    FLIP_CARD_TIP_CLICK_ROI,
    FLIP_CARD_VICTORY_COUNT,
    GEAR_TICKET_ROI,
    IMPOSSIBLE_SENRYOKU,
    MIN_ENEMY_COUNT,
    MISSION_CURRENT_RESOURCE_ROI,
    MISSION_MAX_RESOURCE_ROI,
    MISSION_REFRESH_BASE,
    MISSION_REFRESH_RATIO,
    SECRET_REALM_TICKET_ROI,
    SENRYOKU_UNIT_WAN,
    SENRYOKU_WAN_MULTIPLIER,
    TEAM_SENRYOKU_ROI,
)
from agent.infrastructure.ocr import read_number, read_numbers
from utils.counter import counter
from utils.logger import logger


def correct_senryoku_text(source_text: str) -> int | None:
    """
    解析战力文本，返回整数战力值
    """
    if source_text.endswith(SENRYOKU_UNIT_WAN):
        text = source_text[:-1]
        text += str(SENRYOKU_WAN_MULTIPLIER)
    else:
        text = source_text

    if text.isdigit():
        logger.info(f"读取到战力：{source_text}")
        return int(text)

    logger.warning(f"战力解析错误：{source_text}")
    return None


def get_senryoku(context: Context, image: ndarray, roi: list[int]) -> int | None:
    """
    获取战力
    """
    reco_detail = context.run_recognition(
        "GetSenryokuText",
        image,
        {
            "GetSenryokuText": {"roi": roi},
        },
    )

    if reco_detail is None or not reco_detail.hit:
        logger.debug(reco_detail)
        logger.warning("无法读取到战力！")
        return None

    source_text = str(reco_detail.best_result.text)  # type: ignore
    return correct_senryoku_text(source_text)


@AgentServer.custom_recognition("IsCounterOverflow")
class IsCounterOverflow(CustomRecognition):
    """
    计数器溢出检测
    """

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        param = json.loads(argv.custom_recognition_param)
        max_hit = int(param.get("max_hit", "0"))

        if max_hit <= 0:
            logger.error("max_hit 参数错误，请检查")
            context.tasker.post_stop()
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        task_id = argv.task_detail.task_id
        now_count = counter.get_count(task_id)
        if now_count >= max_hit:
            logger.debug(f"计数器溢出！最大值: {max_hit} 当前值: {now_count} ")
            logger.info("达到最大执行次数")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        logger.debug(f"计数器状态： 最大值: {max_hit} 当前值: {now_count} ")
        return CustomRecognition.AnalyzeResult(box=Rect(0, 0, 1, 1), detail={})


@AgentServer.custom_recognition("IsInNinjaGuide")
class IsInNinjaGuide(CustomRecognition):
    """
    是否在忍界引导界面
    """

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        reco_detail = context.run_recognition("in_ninja_guide", argv.image, {})
        if reco_detail and reco_detail.hit:
            # GoIntoEntryByGuide不需要这个box
            return CustomRecognition.AnalyzeResult(
                box=Rect(0, 0, 1, 1),
                detail={},
            )
        return CustomRecognition.AnalyzeResult(box=None, detail={})


@AgentServer.custom_recognition("FindToChallenge")
class FindToChallenge(CustomRecognition):
    """
    在积分赛中寻找可以挑战的对象
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        fource_battle = json.loads(argv.custom_recognition_param).get(
            "fource_battle", False
        )
        if fource_battle:
            logger.info("当前配置：强制挑战")
        else:
            logger.info("当前配置：非强制挑战")

        logger.info("尝试读取我方小队战力...")
        team_senryoku = get_senryoku(context, argv.image, list(TEAM_SENRYOKU_ROI))
        if team_senryoku is None:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={},
            )

        logger.info("尝试读取敌方小队战力...")

        reco_detail = context.run_recognition(
            "GetSenryokuText",
            argv.image,
            {
                "GetSenryokuText": {"roi": list(ENEMY_LIST_ROI)},
            },
        )

        if (reco_detail is None) or len(reco_detail.filtered_results) < MIN_ENEMY_COUNT:
            logger.warning("无法读取到敌队战力！")
            logger.debug(
                f"识别结果：{reco_detail.all_results if reco_detail else None}"
            )
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={},
            )

        pattern = re.compile(r"\d+万?")
        enemy_senryoku_list: list[int] = []
        for x in reco_detail.filtered_results[:MIN_ENEMY_COUNT]:
            match = pattern.search(x.text)  # ty:ignore[unresolved-attribute]
            if match:
                senryoku = correct_senryoku_text(match.group())
                if senryoku:
                    enemy_senryoku_list.append(senryoku)
                else:
                    logger.warning(
                        f"无法解析战力文本: {x.text}"  # ty:ignore[unresolved-attribute]
                    )
                    enemy_senryoku_list.append(IMPOSSIBLE_SENRYOKU)
            else:
                logger.warning(
                    f"无法解析战力文本: {x.text}"  # ty:ignore[unresolved-attribute]
                )
                enemy_senryoku_list.append(IMPOSSIBLE_SENRYOKU)

        min_enemy_senryoku = min(enemy_senryoku_list)
        idx = enemy_senryoku_list.index(min_enemy_senryoku)
        logger.info(f"敌队{idx + 1}战力最低：{min_enemy_senryoku / SENRYOKU_WAN_MULTIPLIER}万")

        if (min_enemy_senryoku > team_senryoku) and (not fource_battle):
            logger.info("没一个打得过的，溜了溜了。")
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={},
            )

        logger.info(f"挑战敌队{idx + 1}!")
        return CustomRecognition.AnalyzeResult(
            box=CHALLENGE_BUTTONS[idx],
            detail={},
        )


@AgentServer.custom_recognition("FindPlantableFlower")
class FindPlantableFlower(CustomRecognition):
    """
    中山花店
    在选花界面中寻找可以种的花
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        logger.info(
            f"开始检测可种植的花(需{FLOWER_SEED_THRESHOLD}个种子)..."
        )

        for flower_idx, (seed_roi, btn_roi) in enumerate(FLOWER_SEED_CONFIG):
            flower_num = flower_idx + 1
            logger.info(f"正在检查第{flower_num}种花...")

            current_seeds = read_number(
                context=context,
                image=argv.image,
                roi=list(seed_roi),
                text_modifier=self._extract_seed_count,
            )
            if current_seeds is None:
                logger.warning(f"第{flower_num}种花:种子数量读取失败,跳过")
                continue

            if current_seeds < FLOWER_SEED_THRESHOLD:
                logger.info(
                    f"第{flower_num}种花:种子不足({current_seeds}/"
                    f"{FLOWER_SEED_THRESHOLD}),跳过"
                )
                continue

            logger.info(
                f"第{flower_num}种花:种子充足({current_seeds}/{FLOWER_SEED_THRESHOLD})"
            )
            btn_box = Rect(btn_roi[0], btn_roi[1], btn_roi[2], btn_roi[3])
            return CustomRecognition.AnalyzeResult(
                box=btn_box,
                detail={
                    "flower_num": flower_num,
                    "seed_count": current_seeds,
                    "btn_roi": btn_roi,
                },
            )

        invalid_box = Rect(0, 0, 1, 1)
        return CustomRecognition.AnalyzeResult(
            box=invalid_box, detail={"has_valid_target": False}
        )

    @staticmethod
    def _extract_seed_count(source_text: str) -> str:
        """从 '剩余:xx/xx' 中提取种子数量。"""
        text = source_text.replace(" ", "")
        if FLOWER_SEED_PREFIX not in text:
            return ""
        colon_index = text.find(FLOWER_SEED_PREFIX) + len(FLOWER_SEED_PREFIX)
        if colon_index >= len(text) or text[colon_index] not in {":", "："}:
            return ""
        slash_index = text.find("/", colon_index + 1)
        if slash_index == -1:
            return ""
        return text[colon_index + 1 : slash_index]


@AgentServer.custom_recognition("FlipCard")
class FlipCard(CustomRecognition):
    """
    周年庆4x4翻牌游戏，基于贪心算法。

    规则：
    1. 胜利判定：仅统计紫色牌数量，连续4个判定胜利；
    2. 初始状态：优先选橙色不在的对角线牌，双对角线橙色则选横竖无橙色牌；
    3. 紫色生长：
       - 按“单一方向（行/列/对角线）的最高紫色数”评分；
       - 同最高分下，优先选该方向内的位置；
       - 有橙色的方向，紫色数直接计0；
       - 同分数+同方向下，优先选对角线位置（双对角线橙色时忽略）。
    """

    TIP_CLICK_ROI = list(FLIP_CARD_TIP_CLICK_ROI)

    @staticmethod
    def _get_card_type(context: Context, image: ndarray, roi: list[int]) -> int:
        """识别单张卡牌类型（0=未翻开，1=紫色牌，2=橙色牌，3=识别失败）。

        识别顺序按“未翻开→紫色→橙色”排列，因为翻牌游戏中大部分时间存在大量
        未翻开卡牌，优先匹配可显著减少平均识别次数（最佳情况每牌1次而非3次）。
        """
        if context.run_recognition("card_wait", image, {"card_wait": {"roi": roi}}):
            return CARD_UNFLIPPED

        if context.run_recognition("card_0", image, {"card_0": {"roi": roi}}):
            return CARD_PURPLE

        if context.run_recognition("card_1", image, {"card_1": {"roi": roi}}):
            return CARD_ORANGE

        logger.warning(f"卡牌ROI{roi} 识别失败,应该是触发提示，或者被奖励遮盖")
        return CARD_UNKNOWN

    def _get_orange_info(self, card_state_grid: List[List[int]]) -> Dict[str, Any]:
        """提取橙色牌信息(只要有1个橙色就标记该对角线)"""
        orange_pos = []
        orange_rows = set()
        orange_cols = set()
        orange_diags = set()
        is_both_diag_orange = False

        # 遍历所有牌，标记橙色位置/行/列/对角线
        for row in range(FLIP_CARD_GRID_SIZE):
            for col in range(FLIP_CARD_GRID_SIZE):
                if card_state_grid[row][col] == CARD_ORANGE:
                    orange_pos.append((row, col))
                    orange_rows.add(row)
                    orange_cols.add(col)
                    # 只要对角线有1个橙色，就标记该对角线为橙色
                    if (row, col) in FLIP_CARD_MAIN_DIAG:
                        orange_diags.add("main")
                    if (row, col) in FLIP_CARD_SUB_DIAG:
                        orange_diags.add("sub")

        # 判断是否双对角线都有橙色
        if "main" in orange_diags and "sub" in orange_diags:
            is_both_diag_orange = True
            logger.info("检测到双对角线都有橙色，忽略对角线优先级")

        return {
            "orange_pos": orange_pos,
            "orange_rows": orange_rows,
            "orange_cols": orange_cols,
            "orange_diags": orange_diags,
            "is_both_diag_orange": is_both_diag_orange,
        }

    def _is_initial_state(self, card_state_grid: List[List[int]]) -> bool:
        """判断是否初始状态（除橙色外全未翻牌）"""
        for row in range(FLIP_CARD_GRID_SIZE):
            for col in range(FLIP_CARD_GRID_SIZE):
                if card_state_grid[row][col] not in (CARD_UNFLIPPED, CARD_ORANGE):
                    return False
        return True

    def _get_valid_initial_pos(
        self, card_state_grid: List[List[int]], orange_info: Dict
    ) -> Tuple[int, int] | None:
        """初始状态选最优翻牌位置"""
        all_unflip = [
            (r, c)
            for r in range(FLIP_CARD_GRID_SIZE)
            for c in range(FLIP_CARD_GRID_SIZE)
            if card_state_grid[r][c] == CARD_UNFLIPPED
        ]
        if not all_unflip:
            return None

        # 双对角线橙色 → 优先选横竖无橙色的未翻牌
        if orange_info["is_both_diag_orange"]:
            valid_unflip = [
                (r, c)
                for (r, c) in all_unflip
                if r not in orange_info["orange_rows"]
                and c not in orange_info["orange_cols"]
            ]
            if valid_unflip:
                logger.info(f"双对角线橙色，选横竖无橙色的未翻牌：{valid_unflip[0]}")
                return valid_unflip[0]
            return all_unflip[0]

        # 单对角线橙色 → 优先选另一对角线无橙色的牌
        diag_unflip = [pos for pos in all_unflip if pos in FLIP_CARD_ALL_DIAG]
        if not diag_unflip:
            return all_unflip[0]

        priority1 = []  # 不在橙色行/列+不在橙色对角线
        priority2 = []  # 不在橙色行/列
        priority3 = []  # 其他对角线牌

        for r, c in diag_unflip:
            in_orange_row_col = (r in orange_info["orange_rows"]) or (
                c in orange_info["orange_cols"]
            )
            in_orange_diag = False
            if (r, c) in FLIP_CARD_MAIN_DIAG and "main" in orange_info["orange_diags"]:
                in_orange_diag = True
            if (r, c) in FLIP_CARD_SUB_DIAG and "sub" in orange_info["orange_diags"]:
                in_orange_diag = True

            if not in_orange_row_col and not in_orange_diag:
                priority1.append((r, c))
            elif not in_orange_row_col:
                priority2.append((r, c))
            else:
                priority3.append((r, c))

        if priority1:
            logger.info(f"初始状态选优先级1对角线牌:{priority1[0]}")
            return priority1[0]
        elif priority2:
            logger.info(f"初始状态选优先级2对角线牌:{priority2[0]}")
            return priority2[0]
        elif priority3:
            logger.info(f"初始状态选优先级3对角线牌:{priority3[0]}")
            return priority3[0]
        return diag_unflip[0]

    def _calc_single_dir_score(
        self, pos: Tuple[int, int], card_state_grid: List[List[int]], orange_info: Dict
    ) -> Dict[str, int | str]:
        """
        计算单一方向的分数（非叠加）：行/列/对角线各自的分数
        return: {"row_score": 行分数, "col_score": 列分数, "diag_score": 对角线分数, "max_score": 最高分}
        """
        r, c = pos
        orange_rows = orange_info["orange_rows"]
        orange_cols = orange_info["orange_cols"]
        orange_diags = orange_info["orange_diags"]

        # 1. 行分数：有橙色则0，否则该行紫色数
        row_score = 0
        if r not in orange_rows:
            row_score = sum(
                1
                for col in range(FLIP_CARD_GRID_SIZE)
                if card_state_grid[r][col] == CARD_PURPLE
            )

        # 2. 列分数：有橙色则0，否则该列紫色数
        col_score = 0
        if c not in orange_cols:
            col_score = sum(
                1
                for row in range(FLIP_CARD_GRID_SIZE)
                if card_state_grid[row][c] == CARD_PURPLE
            )

        # 3. 对角线分数：有橙色则0，否则所属对角线的紫色数
        diag_score = 0
        # 主对角线
        if (r, c) in FLIP_CARD_MAIN_DIAG and "main" not in orange_diags:
            diag_score = sum(
                1
                for (x, y) in FLIP_CARD_MAIN_DIAG
                if card_state_grid[x][y] == CARD_PURPLE
            )
        # 副对角线（若同时在两个对角线，取最大值,不过应该不会出现这种情况）
        if (r, c) in FLIP_CARD_SUB_DIAG and "sub" not in orange_diags:
            sub_score = sum(
                1
                for (x, y) in FLIP_CARD_SUB_DIAG
                if card_state_grid[x][y] == CARD_PURPLE
            )
            diag_score = max(diag_score, sub_score)

        # 4. 单一方向最高分
        max_score = max(row_score, col_score, diag_score)

        return {
            "row_score": row_score,
            "col_score": col_score,
            "diag_score": diag_score,
            "max_score": max_score,
            # 标记最高分所属方向（用于优先选同方向位置）
            "max_dir": (
                "row"
                if row_score == max_score
                else ("col" if col_score == max_score else "diag")
            ),
        }

    def _get_best_growth_pos_by_score(
        self, card_state_grid: List[List[int]], orange_info: Dict
    ) -> Optional[Tuple[int, int]]:
        """
        优先同方向生长
        """
        all_unflip = [
            (r, c)
            for r in range(FLIP_CARD_GRID_SIZE)
            for c in range(FLIP_CARD_GRID_SIZE)
            if card_state_grid[r][c] == CARD_UNFLIPPED
        ]
        if not all_unflip:
            return None

        # 计算每个未翻牌的单一方向分数
        pos_data = []
        for pos in all_unflip:
            dir_scores = self._calc_single_dir_score(pos, card_state_grid, orange_info)
            max_score: int = dir_scores["max_score"]  # type: ignore
            max_dir = dir_scores["max_dir"]
            # 排序权重：1. 最高分降序 → 2. 最高分方向（行>列>对角线）→ 3. 对角线优先 → 4. 行列号升序
            dir_priority = 0 if max_dir == "row" else (1 if max_dir == "col" else 2)
            is_diag = (
                1
                if (pos in FLIP_CARD_ALL_DIAG and not orange_info["is_both_diag_orange"])
                else 0
            )
            pos_data.append((-max_score, dir_priority, -is_diag, pos))

        # 排序规则：
        # 1. -max_score → 最高分降序；
        # 2. dir_priority → 行>列>对角线；
        # 3. -is_diag → 对角线优先；
        # 4. pos → 行列号升序；
        pos_data.sort()
        best_pos = pos_data[0][3]
        best_score = -pos_data[0][0]

        # 日志输出单一方向分数
        logger.info("未翻牌评分详情（优先同方向生长，行>列>对角线）：")
        for idx, item in enumerate(pos_data[:3]):
            max_score = -item[0]
            dir_priority = item[1]
            max_dir = (
                "行" if dir_priority == 0 else ("列" if dir_priority == 1 else "对角线")
            )
            diag_marker = "*" if -item[2] == 1 else " "
            pos = item[3]
            logger.info(
                f"  候选{idx+1}:({pos[0]+1},{pos[1]+1}) {diag_marker} 最高分={max_score} 最高分方向={max_dir}"
            )
        logger.info(f"最终选择：({best_pos[0]+1},{best_pos[1]+1}) 最高分={best_score}")

        return best_pos

    def _check_victory(self, card_state_grid: List[List[int]]) -> bool:
        """胜利判定：仅统计紫色牌数量，连续4个判定胜利。"""
        # 检查行
        for r in range(FLIP_CARD_GRID_SIZE):
            purple_count = sum(
                1
                for col in range(FLIP_CARD_GRID_SIZE)
                if card_state_grid[r][col] == CARD_PURPLE
            )
            if purple_count == FLIP_CARD_VICTORY_COUNT:
                logger.info(f"检测到第{r + 1}行4个紫色连成一线,胜利!")
                return True
        # 检查列
        for c in range(FLIP_CARD_GRID_SIZE):
            purple_count = sum(
                1
                for row in range(FLIP_CARD_GRID_SIZE)
                if card_state_grid[row][c] == CARD_PURPLE
            )
            if purple_count == FLIP_CARD_VICTORY_COUNT:
                logger.info(f"检测到第{c + 1}列4个紫色连成一线,胜利!")
                return True
        # 检查主对角线
        main_purple = sum(
            1
            for i in range(FLIP_CARD_GRID_SIZE)
            if card_state_grid[i][i] == CARD_PURPLE
        )
        if main_purple == FLIP_CARD_VICTORY_COUNT:
            logger.info("检测到主对角线4个紫色连成一线,胜利!")
            return True
        # 检查副对角线
        sub_purple = sum(
            1
            for i in range(FLIP_CARD_GRID_SIZE)
            if card_state_grid[i][FLIP_CARD_GRID_SIZE - 1 - i] == CARD_PURPLE
        )
        if sub_purple == FLIP_CARD_VICTORY_COUNT:
            logger.info("检测到副对角线4个紫色连成一线,胜利!")
            return True
        return False

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        logger.info("===== 开始检测翻牌游戏状态=====")

        # 步骤1：识别卡牌状态
        card_state_grid = []
        has_recognize_fail = False
        for row in range(FLIP_CARD_GRID_SIZE):
            row_state = []
            for col in range(FLIP_CARD_GRID_SIZE):
                roi = list(FLIP_CARD_ROI_GRID[row][col])
                card_type = self._get_card_type(context, argv.image, roi)
                row_state.append(card_type)
                if card_type == CARD_UNKNOWN:
                    has_recognize_fail = True
            card_state_grid.append(row_state)
        logger.info(f"当前卡牌状态网格：\n{card_state_grid}")

        # 步骤2：处理识别失败
        if has_recognize_fail:
            logger.info(f"检测到识别失败,点击提示ROI:{self.TIP_CLICK_ROI}")
            tip_box = Rect(*self.TIP_CLICK_ROI)
            return CustomRecognition.AnalyzeResult(
                box=tip_box,
                detail={"action": "click_tip", "tip_roi": self.TIP_CLICK_ROI},
            )

        # 步骤3：检查胜利
        if self._check_victory(card_state_grid):
            invalid_box = Rect(0, 0, 1, 1)
            return CustomRecognition.AnalyzeResult(
                box=invalid_box, detail={"has_valid_target": False, "is_win": True}
            )

        # 步骤4：提取橙色信息
        orange_info = self._get_orange_info(card_state_grid)
        logger.info(
            f"橙色牌信息：位置{[(x+1,y+1) for x,y in orange_info['orange_pos']]}，阻挡行{orange_info['orange_rows']},"
            f"阻挡列{orange_info['orange_cols']}，阻挡对角线{orange_info['orange_diags']}，双对角线橙色：{orange_info['is_both_diag_orange']}"
        )

        # 步骤5：初始状态选牌
        if self._is_initial_state(card_state_grid):
            best_pos = self._get_valid_initial_pos(card_state_grid, orange_info)
            if best_pos is None:
                logger.warning("初始状态无未翻牌可选")
                invalid_box = Rect(0, 0, 1, 1)
                return CustomRecognition.AnalyzeResult(
                    box=invalid_box,
                    detail={"has_valid_target": False, "reason": "no_unflip_card"},
                )
            best_roi = list(FLIP_CARD_ROI_GRID[best_pos[0]][best_pos[1]])
            logger.info(
                f"初始状态选择翻牌位置：({best_pos[0] + 1},{best_pos[1] + 1}),ROI={best_roi}"
            )
            flip_box = Rect(*best_roi)
            return CustomRecognition.AnalyzeResult(
                box=flip_box,
                detail={
                    "has_valid_target": False,
                    "action": "flip_initial",
                    "flip_pos": (best_pos[0] + 1, best_pos[1] + 1),
                    "flip_roi": best_roi,
                },
            )

        # 步骤6：按单一方向最高分选最优生长位置
        best_growth_pos = self._get_best_growth_pos_by_score(
            card_state_grid, orange_info
        )
        if not best_growth_pos:
            logger.warning("无未翻牌可翻")
            invalid_box = Rect(0, 0, 1, 1)
            return CustomRecognition.AnalyzeResult(
                box=invalid_box,
                detail={"has_valid_target": False, "reason": "no_unflip_card"},
            )

        best_roi = list(FLIP_CARD_ROI_GRID[best_growth_pos[0]][best_growth_pos[1]])
        logger.info(
            f"紫色生长选择翻牌位置：({best_growth_pos[0] + 1},{best_growth_pos[1] + 1}),ROI={best_roi}"
        )
        flip_box = Rect(*best_roi)
        return CustomRecognition.AnalyzeResult(
            box=flip_box,
            detail={
                "has_valid_target": False,
                "action": "flip_growth",
                "flip_pos": (best_growth_pos[0] + 1, best_growth_pos[1] + 1),
                "flip_roi": best_roi,
            },
        )


@AgentServer.custom_recognition("find_bonds_without_enough_token")
class FindBondsWithoutEnoughToken(CustomRecognition):
    """
    固定读取ROI的纯数字
    数字 < 5 → 返回识别通过(非空box)
    数字 ≥ 5 或识别失败 → 返回识别未通过(空box)
    """

    TOKEN_CHECK_ROI = list(BONDS_TOKEN_ROI)

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        logger.info("===== 执行find_bonds_without_enough_token节点 =====")

        token_count = read_number(context, argv.image, self.TOKEN_CHECK_ROI)

        if token_count is None:
            logger.warning(
                "[find_bonds_without_enough_token] token数量识别失败,返回未通过"
            )
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"token_count": None, "passed": False}
            )

        if token_count < BONDS_TOKEN_THRESHOLD:
            logger.info(
                f"[find_bonds_without_enough_token] token数量{token_count}<{BONDS_TOKEN_THRESHOLD},返回识别通过"
            )
            pass_box = Rect(0, 0, 1, 1)
            return CustomRecognition.AnalyzeResult(
                box=pass_box, detail={"token_count": token_count, "passed": True}
            )

        logger.info(
            f"[find_bonds_without_enough_token] token数量{token_count}≥{BONDS_TOKEN_THRESHOLD}，返回识别未通过"
        )
        return CustomRecognition.AnalyzeResult(
            box=None, detail={"token_count": token_count, "passed": False}
        )


def get_flip_ticket_count(
    context: Context, image: ndarray, roi: list[int], text_modifier=lambda x: x
) -> int | None:
    """独立读取指定ROI的翻牌卷数量，委托给 read_number 复用 OCR 逻辑。"""
    return read_number(context, image, roi, text_modifier)


@AgentServer.custom_recognition("FindAccessoryFlipTicket")
class FindAccessoryFlipTicket(CustomRecognition):
    """
    秘境饰品翻牌卷识别
    """

    ACCESSORY_TICKET_ROI = list(ACCESSORY_TICKET_ROI)

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        logger.info("===== 执行饰品翻牌卷识别 =====")

        ticket_count = get_flip_ticket_count(
            context=context,
            image=argv.image,
            roi=self.ACCESSORY_TICKET_ROI,
            text_modifier=lambda x: x,
        )

        # 逻辑1：识别失败 → 返回未通过（空box）
        if ticket_count is None:
            logger.warning("饰品翻牌卷数量识别失败,返回未通过")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        # 逻辑2：数量>0 → 返回通过（非空无效Rect）
        if ticket_count > 0:
            logger.info(f"饰品翻牌卷数量{ticket_count}>0,返回识别通过")
            return CustomRecognition.AnalyzeResult(box=Rect(0, 0, 1, 1), detail={})

        # 逻辑3：数量≤0 → 返回未通过（空box）
        logger.info(f"饰品翻牌卷数量{ticket_count}≤0,返回识别未通过")
        return CustomRecognition.AnalyzeResult(box=None, detail={})


@AgentServer.custom_recognition("FindGearFlipTicket")
class FindGearFlipTicket(CustomRecognition):
    """
    忍具翻牌卷识别:和上面的饰品翻牌差不多
    """

    GEAR_TICKET_ROI = list(GEAR_TICKET_ROI)

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        logger.info("===== 执行忍具翻牌卷识别 =====")

        ticket_count = get_flip_ticket_count(
            context=context,
            image=argv.image,
            roi=self.GEAR_TICKET_ROI,
            text_modifier=lambda x: x,
        )

        if ticket_count is None:
            logger.warning("忍具翻牌卷数量识别失败,返回未通过")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        if ticket_count > 0:
            logger.info(f"忍具翻牌卷数量{ticket_count}>0,返回识别通过")
            return CustomRecognition.AnalyzeResult(box=Rect(0, 0, 1, 1), detail={})

        logger.info(f"忍具翻牌卷数量{ticket_count}≤0,返回识别未通过")
        return CustomRecognition.AnalyzeResult(box=None, detail={})


@AgentServer.custom_recognition("SecretRealmTicket")
class SecretRealmTicket(CustomRecognition):
    """
    秘境挑战卷识别:和上面的饰品翻牌差不多
    """

    Secret_Real_Roi = list(SECRET_REALM_TICKET_ROI)

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        logger.info("===== 执行秘境挑战卷识别 SecretRealmTicket =====")

        ticket_count = get_flip_ticket_count(
            context=context,
            image=argv.image,
            roi=self.Secret_Real_Roi,
            text_modifier=lambda x: x,
        )

        if ticket_count is None:
            logger.warning(
                "[SecretRealmTicket] 秘境挑战卷数量识别失败,返回未通过,可能是挑战卷不够了"
            )
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        if ticket_count > 0:
            logger.info(
                f"[SecretRealmTicket] 秘境挑战卷数量{ticket_count}>0,返回识别通过"
            )
            return CustomRecognition.AnalyzeResult(box=Rect(0, 0, 1, 1), detail={})

        logger.info(
            f"[SecretRealmTicket] 秘境挑战卷数量{ticket_count}≤0,返回识别未通过"
        )
        return CustomRecognition.AnalyzeResult(box=None, detail={})


@AgentServer.custom_recognition("MissionOfficeStrategy")
class MissionOfficeStrategy(CustomRecognition):
    """
    策略
    目前刷新上限 ROI: [1004,614,27,27]
    可接受任务 ROI: [1003,648,22,28]
    判断公式：(目前刷新上限 - 9) * 1.5 >= 可接受任务
    也就是期望是一次刷新能刷1.5个神秘箱子任务,我是直接用9/6,可能不准
    """

    MAX_RESOURCE_ROI = list(MISSION_MAX_RESOURCE_ROI)
    CURRENT_RESOURCE_ROI = list(MISSION_CURRENT_RESOURCE_ROI)

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> CustomRecognition.AnalyzeResult:
        logger.info("===== 执行任务集会所策略选择 MissionOfficeStrategy =====")

        max_resource, current_resource = read_numbers(
            context,
            argv.image,
            [self.MAX_RESOURCE_ROI, self.CURRENT_RESOURCE_ROI],
        )

        # 识别失败
        if max_resource is None or current_resource is None:
            logger.warning("[MissionOfficeStrategy] 数字识别失败,返回未通过(安全策略)")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        logger.info(
            f"[MissionOfficeStrategy] 识别结果：刷新上限={max_resource},可接取={current_resource}"
        )

        condition = (max_resource - MISSION_REFRESH_BASE) * MISSION_REFRESH_RATIO >= current_resource
        if condition:
            logger.info("[MissionOfficeStrategy] 公式条件成立，返回识别通过(贪心策略)")
            return CustomRecognition.AnalyzeResult(box=Rect(0, 0, 1, 1), detail={})
        else:
            logger.info(
                "[MissionOfficeStrategy] 公式条件不成立，返回识别未通过(安全策略)"
            )
            return CustomRecognition.AnalyzeResult(box=None, detail={})
