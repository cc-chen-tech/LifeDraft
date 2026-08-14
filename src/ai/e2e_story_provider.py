"""Deterministic narrative responses used only by the browser E2E runtime."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from src.ai.system_prompts import OPTION_GENERATOR_EN, OPTION_GENERATOR_ZH
from src.ai.system_prompts import STORY_NOVELIST_EN, STORY_NOVELIST_ZH
from src.ai.system_prompts import STORY_CONTINUATION_EN, STORY_CONTINUATION_ZH


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


def deterministic_e2e_response(system_prompt: str) -> Optional[str]:
    """Return a contract-valid response only in E2E narrative mode."""
    if os.getenv("E2E_DETERMINISTIC_STORY") != "1":
        return None
    if system_prompt.startswith(STORY_NOVELIST_ZH):
        return _E2E_STORY_ZH
    if system_prompt.startswith(STORY_NOVELIST_EN):
        return _E2E_STORY_EN
    if system_prompt.startswith(OPTION_GENERATOR_ZH):
        return json.dumps(_E2E_OPTIONS_ZH, ensure_ascii=False)
    if system_prompt.startswith(OPTION_GENERATOR_EN):
        return json.dumps(_E2E_OPTIONS_EN)
    if system_prompt.startswith(STORY_CONTINUATION_ZH):
        return _E2E_CONTINUATION_ZH
    if system_prompt.startswith(STORY_CONTINUATION_EN):
        return _E2E_CONTINUATION_EN
    return None
