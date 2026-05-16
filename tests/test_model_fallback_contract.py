"""Model fallback chain contract tests.

Tests FallbackChain behavior with a hand-rolled stub AIClient.
No unittest.mock usage.
"""

import openai
import pytest

from src.ai.model_fallback import FallbackChain, ModelFallbackConfig


class FakeAIClient:
    """Stub AIClient for testing fallback chains."""

    def __init__(self, responses=None, errors=None):
        self.responses = responses or {}
        self.errors = errors or {}
        self.call_history = []

    def call(
        self,
        *,
        system_prompt,
        user_prompt,
        temperature=0.8,
        max_tokens=2000,
        stream_callback=None,
        model=None,
    ):
        self.call_history.append(model)
        if model in self.errors:
            raise self.errors[model]
        return self.responses.get(model, f"response-from-{model}")


def _make_retryable_error(status_code: int, message: str = "rate limited"):
    """Create an openai.APIError with a status_code attribute."""
    err = openai.APIError(message, request=None, body=None)
    err.status_code = status_code
    return err


class TestModelFallbackContract:
    """Contract tests for model fallback behavior."""

    def test_primary_model_succeeds_no_fallback(self):
        """Primary model succeeds — fallback chain should not be used."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5", "local"],
        )
        client = FakeAIClient(responses={"gpt-4": "success"})
        chain = FallbackChain(config, client)

        response, model = chain.call_with_fallback(system_prompt="sys", user_prompt="user")

        assert response == "success"
        assert model == "gpt-4"
        assert client.call_history == ["gpt-4"]

    def test_fallback_to_second_model_on_error(self):
        """Primary fails with retryable error — should fallback to second model."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5", "local"],
        )
        client = FakeAIClient(
            errors={"gpt-4": _make_retryable_error(429, "rate limited")},
            responses={"gpt-3.5": "fallback-response"},
        )
        chain = FallbackChain(config, client)

        response, model = chain.call_with_fallback(system_prompt="sys", user_prompt="user")

        assert response == "fallback-response"
        assert model == "gpt-3.5"
        assert client.call_history == ["gpt-4", "gpt-3.5"]

    def test_fallback_to_third_model(self):
        """First two models fail — should fallback to third."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5", "local"],
        )
        client = FakeAIClient(
            errors={
                "gpt-4": _make_retryable_error(503, "down"),
                "gpt-3.5": _make_retryable_error(503, "down"),
            },
            responses={"local": "local-response"},
        )
        chain = FallbackChain(config, client)

        response, model = chain.call_with_fallback(system_prompt="sys", user_prompt="user")

        assert response == "local-response"
        assert model == "local"
        assert client.call_history == ["gpt-4", "gpt-3.5", "local"]

    def test_all_models_fail_raises_last_error(self):
        """All models fail — should raise the last error."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5"],
        )
        client = FakeAIClient(
            errors={
                "gpt-4": _make_retryable_error(429, "rate limited"),
                "gpt-3.5": _make_retryable_error(429, "also rate limited"),
            },
        )
        chain = FallbackChain(config, client)

        with pytest.raises(openai.APIError):
            chain.call_with_fallback(system_prompt="sys", user_prompt="user")

        assert client.call_history == ["gpt-4", "gpt-3.5"]

    def test_non_retryable_error_raises_immediately(self):
        """Non-retryable error (e.g. 400) should not trigger fallback."""
        bad_req = openai.APIError("bad request", request=None, body=None)
        bad_req.status_code = 400

        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5"],
        )
        client = FakeAIClient(errors={"gpt-4": bad_req})
        chain = FallbackChain(config, client)

        with pytest.raises(openai.APIError):
            chain.call_with_fallback(system_prompt="sys", user_prompt="user")

        assert client.call_history == ["gpt-4"]

    def test_status_callback_triggered_on_fallback(self):
        """Status callback should be called when fallback occurs."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5"],
        )
        client = FakeAIClient(
            errors={"gpt-4": _make_retryable_error(429, "rate limited")},
            responses={"gpt-3.5": "ok"},
        )
        chain = FallbackChain(config, client)
        statuses = []

        chain.call_with_fallback(
            system_prompt="sys",
            user_prompt="user",
            status_callback=lambda s: statuses.append(s),
        )

        assert "model_fallback" in statuses

    def test_get_available_models_returns_all(self):
        """get_available_models should return primary + fallbacks."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5", "local"],
        )
        chain = FallbackChain(config, FakeAIClient())

        models = chain.get_available_models()

        assert models == ["gpt-4", "gpt-3.5", "local"]

    def test_max_fallback_attempts_limits_retries(self):
        """max_fallback_attempts should limit how many models are tried."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5", "local", "tiny"],
            max_fallback_attempts=2,
        )
        client = FakeAIClient(
            errors={
                "gpt-4": _make_retryable_error(503, "down"),
                "gpt-3.5": _make_retryable_error(503, "down"),
            },
        )
        chain = FallbackChain(config, client)

        with pytest.raises(openai.APIError):
            chain.call_with_fallback(system_prompt="sys", user_prompt="user")

        # Only tried primary + 1 fallback = 2 attempts
        assert len(client.call_history) == 2

    def test_stream_callback_passed_to_client(self):
        """stream_callback should be forwarded to client.call."""
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5"],
        )
        client = FakeAIClient(responses={"gpt-4": "streamed"})
        chain = FallbackChain(config, client)
        chunks = []

        def stream_cb(chunk):
            chunks.append(chunk)

        response, _ = chain.call_with_fallback(
            system_prompt="sys",
            user_prompt="user",
            stream_callback=stream_cb,
        )

        assert response == "streamed"
