/**
 * choiceUtils.ts 故事文本追加测试
 *
 * 验证 handleChoiceComplete 在 retry 场景下使用 appendStoryText 追加 continuation，
 * 而非 setStoryText 替换全部文本。
 */

import { useEventStore } from "@/stores/useEventStore";
import { handleChoiceComplete } from "@/hooks/game/choiceUtils";
import { markRetry } from "@/hooks/game/eventUtils";

describe("handleChoiceComplete — story text append on retry", () => {
  beforeEach(() => {
    useEventStore.setState({ storyText: "" });
  });

  it("retry 时应将 story_continuation 追加到现有文本", () => {
    useEventStore.setState({ storyText: "第一章：开局。" });
    markRetry(); // 标记发生了重试

    const handlers = {
      setProcessing: () => {},
      setConnectionStatus: () => {},
      setReconnectAttempt: () => {},
      setRoundSummary: () => {},
      setSummaryText: () => {},
      setCurrentEvent: () => {},
      setGameOver: () => {},
      setOptions: () => {},
      setStoryText: () => {},
      setPhase: () => {},
      generatingRef: { current: false },
    };

    handleChoiceComplete(
      {
        story_continuation: "你选择了继续前进。",
      },
      handlers
    );

    expect(useEventStore.getState().storyText).toBe(
      "第一章：开局。你选择了继续前进。"
    );
  });

  it("非 retry 时不应修改 storyText（由 SSE onStory 负责追加）", () => {
    useEventStore.setState({ storyText: "第一章：开局。" });
    // 不调用 markRetry()，模拟正常流程

    const handlers = {
      setProcessing: () => {},
      setConnectionStatus: () => {},
      setReconnectAttempt: () => {},
      setRoundSummary: () => {},
      setSummaryText: () => {},
      setCurrentEvent: () => {},
      setGameOver: () => {},
      setOptions: () => {},
      setStoryText: () => {},
      setPhase: () => {},
      generatingRef: { current: false },
    };

    handleChoiceComplete(
      {
        story_continuation: "你选择了继续前进。",
      },
      handlers
    );

    // 正常流程下 handleChoiceComplete 不应修改 storyText
    expect(useEventStore.getState().storyText).toBe("第一章：开局。");
  });

  it("retry 但 continuation 为空时不应改变现有文本", () => {
    useEventStore.setState({ storyText: "第一章：开局。" });
    markRetry();

    const handlers = {
      setProcessing: () => {},
      setConnectionStatus: () => {},
      setReconnectAttempt: () => {},
      setRoundSummary: () => {},
      setSummaryText: () => {},
      setCurrentEvent: () => {},
      setGameOver: () => {},
      setOptions: () => {},
      setStoryText: () => {},
      setPhase: () => {},
      generatingRef: { current: false },
    };

    handleChoiceComplete(
      {
        story_continuation: "",
      },
      handlers
    );

    expect(useEventStore.getState().storyText).toBe("第一章：开局。");
  });
});
