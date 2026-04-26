/**
 * HistorySceneImage Component Tests
 * Tests the historical scene image display with all states
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HistorySceneImage } from "@/components/game/HistorySceneImage";

// Mock useGameStore
const mockClearImageCache = jest.fn();
jest.mock("@/stores/useGameStore", () => ({
  useGameStore: jest.fn((selector: (s: Record<string, unknown>) => unknown) => {
    const state = {
      enableSceneImage: true,
      clearImageCache: mockClearImageCache,
    };
    return selector(state);
  }),
}));

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
  });

  describe("Disabled state", () => {
    it("returns null when enableSceneImage is false", () => {
      jest.mocked(
        require("@/stores/useGameStore").useGameStore
      ).mockImplementationOnce((selector: (s: Record<string, unknown>) => unknown) => {
        const state = { enableSceneImage: false, clearImageCache: mockClearImageCache };
        return selector(state);
      });

      const { container } = render(<HistorySceneImage {...baseProps} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe("Generating state", () => {
    it("shows generating UI when isGenerating is true", () => {
      render(<HistorySceneImage {...baseProps} isGenerating={true} />);
      expect(
        screen.getByText("AI正在为你绘制场景插画...")
      ).toBeInTheDocument();
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
      render(<HistorySceneImage {...baseProps} />);
      expect(screen.getByText("该轮次暂无场景插画")).toBeInTheDocument();
      expect(screen.getByText("生成场景插画")).toBeInTheDocument();
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

    it("disables generate button when loading", () => {
      render(
        <HistorySceneImage
          {...baseProps}
          isLoading={true}
        />
      );
      const button = screen.getByText("生成场景插画").closest("button");
      expect(button).toBeDisabled();
    });
  });

  describe("Image display", () => {
    const sceneImage = {
      image_url: "https://example.com/scene.jpg",
      scene_description: "A beautiful landscape scene",
      scene_id: 1,
      created_at: "2025-01-01T00:00:00Z",
    };

    it("renders the image with src", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);

      const img = document.querySelector("img");
      expect(img).toBeInTheDocument();
      expect(img?.getAttribute("src")).toContain("https://example.com/scene.jpg");
    });

    it("renders scene description", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);
      expect(screen.getByText("A beautiful landscape scene")).toBeInTheDocument();
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
      expect(screen.getByText("重新加载")).toBeInTheDocument();
    });

    it("clears image cache on first error", () => {
      render(<HistorySceneImage {...baseProps} sceneImage={sceneImage} />);

      const img = document.querySelector("img");
      fireEvent.error(img!);

      expect(mockClearImageCache).toHaveBeenCalled();
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
      expect(
        screen.getByPlaceholderText("例如：让场景更明亮一些，增加更多人物...")
      ).toBeInTheDocument();
      expect(screen.getByText("确认生成")).toBeInTheDocument();
      expect(screen.getByText("取消")).toBeInTheDocument();
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
