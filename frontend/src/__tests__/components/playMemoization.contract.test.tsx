/**
 * P2-性能优化（前端 Step 1）：PlayReadingFrame / PlayPhaseContent memo 契约。
 *
 * 流式期间页面每个 chunk 都会重渲染；memo 化的框架组件在 props 引用不变时
 * 必须跳过重渲染，让工具栏/框架不再随 story 文本变化而重渲染。
 */
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createElement, useRef } from "react";

import { PlayReadingFrame } from "@/components/game/PlayReadingFrame";
import { PlayPhaseContent } from "@/components/game/PlayPhaseContent";

function Probe({ label }: { label: string }) {
  const renders = useRef(0);
  renders.current += 1;
  return createElement("span", { "data-renders": renders.current }, label);
}

function FrameHarness({ children }: { children: ReactElement }) {
  const stableTools = {
    isSaving: false,
    isStoryBusy: false,
    isViewingHistory: false,
    constraintLevel: "expert" as const,
    narrativeStyleId: "",
    narrativeStyles: [],
    narrativeStylesLoading: false,
    rewriteDisabled: false,
    rewriteDisabledReason: "",
    soundAvailable: false,
    enableSceneImage: true,
    onSave: () => undefined,
    onOpenHistory: () => undefined,
    onOpenCollection: () => undefined,
    onOpenChat: () => undefined,
    onOpenRewrite: () => undefined,
    onOpenSummary: () => undefined,
    onRegenerate: () => undefined,
    onOpenSound: () => undefined,
    onHome: () => undefined,
    onConstraintLevelChange: () => undefined,
    onNarrativeStyleChange: () => undefined,
    onSceneImageChange: () => undefined,
    onRequestNarrativeStyles: () => undefined,
    onOpenTools: () => undefined,
    onToolsOpenChange: () => undefined,
    isDailyTimeline: false,
  };
  return createElement(
    PlayReadingFrame,
    {
      playerState: null,
      progress: null,
      isViewingHistory: false,
      toolsProps: stableTools,
    },
    children,
  );
}

describe("memoized play components", () => {
  it("PlayReadingFrame skips re-render when props are referentially stable", () => {
    const probe = createElement(Probe, { label: "frame" });
    const first = render(createElement(FrameHarness, {}, probe));
    expect(first.getByText("frame").getAttribute("data-renders")).toBe("1");
    first.rerender(createElement(FrameHarness, {}, probe));
    expect(first.getByText("frame").getAttribute("data-renders")).toBe("1");
  });

  it("PlayPhaseContent skips re-render when its props are referentially stable", () => {
    const probe = createElement(Probe, { label: "content" });
    const props = {
      phase: "options" as const,
      isViewingHistory: false,
      displayText: "固定文本",
      historyPosition: null,
      onBackToCurrent: () => undefined,
      loading: {
        visible: false,
        phase: "loading_context" as const,
        operation: "event" as const,
        delayed: false,
        transport: "active" as const,
        onAction: () => undefined,
      },
      media: probe,
      roundSummary: null,
      inlineError: { visible: false, onRetry: () => undefined },
      options: [],
      onSelectChoice: () => undefined,
      onCustomChoice: () => undefined,
      result: { currentRound: 0, roundsPerWeek: 3, isPrefetching: false, onContinue: () => undefined },
      weeklySummary: { text: "", onContinue: () => undefined },
    };
    const first = render(createElement(PlayPhaseContent, props));
    expect(first.getByText("content").getAttribute("data-renders")).toBe("1");
    first.rerender(createElement(PlayPhaseContent, props));
    expect(first.getByText("content").getAttribute("data-renders")).toBe("1");
  });
});
