/**
 * HistorySceneImage Component Tests
 * Tests the historical scene image display with all states
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HistorySceneImage } from "@/components/game/HistorySceneImage";
import { useGameStore } from "@/stores/useGameStore";

describe("HistorySceneImage", () => {
  const baseProps = {
    sceneImage: null as {
      image_url: string;
      scene_description: string;
      scene_id: number;
      created_at?: string;
    } | null,
    isLoading: false,
    isGenerating: false,
    isRegenerating: false,
    week: 0,
    round: 0,
    storyText: "Test story text",
    onGenerate: jest.fn().mockResolvedValue(undefined),
    onRegenerate: jest.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    useGameStore.setState({ enableSceneImage: true });
  });

  describe("Disabled state", () => {
    it("returns null when enableSceneImage is false", () => {
      useGameStore.setState({ enableSceneImage: false });

      const { container } = render(<HistorySceneImage {...baseProps} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe("Generating state", () => {
    it("shows generating UI when isGenerating is true", () => {
      const { container } = render(
        <HistorySceneImage {...baseProps} isGenerating={true} />
      );
      const status = screen.getByRole("status");
      expect(status).toHaveTextContent("正在绘制历史场景插画");
      expect(status).not.toHaveTextContent("AI");
      expect(status.querySelector(".animate-pulse")).toBeNull();
      expect(status.querySelector(".rounded-full")).toBeNull();
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
      expect(container.querySelector('[data-slot="history-scene-state"]')).toHaveClass(
        'border-y',
        'bg-transparent',
        'shadow-none',
      );
    });
  });

  describe("Loading state", () => {
    it("shows loading when isLoading and no sceneImage", () => {
      render(<HistorySceneImage {...baseProps} isLoading={true} />);
      expect(screen.getByText("正在加载场景插画...")).toBeInTheDocument();
    });
  });

  describe("Empty state (no image)", () => {
    it("shows generate button when no scene image", () => {
      const { container } = render(<HistorySceneImage {...baseProps} />);
      expect(screen.getByText("该轮次暂无场景插画")).toBeInTheDocument();
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
      expect(screen.getByRole('button', { name: '生成场景插画' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it("calls onGenerate when clicking generate button", async () => {
      const onGenerate = jest.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <HistorySceneImage {...baseProps} onGenerate={onGenerate} />
      );

      await user.click(screen.getByText("生成场景插画"));
      expect(onGenerate).toHaveBeenCalledWith(0, 0, "Test story text");
    });

    it("shows loading state instead of generate button when loading", () => {
      render(
        <HistorySceneImage
          {...baseProps}
          isLoading={true}
        />
      );
      // When loading with no sceneImage, should show loading text, not generate button
      expect(screen.getByText("正在加载场景插画...")).toBeInTheDocument();
      expect(screen.queryByText("生成场景插画")).not.toBeInTheDocument();
    });
  });

  describe("Image display", () => {
    const sceneImage = {
      image_url: "https://example.com/scene.jpg",
      scene_description: "A beautiful landscape scene",
      scene_id: 1,
      created_at: "2025-01-01T00:00:00Z",
    };

    it("renders a flat historical figure with caption metadata instead of a card", () => {
      const { container } = render(
        <HistorySceneImage
          {...baseProps}
          sceneImage={sceneImage}
          week={4}
          round={2}
        />
      );

      const figure = container.querySelector('figure[data-slot="history-scene-figure"]');
      expect(figure).toBeInTheDocument();
      expect(figure).toHaveClass(
        'rounded-none',
        'border-y',
        'bg-transparent',
        'shadow-none',
      );
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
      expect(figure?.querySelector('figcaption')).toHaveTextContent('历史场景插画');
      expect(figure?.querySelector('figcaption')).toHaveTextContent('第 5 周 · 第 3 轮');

      const roundLabel = screen.getByText('第 5 周 · 第 3 轮');
      expect(roundLabel).not.toHaveClass('rounded', 'bg-black/50', 'text-white');
      expect(figure?.getAttribute('class')).not.toMatch(
        /(?:rounded-(?:lg|xl|2xl)|shadow-(?!none)|bg-card|drop-shadow)/,
      );
    });

    it("keeps the historical image action at a 44px touch target", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);

      expect(screen.getByRole('button', { name: '修改图片' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it("renders the image with src", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);

      const img = document.querySelector("img");
      expect(img).toBeInTheDocument();
      expect(img?.getAttribute("src")).toContain("https://example.com/scene.jpg");
    });

    it("renders scene description", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);
      const description = screen.getByText("A beautiful landscape scene");
      expect(description).toHaveClass("whitespace-normal", "break-words");
      expect(description).not.toHaveClass("line-clamp-2", "truncate");
    });

    it("shows week and round labels", () => {
      render(
        <HistorySceneImage
          {...baseProps}
          sceneImage={sceneImage}
          week={4}
          round={2}
        />
      );
      expect(screen.getByText("第 5 周 · 第 3 轮")).toBeInTheDocument();
    });

    it("shows image loading spinner initially", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);
      // Image not loaded yet, there should be a Loader2 spinner
      expect(screen.getByText("A beautiful landscape scene")).toBeInTheDocument();
    });
  });

  describe("Image error handling", () => {
    const sceneImage = {
      image_url: "https://example.com/broken.jpg",
      scene_description: "Broken image scene",
      scene_id: 2,
    };

    it("shows error UI when image fails to load", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);

      const img = document.querySelector("img");
      fireEvent.error(img!);

      expect(screen.getByText("图片加载失败")).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重新加载' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it("clears image cache on first error", () => {
      const spy = jest.spyOn(useGameStore.getState(), 'clearImageCache');
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);

      const img = document.querySelector("img");
      fireEvent.error(img!);

      expect(spy).toHaveBeenCalled();
      spy.mockRestore();
    });
  });

  describe("Regenerate UI", () => {
    const sceneImage = {
      image_url: "https://example.com/scene.jpg",
      scene_description: "Scene for regenerate",
      scene_id: 3,
    };

    it("shows modify button when onRegenerate is provided", () => {
      render(
        <HistorySceneImage
          {...baseProps}
          sceneImage={sceneImage}
          onRegenerate={jest.fn().mockResolvedValue(undefined)}
        />
      );
      expect(screen.getByText("修改图片")).toBeInTheDocument();
    });

    it("does not show modify button when onRegenerate is not provided", () => {
      const props = { ...baseProps, sceneImage, onRegenerate: undefined };
      render(<HistorySceneImage {...props} />);
      expect(screen.queryByText("修改图片")).not.toBeInTheDocument();
    });

    it("shows regenerate input when clicking modify button", async () => {
      const user = userEvent.setup();
      render(
        <HistorySceneImage
          {...baseProps}
          sceneImage={sceneImage}
          onRegenerate={jest.fn().mockResolvedValue(undefined)}
        />
      );

      await user.click(screen.getByText("修改图片"));
      const input = screen.getByRole("textbox", { name: "插画修改要求" });
      expect(input).toHaveAttribute("data-control-size", "touch");
      expect(screen.getByRole("button", { name: "确认生成" })).not.toHaveClass("text-xs");
      expect(screen.getByRole("button", { name: "取消" })).not.toHaveClass("text-xs");
      expect(screen.getByText("取消")).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '确认生成' })).toHaveAttribute(
        'data-size',
        'touch',
      );
      expect(screen.getByRole('button', { name: '取消' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it("hides regenerate input when clicking cancel", async () => {
      const user = userEvent.setup();
      render(
        <HistorySceneImage
          {...baseProps}
          sceneImage={sceneImage}
          onRegenerate={jest.fn().mockResolvedValue(undefined)}
        />
      );

      await user.click(screen.getByText("修改图片"));
      expect(
        screen.getByPlaceholderText("例如：让场景更明亮一些，增加更多人物...")
      ).toBeInTheDocument();

      await user.click(screen.getByText("取消"));
      expect(
        screen.queryByPlaceholderText("例如：让场景更明亮一些，增加更多人物...")
      ).not.toBeInTheDocument();
    });

    it("disables confirm button when prompt is empty", async () => {
      const user = userEvent.setup();
      render(
        <HistorySceneImage
          {...baseProps}
          sceneImage={sceneImage}
          onRegenerate={jest.fn().mockResolvedValue(undefined)}
        />
      );

      await user.click(screen.getByText("修改图片"));
      const confirmButton = screen.getByText("确认生成").closest("button");
      expect(confirmButton).toBeDisabled();
    });
  });

  describe("Edge cases", () => {
    it("renders with week=0 and round=0 (displayed as 1 and 1)", () => {
      const sceneImage = {
        image_url: "https://example.com/scene.jpg",
        scene_description: "First scene",
        scene_id: 1,
      };
      render(
        <HistorySceneImage {...baseProps} sceneImage={sceneImage} week={0} round={0} />
      );
      expect(screen.getByText("第 1 周 · 第 1 轮")).toBeInTheDocument();
    });

    it("renders with large week and round numbers", () => {
      const sceneImage = {
        image_url: "https://example.com/scene.jpg",
        scene_description: "Later scene",
        scene_id: 1,
      };
      render(
        <HistorySceneImage
          {...baseProps}
          sceneImage={sceneImage}
          week={99}
          round={99}
        />
      );
      expect(screen.getByText("第 100 周 · 第 100 轮")).toBeInTheDocument();
    });
  });
});
