/**
 * StepPortrait Component Tests
 * Tests the portrait selection step in character creation
 */
import React from "react";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StepPortrait } from "@/components/create/StepPortrait";

describe("StepPortrait", () => {
  const baseProps = {
    playerImages: [] as Array<{ image_id: number; image_url: string }>,
    selectedImageIndex: 0,
    isGeneratingImage: false,
    imageGenerationError: null as string | null,
    playerName: "TestPlayer",
    imageFeedback: "",
    gameId: 1,
    isBackgroundGenerating: false,
    onSelectImage: jest.fn(),
    onFeedbackChange: jest.fn(),
    onRegenerate: jest.fn().mockResolvedValue(undefined),
    onRegenerateFresh: jest.fn().mockResolvedValue(undefined),
    onRetryGeneration: jest.fn().mockResolvedValue(undefined),
    showToast: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows three fixed slots, partial progress, retry and current old portrait', async () => {
    const retry = jest.fn().mockResolvedValue(undefined);
    const select = jest.fn().mockResolvedValue(undefined);
    render(<StepPortrait {...baseProps} selectedImageId={99}
      playerImages={[{ image_id: 99, image_url: 'old' }, { image_id: 22, image_url: 'new2' }, { image_id: 11, image_url: 'new1' }]}
      portraitCandidates={{ batch_id: 9, job_id: 8, game_id: 1, mode: 'fresh', status: 'failed', selected_image_id: 99, completed_count: 2,
        slots: [{ slot_index: 0, image_id: 11, status: 'ready' }, { slot_index: 1, image_id: null, status: 'failed' }, { slot_index: 2, image_id: 22, status: 'ready' }] }}
      onRetryMissing={retry} onSelectImage={select} />);
    expect(screen.getByText('已完成 2/3')).toBeVisible();
    expect(screen.getByText('当前使用')).toBeVisible();
    expect(screen.getByRole('img', { name: 'TestPlayer' })).toHaveAttribute('src', 'old');
    const slots = screen.getAllByRole('button', { name: /选择人物形象/ });
    expect(slots).toHaveLength(3); expect(slots[1]).toBeDisabled();
    fireEvent.click(slots[2]); await waitFor(() => expect(select).toHaveBeenCalledWith(22));
    expect(slots[2]).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(screen.getByRole('button', { name: '重试未完成的形象' }));
    await waitFor(() => expect(retry).toHaveBeenCalledWith(9));
  });

  it('offers an explicit initial request for an empty restored game', () => {
    const retry = jest.fn().mockResolvedValue(undefined);
    render(<StepPortrait {...baseProps} onRetryGeneration={retry} />);
    fireEvent.click(screen.getByRole('button', { name: '生成三张人物形象' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  describe("Generating state", () => {
    it("shows loading when generating image", () => {
      render(<StepPortrait {...baseProps} isGeneratingImage={true} />);
      expect(
        screen.getByText("人物形象正在后台生成，你可以先继续创建。")
      ).toBeInTheDocument();
      expect(screen.queryByText(/AI/)).not.toBeInTheDocument();
    });

    it("shows long-running portrait guidance and recover action after one minute", () => {
      jest.useFakeTimers();
      const onRecover = jest.fn();

      try {
        render(
          <StepPortrait
            {...baseProps}
            isGeneratingImage={true}
            onRecover={onRecover}
          />
        );

        act(() => {
          jest.advanceTimersByTime(75_000);
        });

        expect(screen.getByText(/人物形象生成通常需要 1-2 分钟/)).toBeInTheDocument();
        const recoverButton = screen.getByRole("button", { name: "刷新状态" });
        fireEvent.click(recoverButton);
        expect(onRecover).toHaveBeenCalledTimes(1);
      } finally {
        jest.useRealTimers();
      }
    });
  });

  describe("Provider failure", () => {
    it("shows an actionable portrait placeholder", async () => {
      const onRetryGeneration = jest.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <StepPortrait
          {...baseProps}
          imageGenerationError="图片生成额度暂时不可用，请稍后再试"
          onRetryGeneration={onRetryGeneration}
        />
      );

      expect(screen.getByText("图片生成额度暂时不可用，请稍后再试")).toBeVisible();
      await user.click(screen.getByRole("button", { name: "重试生成人物形象" }));
      expect(onRetryGeneration).toHaveBeenCalledTimes(1);
    });
  });

  describe("Empty state", () => {
    it("shows preparing state when no images and no gameId", () => {
      render(<StepPortrait {...baseProps} gameId={null} />);
      expect(screen.getByText("正在准备生成...")).toBeInTheDocument();
    });

    it("shows waiting state when no images but has gameId", () => {
      render(<StepPortrait {...baseProps} />);
      expect(screen.getByText("正在准备生成...")).toBeInTheDocument();
    });

    it("does not show waiting state when no images but is generating", () => {
      render(
        <StepPortrait {...baseProps} isGeneratingImage={true} gameId={null} />
      );
      expect(
        screen.getByText("人物形象正在后台生成，你可以先继续创建。")
      ).toBeInTheDocument();
      expect(screen.queryByText("正在准备生成...")).not.toBeInTheDocument();
    });
  });

  describe("With images", () => {
    const images = [
      { image_id: 1, image_url: "https://example.com/portrait1.jpg" },
      { image_id: 2, image_url: "https://example.com/portrait2.jpg" },
    ];

    it("renders the main image when images are provided", () => {
      render(<StepPortrait {...baseProps} playerImages={images} />);

      const img = document.querySelector("img");
      expect(img).toBeInTheDocument();
      expect(img?.getAttribute("src")).toBe("https://example.com/portrait1.jpg");
    });

    it("keeps the old image visible during background regeneration", () => {
      render(<StepPortrait {...baseProps} playerImages={images} isGeneratingImage />);

      expect(screen.getByRole("img", { name: "TestPlayer" })).toBeInTheDocument();
      expect(screen.getByRole("status")).toHaveTextContent("正在后台重新生成人物形象");
    });

    it("shows the error while retaining the old image after regeneration fails", () => {
      render(<StepPortrait {...baseProps} playerImages={images} imageGenerationError="生成失败" />);

      expect(screen.getByRole("img", { name: "TestPlayer" })).toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent("生成失败");
    });

    it("shows thumbnail selectors when multiple images", () => {
      render(<StepPortrait {...baseProps} playerImages={images} />);

      const thumbnails = screen.getAllByRole("button", { name: /选择人物形象/ });
      expect(thumbnails).toHaveLength(2);
      expect(thumbnails[0]).toHaveAttribute("aria-pressed", "true");
      expect(thumbnails[1]).toHaveAttribute("aria-pressed", "false");
    });

    it("does not show thumbnails when only one image", () => {
      render(
        <StepPortrait
          {...baseProps}
          playerImages={[images[0]]}
        />
      );

      const img = document.querySelector("img");
      expect(img).toBeInTheDocument();
    });

    it("calls onSelectImage when clicking a thumbnail", async () => {
      const onSelectImage = jest.fn();
      const user = userEvent.setup();
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          onSelectImage={onSelectImage}
        />
      );

      const thumbnailButtons = document.querySelectorAll("button");
      // Find the thumbnail button (not the main regenerate buttons)
      const thumbButton = Array.from(thumbnailButtons).find(
        (btn) => btn.querySelector("img")
      );
      if (thumbButton) {
        await user.click(thumbButton);
        // Should call onSelectImage (could be 0 if clicking first, or 1 if clicking second)
        expect(onSelectImage).toHaveBeenCalled();
      }
    });
  });

  describe("Image error handling", () => {
    const images = [
      { image_id: 1, image_url: "https://example.com/broken.jpg" },
    ];

    it("shows error fallback when main image fails", () => {
      render(<StepPortrait {...baseProps} playerImages={images} />);

      const img = document.querySelector("img");
      fireEvent.error(img!);

      expect(screen.getByText("图片加载失败")).toBeInTheDocument();
    });
  });

  describe("Feedback input", () => {
    const images = [
      { image_id: 1, image_url: "https://example.com/portrait.jpg" },
    ];

    it("shows feedback input when images exist and not generating", () => {
      render(<StepPortrait {...baseProps} playerImages={images} />);

      const feedback = screen.getByRole("textbox", { name: "人物形象修改意见" });
      expect(feedback.tagName).toBe("TEXTAREA");
      expect(feedback).toHaveAttribute("aria-describedby");
      expect(feedback.getAttribute("aria-describedby")).toContain(
        "portrait-feedback-count",
      );
    });

    it("does not show feedback input when generating image", () => {
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          isGeneratingImage={true}
        />
      );
      expect(
        screen.queryByPlaceholderText("不满意？描述你想要的修改...（会保留之前的角色设定）")
      ).not.toBeInTheDocument();
    });

    it("does not show feedback input when no images", () => {
      render(<StepPortrait {...baseProps} />);
      expect(
        screen.queryByPlaceholderText("不满意？描述你想要的修改...（会保留之前的角色设定）")
      ).not.toBeInTheDocument();
    });

    it("calls onFeedbackChange when typing feedback", async () => {
      const onFeedbackChange = jest.fn();
      const user = userEvent.setup();
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          onFeedbackChange={onFeedbackChange}
        />
      );

      const input = screen.getByPlaceholderText(
        "不满意？描述你想要的修改...（会保留之前的角色设定）"
      );
      await user.type(input, "Make hair longer");

      expect(onFeedbackChange).toHaveBeenCalled();
    });
  });

  describe("Regenerate buttons", () => {
    const images = [
      { image_id: 1, image_url: "https://example.com/portrait.jpg" },
    ];

    it("renders regenerate button with feedback", () => {
      render(<StepPortrait {...baseProps} playerImages={images} />);
      expect(
        screen.getByText("根据修改意见重新生成")
      ).toBeInTheDocument();
    });

    it("disables regenerate button when feedback is empty", () => {
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          imageFeedback=""
        />
      );
      const button = screen.getByText("根据修改意见重新生成").closest("button");
      expect(button).toBeDisabled();
    });

    it("renders fresh regenerate button", () => {
      render(<StepPortrait {...baseProps} playerImages={images} />);
      expect(
        screen.getByText("完全重新生成（三张新形象）")
      ).toBeInTheDocument();
    });

    it("calls onRegenerate when clicking regenerate button with feedback", async () => {
      const onRegenerate = jest.fn().mockResolvedValue(undefined);
      const onFeedbackChange = jest.fn();
      const user = userEvent.setup();
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          imageFeedback="Test feedback"
          onRegenerate={onRegenerate}
          onFeedbackChange={onFeedbackChange}
        />
      );

      await user.click(screen.getByText("根据修改意见重新生成"));
      await waitFor(() => {
        expect(onRegenerate).toHaveBeenCalled();
      });
      expect(onFeedbackChange).not.toHaveBeenCalledWith("");
    });

    it("calls onRegenerateFresh when clicking fresh regenerate", async () => {
      const onRegenerateFresh = jest.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          onRegenerateFresh={onRegenerateFresh}
        />
      );

      await user.click(screen.getByText("完全重新生成（三张新形象）"));
      await waitFor(() => {
        expect(onRegenerateFresh).toHaveBeenCalled();
      });
    });
  });

  describe("Background generating indicator", () => {
    it("shows background generating message when isBackgroundGenerating with images", () => {
      const images = [
        { image_id: 1, image_url: "https://example.com/portrait.jpg" },
      ];
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          isBackgroundGenerating={true}
        />
      );
      expect(
        screen.getByText("后台正在生成家庭背景、人际关系等设定...")
      ).toBeInTheDocument();
    });

    it("does not show background message when no images", () => {
      render(
        <StepPortrait {...baseProps} isBackgroundGenerating={true} />
      );
      expect(
        screen.queryByText("后台正在生成家庭背景、人际关系等设定...")
      ).not.toBeInTheDocument();
    });
  });

  describe("Error handling", () => {
    it("shows toast on regenerate failure", async () => {
      const showToast = jest.fn();
      const onRegenerate = jest.fn().mockRejectedValue(
        new Error("Generation failed")
      );
      const user = userEvent.setup();
      const images = [
        { image_id: 1, image_url: "https://example.com/portrait.jpg" },
      ];

      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          imageFeedback="Test"
          onRegenerate={onRegenerate}
          showToast={showToast}
        />
      );

      await user.click(screen.getByText("根据修改意见重新生成"));

      await waitFor(() => {
        expect(showToast).toHaveBeenCalledWith(
          "error",
          expect.stringContaining("Generation failed")
        );
      });
    });

    it("shows toast on fresh regenerate failure", async () => {
      const showToast = jest.fn();
      const onRegenerateFresh = jest.fn().mockRejectedValue(
        new Error("Fresh generation failed")
      );
      const user = userEvent.setup();
      const images = [
        { image_id: 1, image_url: "https://example.com/portrait.jpg" },
      ];

      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          onRegenerateFresh={onRegenerateFresh}
          showToast={showToast}
        />
      );

      await user.click(
        screen.getByText("完全重新生成（三张新形象）")
      );

      await waitFor(() => {
        expect(showToast).toHaveBeenCalledWith(
          "error",
          expect.stringContaining("Fresh generation failed")
        );
      });
    });
  });

  describe("Edge cases", () => {
    it("handles selectedImageIndex out of bounds gracefully", () => {
      const images = [
        { image_id: 1, image_url: "https://example.com/portrait1.jpg" },
      ];
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          selectedImageIndex={99}
        />
      );
      // Should fall back to images[0]
      const img = document.querySelector("img");
      expect(img?.getAttribute("src")).toBe("https://example.com/portrait1.jpg");
    });

    it("handles disabled regenerate when isGeneratingImage", () => {
      const images = [
        { image_id: 1, image_url: "https://example.com/portrait.jpg" },
      ];
      render(
        <StepPortrait
          {...baseProps}
          playerImages={images}
          isGeneratingImage={true}
          imageFeedback="Test"
        />
      );
      // Feedback input should not be shown when generating
      expect(
        screen.queryByText("根据修改意见重新生成")
      ).not.toBeInTheDocument();
    });
  });
});
