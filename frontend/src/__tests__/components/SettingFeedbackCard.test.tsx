/**
 * SettingFeedbackCard Component Tests
 * Tests the feedback card for character settings
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingFeedbackCard } from "@/components/create/SettingFeedbackCard";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

describe("SettingFeedbackCard", () => {
  const baseProps = {
    stepKey: "background",
    stepLabel: "家庭背景",
    data: { family: "商人世家", hometown: "长安" },
    onRegenerate: jest.fn().mockResolvedValue(undefined),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic rendering", () => {
    it("uses a quiet divided section instead of nesting cards", () => {
      const { container } = render(<SettingFeedbackCard {...baseProps} />);

      expect(container.querySelector('[data-slot="card"]')).not.toBeInTheDocument();
      expect(container.querySelector('[data-slot="setting-feedback"]')).toBeInTheDocument();
    });

    it("renders the step label", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      expect(screen.getByText("家庭背景")).toBeInTheDocument();
    });

    it("renders the feedback button", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      expect(screen.getByText("给反馈重新生成")).toBeInTheDocument();
    });

    it("exposes step-specific accessible names for feedback actions", async () => {
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} />);

      const feedbackButton = screen.getByRole("button", {
        name: "给家庭背景反馈重新生成",
      });
      expect(feedbackButton).toBeInTheDocument();

      await user.click(feedbackButton);

      expect(screen.getByRole("button", { name: "重新生成家庭背景" }))
        .toHaveAttribute("data-size", "touch");
    });

    it("renders the SettingDisplay content", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      expect(screen.getByTestId("background-content")).toBeInTheDocument();
      // Real SettingDisplay renders JSON for unknown stepKey
      expect(screen.getByText(/"family"/)).toBeInTheDocument();
    });

    it("passes data to SettingDisplay", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      // Real SettingDisplay renders JSON for "background" stepKey (fallback case)
      expect(screen.getByText(/"hometown"/)).toBeInTheDocument();
    });
  });

  describe("Toggle feedback editing", () => {
    it("shows feedback input when clicking feedback button", async () => {
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} />);

      await user.click(screen.getByTestId("background-feedback-button"));

      expect(screen.getByTestId("background-feedback-input")).toBeInTheDocument();
      expect(screen.getByTestId("background-feedback-input").tagName).toBe("TEXTAREA");
      expect(screen.getByRole("textbox", { name: "家庭背景修改意见" }))
        .toHaveAttribute("aria-describedby");
      expect(screen.getByText("重新生成")).toBeInTheDocument();
      expect(screen.getByTestId("background-feedback-input")).not.toHaveAttribute("maxlength");
      expect(screen.getByText(`还可输入 ${INPUT_LIMITS.feedback} 字`)).toBeInTheDocument();
    });

    it("changes feedback trigger button text to reflect editing state", async () => {
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} />);

      const button = screen.getByTestId("background-feedback-button");
      expect(button).toHaveTextContent("给反馈重新生成");

      await user.click(button);
      // After clicking, the button text changes to include "取消"
      expect(button).toHaveTextContent("取消");
    });

    it("hides feedback input when clicking cancel", async () => {
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} />);

      await user.click(screen.getByTestId("background-feedback-button"));
      expect(screen.getByTestId("background-feedback-input")).toBeInTheDocument();

      // Click the second cancel button (inside the editing area)
      const cancelButtons = screen.getAllByText("取消");
      await user.click(cancelButtons[cancelButtons.length - 1]);

      expect(
        screen.queryByTestId("background-feedback-input")
      ).not.toBeInTheDocument();
    });
  });

  describe("Regenerate flow", () => {
    it("calls onRegenerate with feedback text", async () => {
      const onRegenerate = jest.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <SettingFeedbackCard {...baseProps} onRegenerate={onRegenerate} />
      );

      await user.click(screen.getByTestId("background-feedback-button"));
      await user.type(
        screen.getByTestId("background-feedback-input"),
        "Make it more detailed"
      );
      await user.click(screen.getByText("重新生成"));

      await waitFor(() => {
        expect(onRegenerate).toHaveBeenCalledWith("Make it more detailed");
      });
    });

    it("disables regenerate button when feedback is empty", async () => {
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} />);

      await user.click(screen.getByTestId("background-feedback-button"));

      const regenerateButton = screen.getByText("重新生成").closest("button");
      expect(regenerateButton).toBeDisabled();
    });

    it("blocks injected overlimit feedback without clearing it", async () => {
      const onRegenerate = jest.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} onRegenerate={onRegenerate} />);
      await user.click(screen.getByTestId("background-feedback-button"));
      const input = screen.getByTestId("background-feedback-input");
      await user.type(input, "😀".repeat(INPUT_LIMITS.feedback + 1));
      expect(screen.getByText("已超出 1 字")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "重新生成家庭背景" })).toBeDisabled();
      expect(input).toHaveValue("😀".repeat(INPUT_LIMITS.feedback + 1));
      expect(onRegenerate).not.toHaveBeenCalled();
    });

    it("clears feedback after successful regeneration", async () => {
      const onRegenerate = jest.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <SettingFeedbackCard {...baseProps} onRegenerate={onRegenerate} />
      );

      await user.click(screen.getByTestId("background-feedback-button"));
      await user.type(
        screen.getByTestId("background-feedback-input"),
        "Test feedback"
      );
      await user.click(screen.getByText("重新生成"));

      await waitFor(() => {
        expect(onRegenerate).toHaveBeenCalled();
      });
    });

    it("keeps old content and shows an error when regeneration fails", async () => {
      const onRegenerate = jest
        .fn()
        .mockRejectedValue(new Error("人际关系生成结果不完整，已保留原设定"));
      const user = userEvent.setup();
      render(
        <SettingFeedbackCard
          stepKey="relationships"
          stepLabel="人际关系"
          data={{ relationships_description: "旧关系摘要" }}
          onRegenerate={onRegenerate}
        />
      );

      await user.click(screen.getByTestId("relationships-feedback-button"));
      await user.type(
        screen.getByTestId("relationships-feedback-input"),
        "保留原职业"
      );
      await user.click(screen.getByRole("button", { name: "重新生成人际关系" }));

      expect(
        await screen.findByText("人际关系生成结果不完整，已保留原设定")
      ).toBeVisible();
      expect(screen.getByText("旧关系摘要")).toBeVisible();
      expect(screen.getByTestId("relationships-feedback-input")).toHaveValue(
        "保留原职业"
      );
    });
  });

  describe("Different step keys", () => {
    it("renders with different step key and label", () => {
      render(
        <SettingFeedbackCard
          stepKey="personality"
          stepLabel="性格特征"
          data={{ trait: "brave" }}
          onRegenerate={jest.fn().mockResolvedValue(undefined)}
        />
      );
      expect(screen.getByText("性格特征")).toBeInTheDocument();
      expect(screen.getByTestId("personality-content")).toBeInTheDocument();
      expect(screen.getByTestId("personality-feedback-button")).toBeInTheDocument();
    });

    it("renders with relationships step key", () => {
      render(
        <SettingFeedbackCard
          stepKey="relationships"
          stepLabel="人际关系"
          data={{ connections: "many" }}
          onRegenerate={jest.fn().mockResolvedValue(undefined)}
        />
      );
      expect(screen.getByText("人际关系")).toBeInTheDocument();
      // Feedback input should not exist before clicking the feedback button
      expect(screen.queryByTestId("relationships-feedback-input")).not.toBeInTheDocument();
    });
  });

  describe("Edge cases", () => {
    it("renders with empty data object", () => {
      render(
        <SettingFeedbackCard
          {...baseProps}
          data={{}}
        />
      );
      expect(screen.getByTestId("background-content")).toBeInTheDocument();
    });

    it("renders with complex nested data", () => {
      render(
        <SettingFeedbackCard
          {...baseProps}
          data={{
            family: { father: "merchant", mother: "scholar" },
            siblings: ["brother", "sister"],
            wealth: 5000,
          }}
        />
      );
      expect(screen.getByTestId("background-content")).toBeInTheDocument();
    });

    it("handles rapid toggle of edit button", async () => {
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} />);

      const button = screen.getByTestId("background-feedback-button");
      await user.click(button);
      expect(screen.getByTestId("background-feedback-input")).toBeInTheDocument();

      await user.click(button);
      expect(
        screen.queryByTestId("background-feedback-input")
      ).not.toBeInTheDocument();
    });
  });
});
