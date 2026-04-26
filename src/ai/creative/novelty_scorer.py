"""NoveltyScorer 反套路引擎。

L3 创意增强层 - 新颖度评分与多样性建议。
尝试使用向量存储做语义相似度比较，无 chromadb 时降级到字符 n-gram Jaccard 相似度。
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 尝试导入向量存储
_vector_store_available = False
try:
    pass

    _vector_store_available = True
except ImportError:
    logger.info("Vector store not available, will use text-based similarity fallback.")


@dataclass
class NoveltyResult:
    """新颖度评分结果。"""

    score: float = 1.0  # 0=完全重复, 1=全新
    most_similar_week: int = -1
    suggestions: Optional[Dict] = None


class NoveltyScorer:
    """基于文本相似度的新颖度评分器。"""

    THRESHOLD = 0.15  # novelty < 0.15 触发反套路

    def __init__(self, use_vector_store: bool = True):
        self._use_vector_store = use_vector_store and _vector_store_available

    def score(
        self, current_text: str, history: Optional[List[str]] = None
    ) -> NoveltyResult:
        """
        计算新颖度: novelty_score = 1.0 - max_similarity。
        无历史时返回高新颖度 (1.0)。
        """
        try:
            if not current_text or not isinstance(current_text, str):
                logger.warning("Invalid current_text, returning default NoveltyResult.")
                return NoveltyResult(score=1.0)

            if not history:
                return NoveltyResult(score=1.0)

            # 过滤无效历史条目
            valid_history = [h for h in history if h and isinstance(h, str)]
            if not valid_history:
                return NoveltyResult(score=1.0)

            if not self._use_vector_store:
                # 降级模式：使用简单文本相似度但给予较高基础分
                max_sim = 0.0
                most_similar_idx = -1
                for i, hist_text in enumerate(valid_history):
                    sim = self._simple_text_similarity(current_text, hist_text)
                    if sim > max_sim:
                        max_sim = sim
                        most_similar_idx = i

                # 降级模式下相似度打折，保证分数 >= 0.5
                novelty = max(0.5, 1.0 - max_sim * 0.5)
                return NoveltyResult(
                    score=novelty,
                    most_similar_week=most_similar_idx,
                )

            # 正常模式：使用文本相似度
            max_sim = 0.0
            most_similar_idx = -1
            for i, hist_text in enumerate(valid_history):
                sim = self._simple_text_similarity(current_text, hist_text)
                if sim > max_sim:
                    max_sim = sim
                    most_similar_idx = i

            novelty = 1.0 - max_sim
            return NoveltyResult(
                score=max(0.0, min(1.0, novelty)),
                most_similar_week=most_similar_idx,
            )

        except Exception as e:
            logger.warning("Error in score: %s, returning default.", e)
            return NoveltyResult(score=1.0)

    def suggest_diversity_boost(self, result: NoveltyResult) -> Optional[str]:
        """
        当 novelty < THRESHOLD 时返回反套路建议字符串。
        """
        try:
            if result.score >= self.THRESHOLD:
                return None

            suggestions = (
                "新颖度过低，建议采取以下措施提升多样性：\n"
                "1. 提高 presence_penalty (+0.2) 和 frequency_penalty (+0.1)\n"
                "2. 注入感官切换指令，切换叙事视角或感官描写\n"
                "3. 引入意外元素打破套路化叙事模式\n"
                "4. 尝试从不同角色视角展开情节"
            )
            return suggestions

        except Exception as e:
            logger.warning("Error in suggest_diversity_boost: %s", e)
            return None

    def _simple_text_similarity(self, text_a: str, text_b: str) -> float:
        """降级方案: 基于字符频率的余弦相似度 + n-gram Jaccard 综合。"""
        try:
            if not text_a or not text_b:
                return 0.0

            # 1. 字符频率余弦相似度
            import math
            from collections import Counter

            freq_a = Counter(text_a)
            freq_b = Counter(text_b)
            all_chars = set(freq_a.keys()) | set(freq_b.keys())

            dot_product = sum(freq_a.get(c, 0) * freq_b.get(c, 0) for c in all_chars)
            norm_a = math.sqrt(sum(v * v for v in freq_a.values()))
            norm_b = math.sqrt(sum(v * v for v in freq_b.values()))

            cosine_sim = dot_product / (norm_a * norm_b) if (norm_a and norm_b) else 0.0

            # 2. Bigram Jaccard
            def get_ngrams(text: str, n: int) -> set:
                return set(text[i : i + n] for i in range(len(text) - n + 1))

            bi_a = get_ngrams(text_a, 2)
            bi_b = get_ngrams(text_b, 2)
            bi_jaccard = len(bi_a & bi_b) / len(bi_a | bi_b) if (bi_a | bi_b) else 0.0

            # 综合：余弦相似度权重更高（更能捕捉语义相似性）
            return 0.8 * cosine_sim + 0.2 * bi_jaccard

        except Exception as e:
            logger.warning("Error in _simple_text_similarity: %s", e)
            return 0.0
