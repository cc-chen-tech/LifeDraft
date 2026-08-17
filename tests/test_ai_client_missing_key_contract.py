"""Contracts for using game state paths without configured AI credentials."""

import pytest

from config.settings import settings
from src.ai.client import AIClient

pytestmark = [pytest.mark.unit]



def test_ai_client_without_api_key_defers_error_until_model_call(monkeypatch):
    """Constructing stateful services must not require live AI credentials."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    client = AIClient()

    assert client.api_key is None
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        client.call("system", "user")
