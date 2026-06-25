/**
 * choiceUtils.ts 故事文本追加测试
 *
 * 验证 handleChoiceComplete 在 choice complete-only 场景下补写故事文本。
 * SSE onStory 负责流式追加；如果 choice stream 没有 story chunk，
 * complete payload 中的 story_continuation 是最后的兜底文本来源。
 */

import { useGameStore } from "@/stores/useGameStore";
import { handleChoiceComplete } from "@/hooks/game/choiceUtils";
import { checkAndClearRetry, markRetry } from "@/hooks/game/eventUtils";

describe("handleChoiceComplete — story text append on retry", () => {
  beforeEach(() => {
    checkAndClearRetry();
    useGameStore.setState({ storyText: "" });
  });

  it("retry complete-only 时补写后端返回的选择结果", () => {
    useGameStore.setState({ storyText: "第一章：开局。" });
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

    expect(handlers.setStoryText).toHaveBeenCalledWith(
      "第一章：开局。\n\n你选择了继续前进。"
    );
    // 处理完成后 phase 应为 "result"
    expect(handlers.setPhase).toHaveBeenCalledWith("result");
    // 处理完成标志已清除
    expect(handlers.setProcessing).toHaveBeenCalledWith(false);
  });

  it("非 retry complete-only 时补写后端返回的选择结果", () => {
    useGameStore.setState({ storyText: "第一章：开局。" });

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

    expect(handlers.setStoryText).toHaveBeenCalledWith(
      "第一章：开局。\n\n你选择了继续前进。"
    );
  });

  it("已由 SSE 写入相同 continuation 时不重复修改 storyText", () => {
    useGameStore.setState({ storyText: "第一章：开局。\n\n你选择了继续前进。" });

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

    expect(handlers.setStoryText).not.toHaveBeenCalled();
    expect(handlers.setPhase).toHaveBeenCalledWith("result");
  });

  it("retry 但 continuation 为空时不应改变现有文本", () => {
    useGameStore.setState({ storyText: "第一章：开局。" });
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
    expect(useGameStore.getState().storyText).toBe("第一章：开局。");
  });
});
