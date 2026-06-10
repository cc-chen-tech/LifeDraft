/**
 * SceneImage 阶段渲染测试
 *
 * 验证 result 阶段不会同时显示 eventSceneImage 和 resultSceneImage。
 * Bug：result 阶段两张图片堆叠在底部。
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { useSceneImageStore } from "@/stores/useSceneImageStore";
import { getSceneImageDisplayMode } from "@/components/game/sceneImageStagePolicy";

// 最小化渲染组件，复刻 play/page.tsx 中的图片渲染条件
function TestSceneImageSection({
  phase,
  isLoading = false,
}: {
  phase: "options" | "result" | "summary" | "story";
  isLoading?: boolean;
}) {
  const eventSceneImage = useSceneImageStore((s) => s.eventSceneImage);
  const resultSceneImage = useSceneImageStore((s) => s.resultSceneImage);

  return (
    <div>
      {phase === "options" && eventSceneImage && (
        <div data-testid="event-image">Event Scene</div>
      )}
      {(phase === "result" || phase === "summary") && resultSceneImage && (
        <div data-testid="result-image">Result Scene</div>
      )}
      {(phase === "result" || phase === "summary") && !resultSceneImage && isLoading && (
        <div data-testid="result-loading">Result Scene Loading</div>
      )}
      {(phase === "result" || phase === "summary") && !resultSceneImage && !isLoading && eventSceneImage && (
        <div data-testid="event-image-fallback">Event Scene (Fallback)</div>
      )}
    </div>
  );
}

describe("SceneImage stage rendering", () => {
  beforeEach(() => {
    useSceneImageStore.setState({
      eventSceneImage: null,
      resultSceneImage: null,
    });
  });

  it("options 阶段只显示 eventSceneImage", () => {
    useSceneImageStore.setState({
      eventSceneImage: {
        scene_id: 1,
        image_url: "http://example.com/event.png",
        stage: "event",
        round_number: 1,
      } as any,
    });

    render(<TestSceneImageSection phase="options" />);
    expect(screen.getByTestId("event-image")).toBeInTheDocument();
    expect(screen.queryByTestId("result-image")).not.toBeInTheDocument();
  });

  it("result 阶段同时存在 event/result 时只显示 resultSceneImage", () => {
    useSceneImageStore.setState({
      eventSceneImage: {
        scene_id: 1,
        image_url: "http://example.com/event.png",
        stage: "event",
        round_number: 1,
      } as any,
      resultSceneImage: {
        scene_id: 2,
        image_url: "http://example.com/result.png",
        stage: "result",
        round_number: 1,
      } as any,
    });

    render(<TestSceneImageSection phase="result" />);
    expect(screen.getByTestId("result-image")).toBeInTheDocument();
    expect(screen.queryByTestId("event-image")).not.toBeInTheDocument();
    expect(screen.queryByTestId("event-image-fallback")).not.toBeInTheDocument();
  });

  it("result 阶段缺少 resultSceneImage 时回退显示 eventSceneImage", () => {
    useSceneImageStore.setState({
      eventSceneImage: {
        scene_id: 1,
        image_url: "http://example.com/event.png",
        stage: "event",
        round_number: 1,
      } as any,
      resultSceneImage: null,
    });

    render(<TestSceneImageSection phase="result" />);
    expect(screen.getByTestId("event-image-fallback")).toBeInTheDocument();
    expect(screen.queryByTestId("result-image")).not.toBeInTheDocument();
  });

  it("result 阶段正在加载结果插画时不回退显示旧事件插画", () => {
    useSceneImageStore.setState({
      eventSceneImage: {
        scene_id: 1,
        image_url: "http://example.com/event.png",
        stage: "event",
        round_number: 1,
      } as any,
      resultSceneImage: null,
    });

    render(<TestSceneImageSection phase="result" isLoading />);
    expect(screen.getByTestId("result-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("event-image-fallback")).not.toBeInTheDocument();
    expect(screen.queryByTestId("event-image")).not.toBeInTheDocument();
  });

  it("result 阶段结果插画加载中时显示加载态而不是旧事件插画策略", () => {
    expect(
      getSceneImageDisplayMode({
        phase: "result",
        hasEventSceneImage: true,
        hasResultSceneImage: false,
        hasCurrentRoundSceneImage: false,
        isLoadingRoundSceneImage: true,
      })
    ).toBe("result-loading");
  });

  it("story 阶段不显示任何场景图片", () => {
    useSceneImageStore.setState({
      eventSceneImage: {
        scene_id: 1,
        image_url: "http://example.com/event.png",
        stage: "event",
        round_number: 1,
      } as any,
      resultSceneImage: {
        scene_id: 2,
        image_url: "http://example.com/result.png",
        stage: "result",
        round_number: 1,
      } as any,
    });

    render(<TestSceneImageSection phase="story" />);
    expect(screen.queryByTestId("event-image")).not.toBeInTheDocument();
    expect(screen.queryByTestId("result-image")).not.toBeInTheDocument();
    expect(screen.queryByTestId("event-image-fallback")).not.toBeInTheDocument();
  });
});
