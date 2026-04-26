/**
 * SettingFeedbackCard Component Tests
 * Tests the feedback card for character settings
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingFeedbackCard } from "@/components/create/SettingFeedbackCard";

// Mock SettingDisplay child component
jest.mock("@/components/game/SettingDisplay", () => ({
  SettingDisplay: ({ stepKey, data }: { stepKey: string; data: Record<string, unknown> }) => (
    <div data-testid="setting-display" data-step-key={stepKey}>
      {JSON.stringify(data)}
    </div>
  ),
}));

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
    it("renders the step label", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      expect(screen.getByText("家庭背景")).toBeInTheDocument();
    });

    it("renders the feedback button", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      expect(screen.getByText("给反馈重新生成")).toBeInTheDocument();
    });

    it("renders the SettingDisplay content", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      expect(screen.getByTestId("setting-display")).toBeInTheDocument();
      expect(screen.getByTestId("background-content")).toBeInTheDocument();
    });

    it("passes data to SettingDisplay", () => {
      render(<SettingFeedbackCard {...baseProps} />);
      const display = screen.getByTestId("setting-display");
      expect(display.textContent).toContain("商人世家");
    });
  });

  describe("Toggle feedback editing", () => {
    it("shows feedback input when clicking feedback button", async () => {
      const user = userEvent.setup();
      render(<SettingFeedbackCard {...baseProps} />);

      await user.click(screen.getByTestId("background-feedback-button"));

      expect(screen.getByTestId("background-feedback-input")).toBeInTheDocument();
      expect(screen.getByText("重新生成")).toBeInTheDocument();
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
