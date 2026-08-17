"""Exceptions contract tests.

No mocks. Pure logic tests for exception hierarchy.
"""

import pytest

from src.exceptions import (AIClientError, AIGenerationError,
                            AuthenticationError, DatabaseError,
                            DataExtractionError, GameException,
                            ImageProcessingError, SSEStreamError,
                            ValidationError)

pytestmark = [pytest.mark.unit]



class TestExceptionsContract:
    """Contract tests for exception hierarchy."""

    def test_all_exceptions_inherit_from_game_exception(self):
        """All custom exceptions should inherit from GameException."""
        exceptions = [
            AIGenerationError("test"),
            AIClientError("test"),
            DataExtractionError("test"),
            DatabaseError("test"),
            ValidationError("test"),
            ImageProcessingError("test"),
            SSEStreamError("test"),
            AuthenticationError("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, GameException)

    def test_game_exception_message(self):
        """GameException should store message."""
        exc = GameException("something went wrong")
        assert str(exc) == "something went wrong"

    def test_game_exception_context_default(self):
        """GameException should have empty context by default."""
        exc = GameException("error")
        assert exc.context == {}

    def test_game_exception_context_provided(self):
        """GameException should store provided context."""
        ctx = {"game_id": 123, "week": 5}
        exc = GameException("error", context=ctx)
        assert exc.context == ctx

    def test_ai_generation_error_is_game_exception(self):
        """AIGenerationError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise AIGenerationError("AI failed")

    def test_validation_error_is_game_exception(self):
        """ValidationError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise ValidationError("invalid input")

    def test_database_error_is_game_exception(self):
        """DatabaseError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise DatabaseError("db connection lost")

    def test_authentication_error_is_game_exception(self):
        """AuthenticationError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise AuthenticationError("unauthorized")

    def test_image_processing_error_is_game_exception(self):
        """ImageProcessingError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise ImageProcessingError("compress failed")

    def test_sse_stream_error_is_game_exception(self):
        """SSEStreamError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise SSEStreamError("stream broken")

    def test_data_extraction_error_is_game_exception(self):
        """DataExtractionError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise DataExtractionError("parse failed")

    def test_ai_client_error_is_game_exception(self):
        """AIClientError should be catchable as GameException."""
        with pytest.raises(GameException):
            raise AIClientError("client timeout")
