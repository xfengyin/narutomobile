"""agent/custom/reco.py 单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from custom.reco import (
    FindBondsWithoutEnoughToken,
    FindPlantableFlower,
    FindToChallenge,
    FlipCard,
    IsCounterOverflow,
    IsInNinjaGuide,
    MissionOfficeStrategy,
    correct_senryoku_text,
    get_flip_ticket_count,
)
from core.game_constants import (
    BONDS_TOKEN_THRESHOLD,
    CARD_ORANGE,
    CARD_PURPLE,
    CARD_UNFLIPPED,
    CHALLENGE_BUTTONS,
    FLOWER_SEED_CONFIG,
    FLOWER_SEED_THRESHOLD,
    MISSION_REFRESH_BASE,
    MISSION_REFRESH_RATIO,
)
from utils import counter


class TestCorrectSenryokuText:
    """战力文本解析测试。"""

    def test_plain_number(self) -> None:
        """纯数字直接解析。"""
        assert correct_senryoku_text("12345") == 12345

    def test_wan_unit(self) -> None:
        """带万字单位乘以万倍。"""
        assert correct_senryoku_text("12万") == 12 * 10_000

    def test_invalid_text_returns_none(self) -> None:
        """非数字文本返回 None。"""
        assert correct_senryoku_text("abc") is None


class TestFindPlantableFlowerExtractSeedCount:
    """花店种子数量提取测试。"""

    def test_extract_seed_count_normal(self) -> None:
        """正常格式提取。"""
        text = "剩余:15/20"
        assert FindPlantableFlower._extract_seed_count(text) == "15"

    def test_extract_seed_count_with_space(self) -> None:
        """带空格也能提取。"""
        text = "剩 余 : 8 / 20"
        assert FindPlantableFlower._extract_seed_count(text) == "8"

    def test_extract_seed_count_missing_prefix(self) -> None:
        """缺少前缀返回空字符串。"""
        assert FindPlantableFlower._extract_seed_count("数量:5/10") == ""

    def test_extract_seed_count_missing_slash(self) -> None:
        """缺少斜杠返回空字符串。"""
        assert FindPlantableFlower._extract_seed_count("剩余:520") == ""


class TestFlipCardAlgorithm:
    """翻牌游戏核心算法单元测试。"""

    @staticmethod
    def _grid_from_matrix(matrix: list[list[int]]) -> list[list[int]]:
        """构造 4x4 卡牌状态矩阵。"""
        return [row[:] for row in matrix]

    @pytest.fixture
    def flip_card(self) -> FlipCard:
        """提供 FlipCard 实例。"""
        return FlipCard()

    def test_get_orange_info_basic(self, flip_card: FlipCard) -> None:
        """提取橙色信息。"""
        grid = self._grid_from_matrix(
            [
                [CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        info = flip_card._get_orange_info(grid)
        assert info["orange_pos"] == [(0, 0)]
        assert info["orange_rows"] == {0}
        assert info["orange_cols"] == {0}
        assert info["orange_diags"] == {"main"}
        assert info["is_both_diag_orange"] is False

    def test_get_orange_info_both_diags(self, flip_card: FlipCard) -> None:
        """双对角线橙色判定。"""
        grid = self._grid_from_matrix(
            [
                [CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_ORANGE],
            ]
        )
        info = flip_card._get_orange_info(grid)
        # (0,0) 和 (3,3) 都在主对角线，因此不是双对角线
        assert info["is_both_diag_orange"] is False

        grid_both = self._grid_from_matrix(
            [
                [CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_ORANGE],
            ]
        )
        # 把副对角线也放上橙色
        grid_both[0][3] = CARD_ORANGE
        info_both = flip_card._get_orange_info(grid_both)
        assert info_both["is_both_diag_orange"] is True

    def test_is_initial_state_true(self, flip_card: FlipCard) -> None:
        """只有未翻和橙色为初始状态。"""
        grid = self._grid_from_matrix(
            [
                [CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        assert flip_card._is_initial_state(grid) is True

    def test_is_initial_state_false(self, flip_card: FlipCard) -> None:
        """出现紫色则不是初始状态。"""
        grid = self._grid_from_matrix(
            [
                [CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        assert flip_card._is_initial_state(grid) is False

    def test_check_victory_row(self, flip_card: FlipCard) -> None:
        """行四紫胜利。"""
        grid = self._grid_from_matrix(
            [
                [CARD_PURPLE, CARD_PURPLE, CARD_PURPLE, CARD_PURPLE],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        assert flip_card._check_victory(grid) is True

    def test_check_victory_col(self, flip_card: FlipCard) -> None:
        """列四紫胜利。"""
        grid = self._grid_from_matrix(
            [
                [CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        assert flip_card._check_victory(grid) is True

    def test_check_victory_main_diag(self, flip_card: FlipCard) -> None:
        """主对角线四紫胜利。"""
        grid = self._grid_from_matrix(
            [
                [CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_PURPLE, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_PURPLE],
            ]
        )
        assert flip_card._check_victory(grid) is True

    def test_check_victory_no_win(self, flip_card: FlipCard) -> None:
        """未胜利。"""
        grid = self._grid_from_matrix(
            [
                [CARD_PURPLE, CARD_PURPLE, CARD_PURPLE, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        assert flip_card._check_victory(grid) is False

    def test_get_valid_initial_pos_avoids_orange_row_col_when_both_diag(
        self, flip_card: FlipCard
    ) -> None:
        """双对角线橙色时优先选横竖无橙色的未翻牌。"""
        grid = self._grid_from_matrix(
            [
                [CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_ORANGE, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_ORANGE],
            ]
        )
        info = flip_card._get_orange_info(grid)
        pos = flip_card._get_valid_initial_pos(grid, info)
        assert pos is not None
        assert pos[0] not in info["orange_rows"]
        assert pos[1] not in info["orange_cols"]

    def test_calc_single_dir_score_with_orange_block(
        self, flip_card: FlipCard
    ) -> None:
        """橙色阻挡时该方向分数为 0。"""
        grid = self._grid_from_matrix(
            [
                [CARD_ORANGE, CARD_PURPLE, CARD_PURPLE, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        info = flip_card._get_orange_info(grid)
        score = flip_card._calc_single_dir_score((0, 3), grid, info)
        assert score["row_score"] == 0
        assert score["col_score"] == 0

    def test_calc_single_dir_score_counts_purple(
        self, flip_card: FlipCard
    ) -> None:
        """无橙色时统计对应方向紫色数。"""
        grid = self._grid_from_matrix(
            [
                [CARD_PURPLE, CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        info = flip_card._get_orange_info(grid)
        score = flip_card._calc_single_dir_score((0, 0), grid, info)
        assert score["row_score"] == 2
        assert score["col_score"] == 1

    def test_get_best_growth_pos_by_score_returns_unflip(
        self, flip_card: FlipCard
    ) -> None:
        """生长阶段返回未翻牌中评分最高的位置。"""
        grid = self._grid_from_matrix(
            [
                [CARD_PURPLE, CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_PURPLE, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
                [CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED, CARD_UNFLIPPED],
            ]
        )
        info = flip_card._get_orange_info(grid)
        pos = flip_card._get_best_growth_pos_by_score(grid, info)
        assert pos is not None
        assert grid[pos[0]][pos[1]] == CARD_UNFLIPPED

    def test_analyze_returns_click_tip_on_unknown(self, flip_card: FlipCard) -> None:
        """识别失败时返回点击提示的 box。"""
        context = MagicMock()
        context.run_recognition.return_value = None
        argv = MagicMock()
        argv.image = MagicMock()

        result = flip_card.analyze(context, argv)
        assert result.box is not None
        assert result.detail.get("action") == "click_tip"

    def test_analyze_returns_win_when_row_four_purple(
        self, flip_card: FlipCard
    ) -> None:
        """四紫连珠时返回胜利结果。"""
        context = MagicMock()
        # 所有卡牌识别为紫色，通过 mock _get_card_type 直接返回紫色
        with patch.object(flip_card, "_get_card_type", return_value=CARD_PURPLE):
            argv = MagicMock()
            argv.image = MagicMock()

            result = flip_card.analyze(context, argv)
            assert result.detail.get("is_win") is True


class TestGetFlipTicketCount:
    """翻牌卷读取入口测试。"""

    def test_delegates_to_read_number(self) -> None:
        """确认委托给 read_number。"""
        with patch("custom.reco.read_number", return_value=3) as mock_read:
            context = MagicMock()
            image = MagicMock()
            roi = [1, 2, 3, 4]
            assert get_flip_ticket_count(context, image, roi) == 3
            mock_read.assert_called_once_with(context, image, roi, mock_read.call_args.args[3])


class TestIsCounterOverflow:
    """计数器溢出检测测试。"""

    @pytest.fixture(autouse=True)
    def _reset_counter(self) -> None:
        """每个用例前清空计数器。"""
        counter.counter.reset()

    def test_returns_hit_box_when_under_limit(self) -> None:
        """计数未溢出时返回命中 box。"""
        reco = IsCounterOverflow()
        argv = MagicMock()
        argv.custom_recognition_param = '{"max_hit": 5}'
        argv.task_detail.task_id = "task-001"

        result = reco.analyze(MagicMock(), argv)
        assert result.box is not None

    def test_returns_empty_box_when_over_limit(self) -> None:
        """计数溢出时返回空 box。"""
        reco = IsCounterOverflow()
        argv = MagicMock()
        argv.custom_recognition_param = '{"max_hit": 2}'
        argv.task_detail.task_id = "task-002"
        counter.counter.increment("task-002", 3)

        result = reco.analyze(MagicMock(), argv)
        assert result.box is None

    def test_invalid_max_hit_stops_task(self) -> None:
        """max_hit 非法时停止任务。"""
        reco = IsCounterOverflow()
        context = MagicMock()
        argv = MagicMock()
        argv.custom_recognition_param = '{"max_hit": 0}'

        result = reco.analyze(context, argv)
        assert result.box is None
        context.tasker.post_stop.assert_called_once()


class TestIsInNinjaGuide:
    """忍界引导界面检测测试。"""

    def test_returns_hit_when_recognition_hit(self) -> None:
        """识别命中时返回命中 box。"""
        reco = IsInNinjaGuide()
        context = MagicMock()
        context.run_recognition.return_value = MagicMock(hit=True)
        argv = MagicMock()
        argv.image = MagicMock()

        result = reco.analyze(context, argv)
        assert result.box is not None

    def test_returns_empty_when_recognition_miss(self) -> None:
        """识别未命中时返回空 box。"""
        reco = IsInNinjaGuide()
        context = MagicMock()
        context.run_recognition.return_value = MagicMock(hit=False)
        argv = MagicMock()
        argv.image = MagicMock()

        result = reco.analyze(context, argv)
        assert result.box is None


class TestFindToChallenge:
    """积分赛挑战对象选择测试。"""

    def test_returns_challenge_button_of_weakest_enemy(self) -> None:
        """选择战力最低的敌人并返回对应按钮。"""
        reco = FindToChallenge()
        context = MagicMock()
        argv = MagicMock()
        argv.custom_recognition_param = '{"fource_battle": false}'
        argv.image = MagicMock()

        with patch("custom.reco.get_senryoku", return_value=500_000):
            filtered_results = [
                MagicMock(text="100万"),
                MagicMock(text="50万"),
                MagicMock(text="80万"),
                MagicMock(text="120万"),
            ]
            context.run_recognition.return_value = MagicMock(
                filtered_results=filtered_results
            )

            result = reco.analyze(context, argv)
            # 最低战力是 50万，对应索引 1
            assert result.box == CHALLENGE_BUTTONS[1]

    def test_returns_empty_when_team_senryoku_missing(self) -> None:
        """无法读取我方战力时返回空 box。"""
        reco = FindToChallenge()
        context = MagicMock()
        argv = MagicMock()
        argv.custom_recognition_param = '{}'
        argv.image = MagicMock()

        with patch("custom.reco.get_senryoku", return_value=None):
            result = reco.analyze(context, argv)
            assert result.box is None

    def test_returns_empty_when_enemies_too_strong(self) -> None:
        """敌人全部强于我方且非强制挑战时返回空 box。"""
        reco = FindToChallenge()
        context = MagicMock()
        argv = MagicMock()
        argv.custom_recognition_param = '{"fource_battle": false}'
        argv.image = MagicMock()

        with patch("custom.reco.get_senryoku", return_value=50_000):
            filtered_results = [
                MagicMock(text="10万"),
                MagicMock(text="20万"),
                MagicMock(text="15万"),
                MagicMock(text="30万"),
            ]
            context.run_recognition.return_value = MagicMock(
                filtered_results=filtered_results
            )

            result = reco.analyze(context, argv)
            assert result.box is None

    def test_force_battle_ignores_team_senryoku(self) -> None:
        """强制挑战时忽略战力差距。"""
        reco = FindToChallenge()
        context = MagicMock()
        argv = MagicMock()
        argv.custom_recognition_param = '{"fource_battle": true}'
        argv.image = MagicMock()

        with patch("custom.reco.get_senryoku", return_value=10_000):
            filtered_results = [
                MagicMock(text="100万"),
                MagicMock(text="200万"),
                MagicMock(text="150万"),
                MagicMock(text="300万"),
            ]
            context.run_recognition.return_value = MagicMock(
                filtered_results=filtered_results
            )

            result = reco.analyze(context, argv)
            assert result.box == CHALLENGE_BUTTONS[0]

    def test_uses_impossible_value_when_text_unparseable(self) -> None:
        """无法解析战力文本时使用极大值占位。"""
        reco = FindToChallenge()
        context = MagicMock()
        argv = MagicMock()
        argv.custom_recognition_param = '{"fource_battle": true}'
        argv.image = MagicMock()

        with patch("custom.reco.get_senryoku", return_value=1_000_000):
            filtered_results = [
                MagicMock(text="abc"),
                MagicMock(text="50万"),
                MagicMock(text="xxx"),
                MagicMock(text="80万"),
            ]
            context.run_recognition.return_value = MagicMock(
                filtered_results=filtered_results
            )

            result = reco.analyze(context, argv)
            assert result.box == CHALLENGE_BUTTONS[1]


class TestFindBondsWithoutEnoughToken:
    """羁绊追寻 token 检测测试。"""

    def test_passes_when_token_below_threshold(self) -> None:
        """token 低于阈值时返回命中 box。"""
        reco = FindBondsWithoutEnoughToken()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        with patch("custom.reco.read_number", return_value=BONDS_TOKEN_THRESHOLD - 1):
            result = reco.analyze(context, argv)
            assert result.box is not None
            assert result.detail["passed"] is True

    def test_fails_when_token_at_threshold(self) -> None:
        """token 等于阈值时返回未通过。"""
        reco = FindBondsWithoutEnoughToken()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        with patch("custom.reco.read_number", return_value=BONDS_TOKEN_THRESHOLD):
            result = reco.analyze(context, argv)
            assert result.box is None
            assert result.detail["passed"] is False

    def test_fails_when_recognition_missing(self) -> None:
        """识别失败时返回未通过。"""
        reco = FindBondsWithoutEnoughToken()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        with patch("custom.reco.read_number", return_value=None):
            result = reco.analyze(context, argv)
            assert result.box is None
            assert result.detail["passed"] is False


class TestMissionOfficeStrategy:
    """任务集会所策略测试。"""

    def test_passes_when_condition_met(self) -> None:
        """公式条件成立时返回命中 box。"""
        reco = MissionOfficeStrategy()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        # (max - 9) * 1.5 >= current
        max_resource = 15
        current_resource = 9
        assert (max_resource - MISSION_REFRESH_BASE) * MISSION_REFRESH_RATIO >= current_resource

        with patch("custom.reco.read_numbers", return_value=(max_resource, current_resource)):
            result = reco.analyze(context, argv)
            assert result.box is not None

    def test_fails_when_condition_not_met(self) -> None:
        """公式条件不成立时返回空 box。"""
        reco = MissionOfficeStrategy()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        with patch("custom.reco.read_numbers", return_value=(10, 10)):
            result = reco.analyze(context, argv)
            assert result.box is None

    def test_fails_when_recognition_missing(self) -> None:
        """识别失败时安全返回空 box。"""
        reco = MissionOfficeStrategy()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        with patch("custom.reco.read_numbers", return_value=(None, 5)):
            result = reco.analyze(context, argv)
            assert result.box is None


class TestFindPlantableFlowerAnalyze:
    """中山花店可种植花检测测试。"""

    def test_returns_first_plantable_flower(self) -> None:
        """返回第一个种子充足的花。"""
        reco = FindPlantableFlower()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        # 第 2 种花种子充足
        target_roi = list(FLOWER_SEED_CONFIG[1][0])

        def side_effect(*args: object, **kwargs: object) -> int | None:
            roi = kwargs.get("roi", [])
            if roi == target_roi:
                return FLOWER_SEED_THRESHOLD + 5
            return FLOWER_SEED_THRESHOLD - 1

        with patch("custom.reco.read_number", side_effect=side_effect):
            result = reco.analyze(context, argv)
            assert result.box is not None
            assert result.detail["flower_num"] == 2

    def test_returns_invalid_when_no_seed_enough(self) -> None:
        """所有花种子不足时返回无效目标。"""
        reco = FindPlantableFlower()
        context = MagicMock()
        argv = MagicMock()
        argv.image = MagicMock()

        with patch("custom.reco.read_number", return_value=FLOWER_SEED_THRESHOLD - 1):
            result = reco.analyze(context, argv)
            assert result.detail["has_valid_target"] is False
