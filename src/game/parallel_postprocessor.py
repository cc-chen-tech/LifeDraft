"""Parallel post-processing for game loop operations.

Inspired by Claude Code's StreamingToolExecutor concurrent execution model.
Runs independent post-processing steps in parallel while respecting dependencies.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PostProcessingResult:
    """Result of parallel post-processing."""

    compression_result: Optional[Dict[str, Any]] = None
    world_model_updates: Optional[Dict[str, Any]] = None
    vector_stored: bool = False
    weekly_summary: Optional[str] = None
    errors: List[str] = field(default_factory=list)


class ParallelPostProcessor:
    """Coordinates parallel execution of post-processing steps."""

    def __init__(self, executor: Optional[ThreadPoolExecutor] = None) -> None:
        self._executor = executor or ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="postproc"
        )
        self._owns_executor = executor is None

    def process(
        self,
        player_state: Any,
        story_text: str,
        choice: str,
        language: str,
        summary_generator: Any,
        world_model_updater: Any,
        vector_store: Optional[Any] = None,
        weekly_summary_generator: Optional[Any] = None,
    ) -> PostProcessingResult:
        """Execute post-processing steps with maximum parallelism.

        Parallel group 1 (independent):
          - Story compression (summary_generator.compress_story)
          - Vector store update (vector_store.add_context)

        Serial group 2 (depends on compression result):
          - World model update (world_model_updater.process_*)
          - Weekly summary generation

        Returns:
            PostProcessingResult with all results and any errors
        """
        result = PostProcessingResult()
        futures: Dict[str, Any] = {}

        # -- Parallel group 1 --------------------------------------------------
        try:
            futures["compress"] = self._executor.submit(
                self._safe_compress, summary_generator, story_text, choice, language
            )
        except Exception as e:
            logger.error("Failed to submit compress task: %s", e)
            result.errors.append(f"compress_submit: {e}")

        if vector_store is not None:
            try:
                futures["vector"] = self._executor.submit(
                    self._safe_vector_store, vector_store, story_text
                )
            except Exception as e:
                logger.error("Failed to submit vector task: %s", e)
                result.errors.append(f"vector_submit: {e}")

        # Wait for parallel group 1
        if "compress" in futures:
            try:
                result.compression_result = futures["compress"].result(timeout=60)
            except Exception as e:
                logger.error("Compress task failed: %s", e)
                result.errors.append(f"compress: {e}")

        if "vector" in futures:
            try:
                result.vector_stored = futures["vector"].result(timeout=30)
            except Exception as e:
                logger.error("Vector store task failed: %s", e)
                result.errors.append(f"vector: {e}")

        # -- Serial group 2 (depends on compression result) --------------------
        if result.compression_result and world_model_updater:
            try:
                result.world_model_updates = world_model_updater.process_updates(
                    result.compression_result
                )
            except Exception as e:
                logger.error("World model update failed: %s", e)
                result.errors.append(f"world_model: {e}")

        if weekly_summary_generator and result.compression_result:
            try:
                result.weekly_summary = weekly_summary_generator.generate(
                    result.compression_result.get("summary", "")
                )
            except Exception as e:
                logger.error("Weekly summary generation failed: %s", e)
                result.errors.append(f"weekly_summary: {e}")

        return result

    def _safe_compress(
        self,
        summary_generator: Any,
        story_text: str,
        choice: str,
        language: str,
    ) -> Dict[str, Any]:
        """Safe wrapper around summary_generator.compress_story."""
        return summary_generator.compress_story(story_text, choice, language)  # type: ignore[no-any-return]

    def _safe_vector_store(self, vector_store: Any, story_text: str) -> bool:
        """Safe wrapper around vector_store.add_context."""
        vector_store.add_context(story_text)
        return True

    def shutdown(self) -> None:
        """Shutdown the internal thread pool executor."""
        if self._owns_executor:
            self._executor.shutdown(wait=False)
