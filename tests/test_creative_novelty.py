"""NoveltyScorer 反套路引擎 单元测试

L3 创意增强层 - 新颖度评分与多样性建议
模块尚未实现，测试应为红色（TDD先行）
"""

import pytest

from src.ai.creative.novelty_scorer import NoveltyScorer, NoveltyResult


# --------------- 测试数据 ---------------

STORY_SEGMENT_A = "少年拔出神剑，击败了恶龙，拯救了公主，全村人载歌载舞庆祝胜利。"
STORY_SEGMENT_B = "少年拿起宝剑，打倒了恶龙，救出了公主，村民们欢天喜地庆贺凯旋。"  # 与A高度相似
STORY_SEGMENT_C = "深夜的实验室里，教授发现了量子纠缠的异常数据，她颤抖的手指停在键盘上方。"  # 与A完全不同
STORY_SEGMENT_D = "集市上，卖糖葫芦的老翁突然变了脸色，低声对身旁的乞丐耳语了几句。"

HISTORY_CLICHE = [
    "英雄踏上了征途，一路斩妖除魔。",
    "英雄遇到了同伴，结伴同行。",
    "英雄到达了魔王城堡，准备决战。",
]


@pytest.mark.unit
class TestNoveltyScorer:
    """NoveltyScorer 反套路引擎测试"""

    def setup_method(self):
        self.scorer = NoveltyScorer()

    def test_score_basic(self):
        """计算新颖度分数"""
        result = self.scorer.score(
            current_text=STORY_SEGMENT_A,
            history=[STORY_SEGMENT_C, STORY_SEGMENT_D],
        )

        assert isinstance(result, NoveltyResult)
        assert hasattr(result, "score")
        assert 0.0 <= result.score <= 1.0

    def test_novelty_score_formula(self):
        """novelty_score = 1.0 - max_similarity"""
        # 构造已知相似度场景
        result = self.scorer.score(
            current_text=STORY_SEGMENT_A,
            history=[STORY_SEGMENT_B],  # 高度相似
        )
        # 高相似 → 低新颖度
        assert result.score < 0.5

    def test_high_novelty(self):
        """全新内容得高分"""
        result = self.scorer.score(
            current_text=STORY_SEGMENT_C,
            history=HISTORY_CLICHE,  # 与英雄征途完全不同
        )
        assert result.score > 0.5

    def test_low_novelty_triggers_suggestion(self):
        """novelty < 0.15 触发反套路建议"""
        # 几乎重复的内容
        result = self.scorer.score(
            current_text=STORY_SEGMENT_A,
            history=[STORY_SEGMENT_B],
        )
        suggestion = self.scorer.suggest_diversity_boost(result)

        if result.score < 0.15:
            assert suggestion is not None
            assert isinstance(suggestion, str)
            assert len(suggestion) > 0

    def test_suggest_diversity_boost_content(self):
        """建议内容合理（提高penalty/注入感官切换）"""
        low_novelty = NoveltyResult(score=0.05)
        suggestion = self.scorer.suggest_diversity_boost(low_novelty)

        assert suggestion is not None
        assert isinstance(suggestion, str)
        # 建议应包含具体的改善方向
        assert len(suggestion) > 10

    def test_no_suggestion_above_threshold(self):
        """novelty >= 0.15 不触发建议"""
        high_novelty = NoveltyResult(score=0.8)
        suggestion = self.scorer.suggest_diversity_boost(high_novelty)
        assert suggestion is None or suggestion == ""

    def test_no_chromadb_degradation(self):
        """无chromadb时优雅降级（返回默认高分）"""
        # 模拟 chromadb 不可用
        scorer = NoveltyScorer(use_vector_store=False)
        result = scorer.score(
            current_text=STORY_SEGMENT_A,
            history=HISTORY_CLICHE,
        )
        # 降级时应返回安全的默认高分（不阻碍生成）
        assert isinstance(result, NoveltyResult)
        assert result.score >= 0.5

    def test_empty_history(self):
        """历史为空时返回高新颖度"""
        result = self.scorer.score(
            current_text=STORY_SEGMENT_A,
            history=[],
        )
        assert result.score >= 0.8

    def test_degradation(self):
        """异常时优雅降级"""
        # None 输入不崩溃
        result = self.scorer.score(current_text=None, history=[])
        assert isinstance(result, NoveltyResult)

        # 空字符串不崩溃
        result2 = self.scorer.score(current_text="", history=[""])
        assert isinstance(result2, NoveltyResult)
