/**
 * choiceUtils.ts 故事文本追加测试
 *
 * 验证 handleChoiceComplete 在 retry 场景下正确处理 phase 转换。
 * 注意：handleChoiceComplete 不再直接修改 storyText（由 handleEventComplete 处理），
 * 仅负责 phase 转换和状态更新。
 */

import { useEventStore } from "@/stores/useEventStore";
import { handleChoiceComplete } from "@/hooks/game/choiceUtils";
import { markRetry } from "@/hooks/game/eventUtils";

describe("handleChoiceComplete — story text append on retry", () => {
  beforeEach(() => {
    useEventStore.setState({ storyText: "" });
  });

  it("retry 时 handleChoiceComplete 应正确检测并清除重试标记", () => {
    useEventStore.setState({ storyText: "第一章：开局。" });
    markRetry(); // 标记发生了重试

    const handlers = {
      setProcessing: jest.fn(),
      setConnectionStatus: jest.fn(),
      setReconnectAttempt: jest.fn(),
      setRoundSummary: jest.fn(),
      setSummaryText: jest.fn(),
      setCurrentEvent: jest.fn(),
      setGameOver: jest.fn(),
      setOptions: jest.fn(),
      setStoryText: jest.fn(),
      setPhase: jest.fn(),
      generatingRef: { current: false },
    };

    handleChoiceComplete(
      {
        story_continuation: "你选择了继续前进。",
      },
      handlers
    );

    // handleChoiceComplete 在 retry 后不应通过 setStoryText 修改文本
    expect(handlers.setStoryText).not.toHaveBeenCalled();
    // 处理完成后 phase 应为 "result"
    expect(handlers.setPhase).toHaveBeenCalledWith("result");
    // 处理完成标志已清除
    expect(handlers.setProcessing).toHaveBeenCalledWith(false);
  });

  it("非 retry 时不应修改 storyText（由 SSE onStory 负责追加）", () => {
    useEventStore.setState({ storyText: "第一章：开局。" });

    const handlers = {
      setProcessing: jest.fn(),
      setConnectionStatus: jest.fn(),
      setReconnectAttempt: jest.fn(),
      setRoundSummary: jest.fn(),
      setSummaryText: jest.fn(),
      setCurrentEvent: jest.fn(),
      setGameOver: jest.fn(),
      setOptions: jest.fn(),
      setStoryText: jest.fn(),
      setPhase: jest.fn(),
      generatingRef: { current: false },
    };

    handleChoiceComplete(
      {
        story_continuation: "你选择了继续前进。",
      },
      handlers
    );

    // 正常流程下 handleChoiceComplete 不应修改 storyText
    expect(handlers.setStoryText).not.toHaveBeenCalled();
  });

  it("complete payload 带 event_description 时也不应覆盖 SSE 已显示的故事", () => {
    useEventStore.setState({ storyText: "第一章：开局。\n\n你选择了继续前进。" });

    const handlers = {
      setProcessing: jest.fn(),
      setConnectionStatus: jest.fn(),
      setReconnectAttempt: jest.fn(),
      setRoundSummary: jest.fn(),
      setSummaryText: jest.fn(),
      setCurrentEvent: jest.fn(),
      setGameOver: jest.fn(),
      setOptions: jest.fn(),
      setStoryText: jest.fn(),
      setPhase: jest.fn(),
      generatingRef: { current: false },
    };

    handleChoiceComplete(
      {
        event_description: "你选择了继续前进。",
      },
      handlers
    );

    expect(handlers.setStoryText).not.toHaveBeenCalled();
    expect(handlers.setPhase).toHaveBeenCalledWith("result");
  });

  it("retry 但 continuation 为空时不应改变现有文本", () => {
    useEventStore.setState({ storyText: "第一章：开局。" });
    markRetry();

    const handlers = {
      setProcessing: jest.fn(),
      setConnectionStatus: jest.fn(),
      setReconnectAttempt: jest.fn(),
      setRoundSummary: jest.fn(),
      setSummaryText: jest.fn(),
      setCurrentEvent: jest.fn(),
      setGameOver: jest.fn(),
      setOptions: jest.fn(),
      setStoryText: jest.fn(),
      setPhase: jest.fn(),
      generatingRef: { current: false },
    };

    handleChoiceComplete(
      {
        story_continuation: "",
      },
      handlers
    );

    expect(handlers.setStoryText).not.toHaveBeenCalled();
    expect(useEventStore.getState().storyText).toBe("第一章：开局。");
  });
});
