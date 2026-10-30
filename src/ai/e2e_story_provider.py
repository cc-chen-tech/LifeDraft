"""Deterministic narrative responses used only by the browser E2E runtime."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from src.ai.budgets import NarrativeBudget, measure_narrative_length
from src.ai.system_prompts import OPTION_GENERATOR_EN, OPTION_GENERATOR_ZH
from src.ai.system_prompts import STORY_NOVELIST_EN, STORY_NOVELIST_ZH
from src.ai.system_prompts import STORY_CONTINUATION_EN, STORY_CONTINUATION_ZH
from src.ai.system_prompts import CONSISTENCY_VALIDATOR_ZH

_E2E_STORY_ZH = (
    "清晨的会议室里，主角把昨夜整理的访谈记录摊在桌上。投影幕上的数据并不漂亮，"
    "但其中一条用户反馈反复提到交付节奏与真实需求脱节。窗外的雨声压低了楼层里的杂音，"
    "同事们陆续坐下，等待主角说明下一步。主角没有急着替团队下结论，而是把三处相互矛盾的"
    "记录标在白板上，说明必须先核对来源，才能决定是否调整明早的汇报。有人建议立刻删去"
    "风险最大的页面，另一个人则担心这样会掩盖真正的问题。主角看着时间表，意识到今晚前"
    "必须给出一个经得起追问的方案。会议结束时，桌上留下待核对的纪要、需要补齐的数据，"
    "以及一项仍未解决的分歧。午后，主角独自回到工位，把访谈原文与产品日志逐条对照。"
    "一处看似普通的时间差终于解释了两组数据为何相反，也让原本模糊的风险有了清晰边界。"
    "主角将发现写进新的纪要，决定在明早汇报前请团队确认这项证据是否足以支持调整。"
)

_E2E_STORY_EN = (
    "In the morning meeting room, the protagonist spread interview notes "
    "across the table. A pattern in the feedback showed that the delivery "
    "schedule no longer matched the users' real needs. Rather than forcing "
    "a conclusion, the protagonist marked three conflicting records on the "
    "whiteboard and explained that the sources had to be checked before the "
    "next briefing. The team left with a clear risk to examine, missing data, "
    "one decision that still needed evidence."
)

_E2E_CONTINUATION_ZH = (
    "主角没有立刻把风险写成结论，而是先把会议纪要中的时间点、访谈原文和产品日志并排核对。"
    "傍晚前，原本相互矛盾的记录逐渐指向同一个遗漏的交接环节。主角请同事确认关键证据，"
    "再把尚未确定的部分标注为待验证，而不是仓促承诺结果。离开办公室时，明早汇报的重点"
    "已经清晰：说明发现了什么、还缺什么，以及团队需要共同决定的下一步。回家的路上，"
    "主角重新读了一遍纪要，确认没有把推测当作事实，也为第二天可能出现的追问准备了依据。"
)

_E2E_CONTINUATION_EN = (
    "The protagonist did not turn the risk into a conclusion immediately. "
    "The meeting notes, interview transcript, and product logs were checked "
    "side by side. By evening, the conflicting records pointed to one missing "
    "handoff. The next briefing would cover the evidence, the gap, and the "
    "decision the team still shared."
)

_E2E_OPTIONS_ZH = {
    "options": [
        {
            "text": "核对会议纪要中的风险点",
            "effects": {"energy": -6, "knowledge": 8, "mood": 0, "wealth": 0},
        },
        {
            "text": "约同事复盘分歧的依据",
            "effects": {"energy": -5, "knowledge": 5, "mood": 3, "wealth": 0},
        },
        {
            "text": "先补齐明早汇报的数据",
            "effects": {"energy": -7, "knowledge": 7, "mood": -1, "wealth": 0},
        },
    ]
}

_E2E_OPTIONS_EN = {
    "options": [
        {
            "text": "Verify the risks in the meeting notes",
            "effects": {"energy": -6, "knowledge": 8, "mood": 0, "wealth": 0},
        },
        {
            "text": "Review the evidence behind the disagreement",
            "effects": {"energy": -5, "knowledge": 5, "mood": 3, "wealth": 0},
        },
        {
            "text": "Fill the missing data for tomorrow's briefing",
            "effects": {"energy": -7, "knowledge": 7, "mood": -1, "wealth": 0},
        },
    ]
}


# Era-neutral, unnamed-cast prose for strict daily-mode browser tests. Unlike the
# legacy short fixture, this does not introduce technology or a modern workplace
# into historical settings. The active production budget selects whole paragraphs;
# production quick, ledger and Harness validation still run unchanged.
_DAILY_PARAGRAPHS_ZH = (
    "主角把几种不同的做法逐一想过，仍没有急着作出决定。眼前的事情看似简单，仔细推敲却各有难处。先前听到的说法并不完全一致，若只挑顺耳的部分相信，很可能错过最重要的线索。主角暂且放慢动作，把能够确认的经过和仍需查证的猜测分开，提醒自己不要因为希望尽快得到答案，就把尚未发生的结果当成事实。",
    "周围渐渐安静下来，主角再次回想事情的起点。真正需要弄清楚的不是谁说得更有把握，而是哪一种说法能与已经知道的经过相互印证。有些细节乍看无关，放回原来的顺序便显出了分量。主角沿着这些细节继续思索，既不替旁人添加未说出口的承诺，也不把一时的迟疑理解成已经确定的拒绝。",
    "一阵轻微的声响打断了思绪，主角停下来，等那点动静过去。心中的着急并没有因此消失，但仓促行动的念头稍稍退后了一步。无论最后采取哪一种办法，都应当先想清楚能够承担什么，又有哪些部分不能只凭猜测推进。主角重新审视手边的事情，把眼下能做的准备与需要进一步确认的事项分别理清。",
    "几种可能的后果逐渐明朗，各自带来的麻烦却没有自动消失。直接追问能尽快得到回应，也可能使原本平和的谈话变得紧绷；暂且观察能够保留余地，却未必能及时补上缺失的线索。主角没有把任何一条路想得过分轻松，而是仔细比较它们与当前处境是否相符，试着找出一个不必靠侥幸支撑的起点。",
    "那点尚未解开的疑问仍留在心里。主角试着换一个角度，把原本笃定的判断暂时放下，重新检视那些容易被忽略的条件。事情并非只有立即答应与彻底放弃两种走向，先把问题问清也可能成为下一步。想到这里，先前混在一起的担忧开始有了区别，哪些来自真实的困难，哪些只是对未知的想象，逐渐能够辨认。",
    "主角把想说的话在心里重新整理了一遍，去掉带着指责意味的猜测，只留下确实需要解释的部分。这样做并不能保证获得满意的回答，却至少不会先把对方推到必须辩解的位置。若回应与预想不同，还应留出继续倾听的余地。眼前的线索没有增加，处理它们的方法却比刚才清楚了一些，选择也因此有了可以衡量的依据。",
    "犹豫之中，主角注意到自己总在反复考虑最不愿发生的结果。那些担心值得认真对待，却不能代替证据，更不应让尚可补救的事情提前变成定局。与其试图一次消除所有不确定，不如先确认其中最关键的一处。主角顺着这个念头继续梳理，逐渐把庞杂的顾虑收束到一个能够提出、能够等待回应的具体问题上。",
    "接下来的行动必须与已经掌握的情况相称。主角不打算用夸大的把握换取暂时安心，也不愿因为仍有疑点便放弃所有尝试。有些准备可以现在完成，有些结论则需要等到更多信息出现。将两者分开后，事情不再是一团没有边界的压力，而成为几项可以按顺序处理的困难。主角认真想过这些区别，才再次看向眼前。",
    "先前忽略的一点细节又浮现在脑海中。它不足以证明哪一种判断正确，却说明原来的解释可能还不完整。主角把这点发现放回整体经过，避免单凭一个巧合推翻其余线索。每一种解释都需要承担同样的检验，不能因为更符合自己的希望便受到优待。思路因此慢了一些，却也少了几分盲目，留下了继续追问的空间。",
    "主角最后确认了一遍能够遵守的界限：不替旁人决定，不把猜想说成经历，也不许下自己尚无把握完成的保证。这些界限不能消除眼前的分歧，却能让下一次交谈有一个清楚的起点。比起急着证明先前的判断没有错，更重要的是让接下来的行动经得起事实检验。主角的心绪逐渐安定，仍把未解决的部分如实留在心里。",
)
_DAILY_END_ZH = "主角需要在继续核对线索、先问清关键疑点和谨慎作出回应之间选择，下一步仍由这次决定展开。"


def _daily_story_zh(budget: NarrativeBudget) -> str:
    paragraphs: list[str] = []
    for paragraph in _DAILY_PARAGRAPHS_ZH:
        paragraphs.append(paragraph)
        story = "\n\n".join([*paragraphs, _DAILY_END_ZH])
        if (
            budget.length.target_min
            <= measure_narrative_length(story, "zh")
            <= budget.length.target_max
        ):
            return story
    raise ValueError("No deterministic E2E prose fixture fits the requested budget")


def deterministic_e2e_story_origin(
    *, life_vision: str, feedback: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Return a coherent origin only for the empty-input deterministic E2E flow.

    Feedback and life vision remain model-owned so this fixture can never bypass
    their semantic or explicit date/age constraints.
    """
    if os.getenv("E2E_DETERMINISTIC_STORY") != "1":
        return None
    if life_vision.strip() or (feedback or "").strip():
        return None
    return {
        "start_date": "2026-01-01",
        "starting_age": 25,
        "era_description": "2020年代中期的现代都市",
        "life_stage_description": "正在探索职业方向与稳定生活的青年阶段",
        "world_context": "数字工具、城市工作与日常关系持续变化",
    }


def deterministic_e2e_response(
    system_prompt: str,
    *,
    user_prompt: str = "",
    narrative_budget: Optional[NarrativeBudget] = None,
) -> Optional[str]:
    """Return a contract-valid response only in E2E narrative mode."""
    if os.getenv("E2E_DETERMINISTIC_STORY") != "1":
        return None
    if system_prompt == CONSISTENCY_VALIDATOR_ZH and narrative_budget is not None:
        # Fixture for the optional model judge only, never a validator bypass.
        # Unknown/modified prose must not receive a blanket successful verdict;
        # the actual quick validator, continuity ledger and Harness still run.
        fixture = _daily_story_zh(narrative_budget)
        _, story_separator, story_and_constraints = user_prompt.partition(
            "【待检查的故事】\n"
        )
        candidate, constraints_separator, _ = story_and_constraints.partition(
            "\n\n【世界模型约束】"
        )
        if story_separator and constraints_separator and candidate.strip() == fixture:
            return json.dumps({"issues": [], "should_retry": False})
        return None
    if system_prompt.startswith(STORY_NOVELIST_ZH):
        if (
            narrative_budget is not None
            and narrative_budget.length.unit == "characters"
        ):
            return _daily_story_zh(narrative_budget)
        return _E2E_STORY_ZH
    if system_prompt.startswith(STORY_NOVELIST_EN):
        return _E2E_STORY_EN
    if system_prompt.startswith(OPTION_GENERATOR_ZH):
        if _DAILY_PARAGRAPHS_ZH[0] in user_prompt:
            return json.dumps(
                {
                    "options": [
                        {"text": text, "effects": {"energy": -3, "knowledge": 2}}
                        for text in (
                            "继续核对尚未确认的线索",
                            "先问清事情中的关键疑点",
                            "谨慎回应并保留查证余地",
                        )
                    ]
                },
                ensure_ascii=False,
            )
        return json.dumps(_E2E_OPTIONS_ZH, ensure_ascii=False)
    if system_prompt.startswith(OPTION_GENERATOR_EN):
        return json.dumps(_E2E_OPTIONS_EN)
    if system_prompt.startswith(STORY_CONTINUATION_ZH):
        return _E2E_CONTINUATION_ZH
    if system_prompt.startswith(STORY_CONTINUATION_EN):
        return _E2E_CONTINUATION_EN
    return None
