/**
 * choiceUtils.ts 故事文本追加测试
 *
 * 验证 handleChoiceComplete 在 choice complete-only 场景下不直接补写故事文本。
 * SSE onStory 负责流式追加；如果 choice stream 没有 story chunk，
 * 同步 fallback 和 round_history recovery 负责兜底文本来源。
 */

import { useGameStore } from "@/stores/useGameStore";
import { handleChoiceComplete } from "@/hooks/game/choiceUtils";

describe("handleChoiceComplete — story text ownership", () => {
  beforeEach(() => {
    useGameStore.setState({ storyText: "" });
  });

  it("complete-only 时不直接补写后端返回的选择结果", () => {
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

    expect(handlers.setStoryText).not.toHaveBeenCalled();
    // 处理完成后 phase 应为 "result"
    expect(handlers.setPhase).toHaveBeenCalledWith("result");
    // 处理完成标志已清除
    expect(handlers.setProcessing).toHaveBeenCalledWith(false);
  });

  it("另一 complete-only payload 也不直接补写后端返回的选择结果", () => {
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

    expect(handlers.setStoryText).not.toHaveBeenCalled();
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

  it("complete payload 带 event_description 时也不应覆盖 SSE 已显示的故事", () => {
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
        event_description: "你选择了继续前进。",
      },
      handlers
    );

    expect(handlers.setStoryText).not.toHaveBeenCalled();
    expect(handlers.setPhase).toHaveBeenCalledWith("result");
  });

  it("continuation 为空时不应改变现有文本", () => {
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
        story_continuation: "",
      },
      handlers
    );

    expect(handlers.setStoryText).not.toHaveBeenCalled();
    expect(useGameStore.getState().storyText).toBe("第一章：开局。");
  });
});
