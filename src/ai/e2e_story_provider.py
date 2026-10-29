"""Deterministic narrative responses used only by the browser E2E runtime."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from src.ai.system_prompts import OPTION_GENERATOR_EN, OPTION_GENERATOR_ZH
from src.ai.system_prompts import STORY_NOVELIST_EN, STORY_NOVELIST_ZH
from src.ai.system_prompts import STORY_CONTINUATION_EN, STORY_CONTINUATION_ZH
from src.ai.system_prompts import CONSISTENCY_VALIDATOR_EN, CONSISTENCY_VALIDATOR_ZH
from src.ai.budgets import NarrativeBudget, measure_narrative_length

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

# Full scenes, rather than padding or a relaxed validator: the production daily
# pipeline uses localized budgets (400/800/1200 minimum characters by tier).
_E2E_STORY_DETAILS_ZH = (
    "\n\n主角翻到最早的一页记录，发现当时的约定与后来转述的说法并不相同。"
    "那一页旁边留着清楚的日期，却没有标明修改缘由。主角拿出另一份保存完整的原稿，"
    "从开头逐句核对，先圈出能够确认的事实，再把仍需询问的地方记在旁边。"
    "这项工作比预想中缓慢，几次看似已经找到答案，又被后面的细节推翻。"
    "主角决定暂时保留两种解释，不让自己的期待替代证据。窗外渐渐安静下来，"
    "桌边的茶已经凉了，纸上的线索却终于有了可以追索的顺序。"
    "\n\n接下来需要核实的是交接过程。主角把每次交付的内容与接收记录逐项排开，"
    "发现遗漏并非出在最后一步，而是在最初的约定中留下了两种理解。"
    "如果只要求最后接手的人补救，同样的分歧还会再次发生。主角重新写下问题，"
    "把责任判断改成需要共同确认的事项，并为每一项留下原始记录的位置。"
    "有些细节依然无法解释，主角没有删去它们，而是注明目前知道的范围。"
    "这样的纪要没有漂亮的结论，却能够让后来的人沿着同一条线索重新检查。"
    "\n\n傍晚的光移到门边，主角再次想起最初想做成这件事的原因。"
    "大家需要的并不是一份看起来毫无缺点的答复，而是能够继续向前的可靠依据。"
    "主角把已经确认的部分另抄一页，准备先请相关的人核对，避免新的转述再次改变原意。"
    "每一个问题都写得尽量具体，既说明出处，也留下对方补充的余地。"
    "对于尚未确认的安排，主角只写下下一步要查什么，没有许下无法兑现的保证。"
    "门外有人经过，脚步声停了一下又远去，主角把纸页按顺序压好，继续检查最后几处细节。"
    "\n\n最后一处矛盾出现在两份记录对同一件事的描述里。主角先看各自记录的时间，"
    "再对照当时能够知道的信息，终于发现双方看到的其实是不同阶段的情况。"
    "这个发现并没有解决全部问题，却让原先互相指责的两种说法都有了合理的位置。"
    "主角将新的解释放在待确认栏里，提醒自己仍须询问当事人，不能只凭纸面上的推演定论。"
    "为了让明天的讨论更有效，主角列出几种可以采取的做法，分别写明还需要哪些依据。"
    "此时天色已经暗了，桌上的材料终于不再是一堆相互冲突的纸页，而是一条能够继续调查的线索。"
    "\n\n收拾东西前，主角又读了一遍准备好的问题，把过于笼统的词语逐一改掉。"
    "哪些地方已经核实，哪些地方只是推测，哪些地方需要别人的经验，纸上都有了明确区分。"
    "主角知道明天的讨论未必顺利，有人可能仍然坚持原来的解释，也有人会带来新的记录。"
    "但只要大家能够从同一份事实开始，分歧就有机会变成具体的工作，而不是反复争论。"
    "主角合上本子，决定先保留这份完整的纪要，再选择最需要核实的一处继续追问。"
)

_E2E_ANCIENT_STORY_ZH = (
    "李逍遥想弄清旧账册中失踪货物的去向，却还缺少能够相互印证的证言。\n\n"
    "清晨的书铺里，李逍遥与赵灵儿把昨日找到的账册放在木桌上。窗外的雨刚停，"
    "屋檐落下的水珠敲着石阶。两人先按日期排好散乱的纸页，发现同一批货物在两处留下了不同的交付记录。"
    "赵灵儿指着其中一行字，提醒李逍遥留意墨迹的深浅，但两人都没有急着认定是谁改过账目。"
    "李逍遥记下需要询问的问题，准备先找原来的凭据核对，再决定是否沿着线索去河边查看。"
)


def _budgeted_story_zh(user_prompt: str, budget: Optional[NarrativeBudget]) -> str:
    story = _E2E_ANCIENT_STORY_ZH if "南宋" in user_prompt else _E2E_STORY_ZH
    minimum = budget.length.target_min if budget is not None else 800
    # Stop at a complete sentence; never manufacture a truncated last paragraph.
    for sentence in re.findall(r"[^。]*。", _E2E_STORY_DETAILS_ZH):
        if measure_narrative_length(story, "zh") >= minimum:
            break
        story += sentence
    return story


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


def deterministic_e2e_response(
    system_prompt: str,
    *,
    user_prompt: str = "",
    budget: Optional[NarrativeBudget] = None,
) -> Optional[str]:
    """Return a contract-valid response only in E2E narrative mode."""
    if os.getenv("E2E_DETERMINISTIC_STORY") != "1":
        return None
    if system_prompt in (CONSISTENCY_VALIDATOR_ZH, CONSISTENCY_VALIDATOR_EN):
        # Replace only the optional model judge at the provider boundary.
        # The real shape, era, required-cast and continuity gates still run.
        return json.dumps({"issues": [], "should_retry": False})
    if system_prompt.startswith(STORY_NOVELIST_ZH):
        return _budgeted_story_zh(user_prompt, budget)
    if system_prompt.startswith(STORY_NOVELIST_EN):
        return _E2E_STORY_EN
    if system_prompt.startswith(OPTION_GENERATOR_ZH):
        if "李逍遥" in user_prompt and "账册" in user_prompt:
            return json.dumps(
                {
                    "options": [
                        {"text": text, "effects": {"energy": -5, "knowledge": 5}}
                        for text in [
                            "核对账册中两份交付记录",
                            "请赵灵儿一同寻找原始凭据",
                            "沿着线索去河边查看",
                        ]
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
