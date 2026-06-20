"""agent/custom/reco.py 单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from custom.reco import (
    FlipCard,
    FindPlantableFlower,
    correct_senryoku_text,
    get_flip_ticket_count,
)
from core.game_constants import (
    CARD_ORANGE,
    CARD_PURPLE,
    CARD_UNFLIPPED,
)


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
