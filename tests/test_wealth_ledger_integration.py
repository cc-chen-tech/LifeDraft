"""Cross-consumer integration coverage for the P1-8 wealth authority."""

from __future__ import annotations

import json

from src.ai.consistency_validator import ConsistencyValidator
from src.ai.summary_generator import SummaryGenerator
from src.game.assistant_grounding import AssistantEvidence
from src.game.round.finalizer import RoundFinalizer
from src.game.state import PlayerState
from src.game.story_service import StoryService
from src.game.wealth_ledger import WealthLedger
from src.game.world_model import WorldModel


class _NoopAIClient:
    def call(self, **_kwargs):
        raise AssertionError(
            "deterministic wealth rejection must run before the AI judge"
        )


class _SummaryClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.prompts: list[str] = []

    def call(self, **kwargs):
        self.prompts.append(kwargs["user_prompt"])
        return json.dumps(self.payload, ensure_ascii=False)


class _ContinuationGenerator:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.ai_client = _NoopAIClient()
        self.prompts: list[str] = []

    def generate_completion(self, **kwargs):
        self.prompts.append(kwargs["prompt"])
        return self.responses.pop(0)


class _WeeklyAI:
    def __init__(self):
        self.kwargs = None

    def generate_weekly_summary(self, **kwargs):
        self.kwargs = kwargs
        return {
            "summary": "本周余额为1,000元。",
            "bonus_effects": {"wealth": 20},
        }


class _CharacterCreator:
    @staticmethod
    def check_and_fix_missing_attributes(_state):
        return None


def _state(wealth: int = 10_000) -> PlayerState:
    state = PlayerState(
        player_name="林岚",
        wealth=wealth,
        week=0,
        current_round=0,
        rounds_per_week=3,
        character_settings={
            "occupation": {"occupation": "建筑师"},
            "wealth": {"currency": "¥", "currency_name": "元"},
        },
    )
    ledger = WealthLedger.from_player_state(state)
    ledger.persist(state)
    return state


def test_world_model_injects_wealth_authority_after_legacy_constraints() -> None:
    state = _state(12_500)
    ledger = WealthLedger.from_player_state(state)
    ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=2_500,
        reason="项目奖金",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    constraints = WorldModel.from_player_state(state).build_constraints_text("zh")

    assert "权威财富账本" in constraints
    assert "当前权威余额：15,000元" in constraints
    assert constraints.rindex("权威财富账本") > constraints.rindex("权威连续性事实账本")


def test_consistency_validator_rejects_invented_balance_before_ai_call() -> None:
    state = _state(10_500)
    world_model = WorldModel.from_player_state(state)
    validator = ConsistencyValidator(_NoopAIClient())

    result = validator.validate_story(
        story_text="林岚打开银行应用，账户余额显示为50,000元。",
        world_model=world_model,
        player_state_dict=state.to_dict(),
        character_settings=state.character_settings,
        language="zh",
        run_ai_validation=False,
    )

    assert result.passed is False
    assert result.critical_issues[0].dimension == "wealth"
    assert "10,500" in result.fix_instructions


def test_story_continuation_retries_then_sanitizes_unsupported_money_claims() -> None:
    state = _state(10_500)
    wrong = "林岚查看账户，余额为50,000元。客户随后又把奖金8,000元打入账户。"
    generator = _ContinuationGenerator([wrong, wrong])
    service = StoryService(generator, language="zh")

    result = service.generate_story_continuation(
        event_description="客户讨论项目结算。",
        chosen_option="接受既定的无额外报酬方案",
        effects={"wealth": 0},
        character_settings=state.character_settings,
        player_state=state.to_dict(),
    )

    assert len(generator.prompts) == 2
    assert "权威财富账本冲突" in generator.prompts[1]
    assert "余额为10,500元" in result
    assert "奖金一笔款项" in result
    assert "50,000" not in result
    assert "8,000" not in result


def test_weekly_summary_uses_balance_context_and_sanitizes_wrong_balance() -> None:
    state = _state(10_500)
    client = _SummaryClient(
        {"summary": "本周结束时账户余额为99,999元。", "bonus_effects": {}}
    )
    generator = SummaryGenerator(client)

    result = generator.generate_weekly_summary(
        [{"summary": "完成项目", "choice": "交付", "effects": {"wealth": 500}}],
        state.character_settings,
        "zh",
        game_date_info=state.get_game_date_info(),
        wealth_context={
            "current_balance": state.wealth,
            "wealth_ledger": state.wealth_ledger,
        },
    )

    assert "当前权威余额：10,500元" in client.prompts[0]
    assert result["summary"] == "本周结束时账户余额为10,500元。"


def test_weekly_bonus_is_a_source_linked_transaction_and_summary_gets_context() -> None:
    state = _state(1_000)
    state.round_history = [
        {"week": 0, "round": 0, "summary": "完成任务", "choice": "交付", "effects": {}}
    ]
    weekly_ai = _WeeklyAI()
    finalizer = RoundFinalizer(
        player_state_getter=lambda: state,
        ai_generator=weekly_ai,
        language_getter=lambda: "zh",
        story_service=None,
        character_creator=_CharacterCreator(),
    )
    finalizer._start_post_week_enrichment = lambda _week: None

    result: dict = {}
    finalizer.finalize_week(result)

    assert weekly_ai.kwargs["wealth_context"]["current_balance"] == 1_000
    assert state.wealth == 1_020
    transaction = state.wealth_ledger["transactions"][-1]
    assert transaction["transaction_id"] == "weekly-bonus:w0"
    assert transaction["opening_balance"] == 1_000
    assert transaction["applied_delta"] == 20
    assert transaction["closing_balance"] == 1_020


def test_assistant_evidence_uses_same_balance_and_transaction_records() -> None:
    state = _state(10_000)
    ledger = WealthLedger.from_player_state(state)
    ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=-500,
        reason="支付报名费",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    evidence = AssistantEvidence.from_player_state(state)

    assert evidence.records["wealth:balance"].fact == "9,500元"
    transaction = evidence.records["wealth:transaction:choice:w0-r0"]
    assert "期初10,000" in transaction.fact
    assert "变动-500" in transaction.fact
    assert "期末9,500" in transaction.fact


def test_assistant_keeps_wealth_authority_when_settings_fill_evidence_limit() -> None:
    state = _state(4_321)
    state.character_settings = {
        "wealth": {"currency_name": "贯"},
        "verbose": {f"field_{index}": index for index in range(220)},
    }

    evidence = AssistantEvidence.from_player_state(state)

    assert evidence.records["wealth:balance"].fact == "4,321贯"


def test_assistant_keeps_wealth_authority_when_continuity_fills_evidence_limit() -> (
    None
):
    state = _state(7_654)
    state.character_settings = {"wealth": {"currency_name": "元"}}
    state.continuity_ledger = {
        "version": 1,
        "timeline": [
            {
                "event_id": f"event-{index}",
                "status": "committed",
                "summary": f"事件{index}",
                "week": index // 3,
                "round": index % 3,
            }
            for index in range(180)
        ],
    }

    evidence = AssistantEvidence.from_player_state(state)

    assert evidence.records["wealth:balance"].fact == "7,654元"
