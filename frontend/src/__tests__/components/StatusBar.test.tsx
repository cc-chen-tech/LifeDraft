/**
 * components/game/StatusBar.tsx Tests
 * Tests for status bar component resource-metric visibility contract
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { StatusBar } from "@/components/game/StatusBar";

describe("StatusBar", () => {
  const mockPlayerState = {
    age: 25,
    week: 9, // ★ week 从0开始，显示时会 +1，所以显示"第10周"
    energy: 80,
    mood: 65,
    knowledge: 70,
    wealth: 5000,
  };

  const mockProgress = {
    current_round: 5,
    total_rounds: 10,
  };

  describe("when playerState is null", () => {
    it("returns null", () => {
      const { container } = render(
        <StatusBar playerState={null} progress={null} />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe("compact mode (default)", () => {
    it("displays age and week", () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      expect(screen.getByText("25岁 第10周")).toBeInTheDocument();
    });

    it("displays progress when available", () => {
      render(<StatusBar playerState={mockPlayerState} progress={mockProgress} />);

      expect(screen.getByText("5/10")).toBeInTheDocument();
    });

    it("hides runtime resource metrics", () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      expect(screen.queryByText(/精力/)).not.toBeInTheDocument();
      expect(screen.queryByText(/情绪/)).not.toBeInTheDocument();
      expect(screen.queryByText(/学识/)).not.toBeInTheDocument();
      expect(screen.queryByText(/财富/)).not.toBeInTheDocument();
      expect(screen.queryByText(/5,000/)).not.toBeInTheDocument();
    });
  });

  describe("full mode", () => {
    it("displays age and week in header", () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={null} compact={false} />
      );

      expect(screen.getByText("25岁 第10周")).toBeInTheDocument();
    });

    it("displays progress bar when available", () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={mockProgress} compact={false} />
      );

      expect(screen.getByText("进度 5/10")).toBeInTheDocument();
    });

    it("hides all resource bars", () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={null} compact={false} />
      );

      expect(screen.queryByText("精力")).not.toBeInTheDocument();
      expect(screen.queryByText("情绪")).not.toBeInTheDocument();
      expect(screen.queryByText("学识")).not.toBeInTheDocument();
      expect(screen.queryByText("财富")).not.toBeInTheDocument();
    });
  });

  describe("edge cases", () => {
    it("handles missing resources gracefully", () => {
      render(
        <StatusBar playerState={{ age: 25, week: 0 }} progress={null} /> // ★ week=0 显示 "第1周"
      );

      expect(screen.getByText("25岁 第1周")).toBeInTheDocument();
      // Should not crash when resources are missing
    });

    it("handles zero progress", () => {
      render(
        <StatusBar
          playerState={mockPlayerState}
          progress={{ current_round: 0, total_rounds: 10 }}
        />
      );

      // Progress should not be shown when current_round is 0
      expect(screen.queryByText("0/10")).not.toBeInTheDocument();
    });
  });
});
