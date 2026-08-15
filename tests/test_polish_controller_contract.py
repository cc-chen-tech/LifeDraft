"""Polish controller contract tests.

No mocks. Tests prompt building and polish loop with stubs.
"""

from src.ai.harness.polish_controller import PolishController


class FakeAIClient:
    """Stub AI client for testing polish controller."""

    def __init__(self, response="polished text"):
        self.response = response
        self.calls = []

    def call(
        self,
        *,
        system_prompt,
        user_prompt,
        temperature=0.4,
        max_tokens=8192,
        request_timeout=None,
        generation_tracker=None,
    ):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "request_timeout": request_timeout,
                "generation_tracker": generation_tracker,
            }
        )
        return self.response


class FakeDiagnosticReport:
    """Stub diagnostic report."""

    def __init__(self, summary="需要修正"):
        self.summary = summary


class TestPolishControllerContract:
    """Contract tests for polish controller."""

    def test_polish_returns_text(self):
        """polish should return the AI-polished text."""
        client = FakeAIClient("refined story")
        controller = PolishController(client)
        report = FakeDiagnosticReport()

        result = controller.polish(
            story_text="original story",
            diagnostic_report=report,
            original_prompt="write a story",
            sys_prompt="system",
        )

        assert result == "refined story"

    def test_polish_calls_client_once_per_round(self):
        """Default max_rounds=2 should call client twice."""
        client = FakeAIClient()
        controller = PolishController(client)
        report = FakeDiagnosticReport()

        controller.polish(
            story_text="story",
            diagnostic_report=report,
            original_prompt="prompt",
            sys_prompt="system",
        )

        assert len(client.calls) == 2

    def test_polish_calls_client_custom_rounds(self):
        """Custom max_rounds should control call count."""
        client = FakeAIClient()
        controller = PolishController(client)
        report = FakeDiagnosticReport()

        controller.polish(
            story_text="story",
            diagnostic_report=report,
            original_prompt="prompt",
            sys_prompt="system",
            max_rounds=1,
        )

        assert len(client.calls) == 1

    def test_polish_passes_system_prompt(self):
        """System prompt should be forwarded to client.call."""
        client = FakeAIClient()
        controller = PolishController(client)
        report = FakeDiagnosticReport()

        controller.polish(
            story_text="story",
            diagnostic_report=report,
            original_prompt="prompt",
            sys_prompt="custom-system-prompt",
        )

        assert client.calls[0]["system_prompt"] == "custom-system-prompt"

    def test_polish_uses_low_temperature(self):
        """Polish should use conservative temperature."""
        client = FakeAIClient()
        controller = PolishController(client)
        report = FakeDiagnosticReport()

        controller.polish(
            story_text="story",
            diagnostic_report=report,
            original_prompt="prompt",
            sys_prompt="system",
        )

        assert client.calls[0]["temperature"] == 0.4
        assert client.calls[0]["max_tokens"] == 8192

    def test_build_polish_prompt_contains_story(self):
        """Prompt should contain the story text."""
        client = FakeAIClient()
        controller = PolishController(client)
        report = FakeDiagnosticReport()

        controller.polish(
            story_text="THE STORY TEXT",
            diagnostic_report=report,
            original_prompt="ORIGINAL PROMPT",
            sys_prompt="system",
        )

        prompt = client.calls[0]["user_prompt"]
        assert "THE STORY TEXT" in prompt
        assert "ORIGINAL PROMPT" in prompt

    def test_build_polish_prompt_contains_report_summary(self):
        """Prompt should contain diagnostic report summary."""
        client = FakeAIClient()
        controller = PolishController(client)
        report = FakeDiagnosticReport("约束违反: 太长了")

        controller.polish(
            story_text="story",
            diagnostic_report=report,
            original_prompt="prompt",
            sys_prompt="system",
        )

        prompt = client.calls[0]["user_prompt"]
        assert "约束违反: 太长了" in prompt

    def test_build_polish_prompt_default_summary(self):
        """Report without summary should use default message."""
        client = FakeAIClient()
        controller = PolishController(client)
        report = FakeDiagnosticReport()  # no summary set

        controller.polish(
            story_text="story",
            diagnostic_report=report,
            original_prompt="prompt",
            sys_prompt="system",
        )

        prompt = client.calls[0]["user_prompt"]
        assert "故事存在约束违反" in prompt

    def test_polish_carries_forward_intermediate_text(self):
        """Each round should polish the previous round's output."""
        client = FakeAIClient("round-1-output")
        controller = PolishController(client)
        report = FakeDiagnosticReport()

        controller.polish(
            story_text="original",
            diagnostic_report=report,
            original_prompt="prompt",
            sys_prompt="system",
            max_rounds=2,
        )

        # Second round should contain the first round's output
        second_prompt = client.calls[1]["user_prompt"]
        assert "round-1-output" in second_prompt
