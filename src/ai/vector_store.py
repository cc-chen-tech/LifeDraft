"""Vector-based history retrieval for story context.

This module provides optional vector search capabilities for finding
relevant historical context when generating new stories.

Configuration:
    Set ENABLE_VECTOR_SEARCH=true in .env to enable this feature.
    Default is disabled to maintain backward compatibility.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Feature flag - default disabled
ENABLE_VECTOR_SEARCH = os.getenv("ENABLE_VECTOR_SEARCH", "false").lower() == "true"


@dataclass
class SearchResult:
    """Result of a vector search."""

    content: str
    score: float
    metadata: Dict[str, Any]


class VectorStore:
    """
    Vector-based storage and retrieval for story history.

    This is an optional feature that can be enabled via configuration.
    When disabled, the system falls back to traditional context building.

    Features:
    - Semantic search over story history
    - Relevance-based context selection
    - Automatic embedding management

    Note: Requires additional dependencies (chromadb or faiss) when enabled.
    """

    def __init__(self, enabled: bool = False):
        """
        Initialize the vector store.

        Args:
            enabled: Whether vector search is enabled
        """
        self.enabled = enabled and ENABLE_VECTOR_SEARCH
        self._client: Any = None
        self._collection: Any = None

        if self.enabled:
            self._initialize_store()

    def _initialize_store(self) -> None:
        """Initialize the underlying vector store."""
        try:
            # Try to import chromadb (preferred)
            import chromadb
            from chromadb.config import Settings

            # Use in-memory or persistent storage based on config
            persist_dir = os.getenv("VECTOR_STORE_PATH", "./data/vector_store")

            client = chromadb.PersistentClient(path=persist_dir)
            self._client = client
            self._collection = client.get_or_create_collection(
                name="story_history", metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Vector store initialized at {persist_dir}")

        except ImportError:
            logger.warning(
                "chromadb not installed. Vector search disabled. "
                "Install with: pip install chromadb"
            )
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            self.enabled = False

    def add_story(
        self, story_id: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a story to the vector store.

        Args:
            story_id: Unique identifier for the story
            content: Story text content
            metadata: Optional metadata (week, characters, etc.)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self._collection:
            logger.debug("Vector store disabled, skipping add_story")
            return False

        try:
            self._collection.add(
                ids=[story_id], documents=[content], metadatas=[metadata or {}]
            )
            logger.info(
                f"[VectorStore] Added story: id={story_id}, len={len(content)}, metadata={metadata}"
            )
            return True
        except Exception as e:
            logger.error(f"[VectorStore] Failed to add story: {e}")
            return False

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for relevant stories.

        Args:
            query: Search query (current situation description)
            n_results: Maximum number of results
            filter_metadata: Optional metadata filters

        Returns:
            List of SearchResult objects
        """
        if not self.enabled or not self._collection:
            logger.debug("Vector store disabled, returning empty search results")
            return []

        try:
            logger.info(
                f"[VectorStore] Searching: query_len={len(query)}, n_results={n_results}"
            )
            results = self._collection.query(
                query_texts=[query], n_results=n_results, where=filter_metadata
            )

            search_results = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                score = (
                    1 - results.get("distances", [[]])[0][i]
                )  # Convert distance to similarity
                metadata = (
                    results.get("metadatas", [[]])[0][i]
                    if results.get("metadatas")
                    else {}
                )

                search_results.append(
                    SearchResult(content=doc, score=score, metadata=metadata)
                )

            # Log results summary
            if search_results:
                scores = [r.score for r in search_results]
                logger.info(
                    f"[VectorStore] Found {len(search_results)} results, scores: {[f'{s:.3f}' for s in scores]}"
                )
            else:
                logger.info("[VectorStore] No results found")

            return search_results

        except Exception as e:
            logger.error(f"[VectorStore] Search failed: {e}")
            return []

    def get_relevant_context(
        self, current_situation: str, max_chars: int = 2000
    ) -> str:
        """
        Get relevant historical context for current situation.

        Args:
            current_situation: Description of current story situation
            max_chars: Maximum characters to return

        Returns:
            Formatted context string
        """
        if not self.enabled:
            logger.debug("Vector store disabled, returning empty context")
            return ""

        results = self.search(current_situation, n_results=5)

        if not results:
            return ""

        context_parts = ["【相关历史片段】"]
        total_chars = 0

        for result in results:
            if total_chars >= max_chars:
                break

            week = result.metadata.get("week", "?")
            excerpt = (
                result.content[:500] if len(result.content) > 500 else result.content
            )

            context_parts.append(f"- 第{week}周: {excerpt}")
            total_chars += len(excerpt)

        context_str = "\n".join(context_parts)
        logger.info(
            f"[VectorStore] Built context: {len(context_str)} chars from {len(results)} results"
        )
        return context_str


# Global instance (disabled by default)
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(enabled=ENABLE_VECTOR_SEARCH)  # ★ 传入启用状态
    return _vector_store


def is_vector_search_enabled() -> bool:
    """Check if vector search is enabled."""
    return ENABLE_VECTOR_SEARCH
