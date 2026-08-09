/**
 * StepPlayerInfo Component Tests
 * Tests the player info input step in character creation
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StepPlayerInfo } from "@/components/create/StepPlayerInfo";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

describe("StepPlayerInfo", () => {
  const baseProps = {
    playerName: "",
    lifeVision: "",
    onPlayerNameChange: jest.fn(),
    onLifeVisionChange: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic rendering", () => {
    it("renders the player name input", () => {
      render(<StepPlayerInfo {...baseProps} />);
      expect(
        screen.getByPlaceholderText("输入你的角色名")
      ).toBeInTheDocument();
    });

    it("renders the life vision textarea", () => {
      render(<StepPlayerInfo {...baseProps} />);
      expect(
        screen.getByPlaceholderText("描述你希望的人生方向...")
      ).toBeInTheDocument();
    });

    it("renders labels", () => {
      render(<StepPlayerInfo {...baseProps} />);
      expect(screen.getByText("角色姓名")).toBeInTheDocument();
      expect(screen.getByText("人生愿景（可选）")).toBeInTheDocument();
    });
  });

  describe("Player name input", () => {
    it("counts Unicode characters without a UTF-16 native maxlength", () => {
      const emojiName = "😀".repeat(INPUT_LIMITS.name);
      const { rerender } = render(<StepPlayerInfo {...baseProps} playerName="林见微" />);
      expect(screen.getByPlaceholderText("输入你的角色名")).not.toHaveAttribute("maxlength");
      expect(screen.getByText(`还可输入 ${INPUT_LIMITS.name - 3} 字`)).toBeInTheDocument();

      rerender(<StepPlayerInfo {...baseProps} playerName={emojiName} />);
      expect(screen.getByText("还可输入 0 字")).toBeInTheDocument();
    });
    it("displays the provided player name", () => {
      render(<StepPlayerInfo {...baseProps} playerName="Alice" />);
      const input = screen.getByPlaceholderText("输入你的角色名");
      expect(input).toHaveValue("Alice");
    });

    it("calls onPlayerNameChange when typing", async () => {
      const onPlayerNameChange = jest.fn();
      const user = userEvent.setup();
      render(
        <StepPlayerInfo
          {...baseProps}
          onPlayerNameChange={onPlayerNameChange}
        />
      );

      const input = screen.getByPlaceholderText("输入你的角色名");
      await user.type(input, "Bob");

      // Should be called for each character
      expect(onPlayerNameChange).toHaveBeenCalledTimes(3);
    });

    it("has autoFocus on the name input", () => {
      render(<StepPlayerInfo {...baseProps} />);
      const input = screen.getByPlaceholderText("输入你的角色名");
      expect(input).toHaveFocus();
    });
  });

  describe("Life vision textarea", () => {
    it("uses the generated vision limit and reports injected overflow", () => {
      render(
        <StepPlayerInfo
          {...baseProps}
          lifeVision={"愿".repeat(INPUT_LIMITS.lifeVision + 1)}
        />,
      );
      expect(screen.getByPlaceholderText("描述你希望的人生方向...")).not.toHaveAttribute("maxlength");
      expect(screen.getByRole("alert")).toHaveTextContent("已超出 1 字");
    });
    it("displays the provided life vision", () => {
      render(
        <StepPlayerInfo
          {...baseProps}
          lifeVision="I want to be a hero"
        />
      );
      const textarea = screen.getByPlaceholderText(
        "描述你希望的人生方向..."
      );
      expect(textarea).toHaveValue("I want to be a hero");
    });

    it("calls onLifeVisionChange when typing", async () => {
      const onLifeVisionChange = jest.fn();
      const user = userEvent.setup();
      render(
        <StepPlayerInfo
          {...baseProps}
          onLifeVisionChange={onLifeVisionChange}
        />
      );

      const textarea = screen.getByPlaceholderText(
        "描述你希望的人生方向..."
      );
      await user.type(textarea, "Peaceful life");

      expect(onLifeVisionChange).toHaveBeenCalled();
    });
  });

  describe("Edge cases", () => {
    it("renders with empty strings", () => {
      render(<StepPlayerInfo {...baseProps} />);
      expect(
        screen.getByPlaceholderText("输入你的角色名")
      ).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("描述你希望的人生方向...")
      ).toBeInTheDocument();
    });

    it("renders with special characters in name", () => {
      render(
        <StepPlayerInfo {...baseProps} playerName="李@#$%^&*()" />
      );
      const input = screen.getByPlaceholderText("输入你的角色名");
      expect(input).toHaveValue("李@#$%^&*()");
    });

    it("renders with long vision text", () => {
      const longVision = "A".repeat(5000);
      render(
        <StepPlayerInfo {...baseProps} lifeVision={longVision} />
      );
      const textarea = screen.getByPlaceholderText(
        "描述你希望的人生方向..."
      );
      expect(textarea).toHaveValue(longVision);
    });

    it("renders with Chinese characters", () => {
      render(
        <StepPlayerInfo
          {...baseProps}
          playerName="张三"
          lifeVision="我想成为一个伟大的剑客，周游世界行侠仗义"
        />
      );
      expect(screen.getByDisplayValue("张三")).toBeInTheDocument();
    });
  });
});
