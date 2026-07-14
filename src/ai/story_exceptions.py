"""Errors that preserve story state when an AI provider cannot complete work."""


class StoryGenerationFailure(RuntimeError):
    """Raised when no valid round story can be generated."""


class StoryRewriteFailure(RuntimeError):
    """Raised when a requested rewrite cannot be completed."""


class StoryContinuationFailure(RuntimeError):
    """Raised when a selected choice cannot produce a valid narrative outcome."""
