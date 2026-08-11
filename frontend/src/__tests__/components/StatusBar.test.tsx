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
    week: 9,
    total_weeks: 52,
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

    it("displays the human-readable current round from player state", () => {
      render(
        <StatusBar
          playerState={{ ...mockPlayerState, current_round: 0, rounds_per_week: 3 }}
          progress={mockProgress}
        />
      );

      expect(screen.getByText("第1轮/3")).toBeInTheDocument();
    });

    it("hides runtime resource metrics", () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      expect(screen.queryByText(/精力/)).not.toBeInTheDocument();
      expect(screen.queryByText(/情绪/)).not.toBeInTheDocument();
      expect(screen.queryByText(/学识/)).not.toBeInTheDocument();
      expect(screen.queryByText(/财富/)).not.toBeInTheDocument();
      expect(screen.queryByText(/5,000/)).not.toBeInTheDocument();
    });

    it("offers a flat narrative treatment without badge pills", () => {
      const { container } = render(
        <StatusBar
          playerState={{ ...mockPlayerState, current_round: 0, rounds_per_week: 3 }}
          progress={mockProgress}
          appearance="narrative"
        />
      );

      expect(screen.getByText("25岁 · 第10周")).toBeInTheDocument();
      expect(screen.getByText("周一 · 第1轮/3")).toBeInTheDocument();
      expect(container.querySelector('[data-slot="badge"]')).not.toBeInTheDocument();
      expect(screen.getByTestId("status-bar")).toHaveAttribute(
        "data-appearance",
        "narrative",
      );
    });
  });

  describe("full mode", () => {
    it("displays age and week in header", () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={null} compact={false} />
      );

      expect(screen.getByText("25岁 第10周")).toBeInTheDocument();
    });

    it("displays a current-round progress bar when available", () => {
      render(
        <StatusBar
          playerState={{ ...mockPlayerState, current_round: 1, rounds_per_week: 3 }}
          progress={mockProgress}
          compact={false}
        />
      );

      expect(screen.getByText("进度 第2轮/3")).toBeInTheDocument();
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

    it("labels the first round instead of hiding or showing round zero", () => {
      render(
        <StatusBar
          playerState={{ ...mockPlayerState, current_round: 0, rounds_per_week: 3 }}
          progress={mockProgress}
        />
      );

      expect(screen.getByText("第1轮/3")).toBeInTheDocument();
      expect(screen.queryByText(/第0轮/)).not.toBeInTheDocument();
    });

    it("keeps the completed week and round visible while weekly summary is open", () => {
      render(
        <StatusBar
          playerState={{
            ...mockPlayerState,
            week: 1,
            current_round: 0,
            rounds_per_week: 3,
            resume_view: {
              phase: "summary",
              completed_week: 0,
              completed_round: 2,
            },
          }}
          progress={{ week: 1, total_weeks: 52 }}
        />
      );

      expect(screen.getByText("25岁 第1周")).toBeInTheDocument();
      expect(screen.getByText("第3轮/3")).toBeInTheDocument();
      expect(screen.queryByText("25岁 第2周")).not.toBeInTheDocument();
    });
  });
});
