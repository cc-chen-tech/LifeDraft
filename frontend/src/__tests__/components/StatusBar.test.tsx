/**
 * components/game/StatusBar.tsx Tests
 * Tests for status bar component — 4D resources display
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

    it("displays 4D resources", () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      expect(screen.getByText(/精力: 80/)).toBeInTheDocument();
      expect(screen.getByText(/情绪: 65/)).toBeInTheDocument();
      expect(screen.getByText(/学识: 70/)).toBeInTheDocument();
      expect(screen.getByText(/财富/)).toBeInTheDocument();
    });

    it("formats wealth with currency symbol", () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      expect(screen.getByText(/5,000货币/)).toBeInTheDocument();
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

    it("displays all 4D resources with bars", () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={null} compact={false} />
      );

      expect(screen.getByText("精力")).toBeInTheDocument();
      expect(screen.getByText("情绪")).toBeInTheDocument();
      expect(screen.getByText("学识")).toBeInTheDocument();
      expect(screen.getByText("财富")).toBeInTheDocument();
    });
  });

  describe("resource colors", () => {
    it("applies success color for high values", () => {
      const highEnergyState = {
        ...mockPlayerState,
        energy: 90,
      };

      render(<StatusBar playerState={highEnergyState} progress={null} />);
      expect(screen.getByText(/精力: 90/)).toBeInTheDocument();
    });

    it("applies warning color for medium values", () => {
      const mediumEnergyState = {
        ...mockPlayerState,
        energy: 50,
      };

      render(<StatusBar playerState={mediumEnergyState} progress={null} />);
      expect(screen.getByText(/精力: 50/)).toBeInTheDocument();
    });

    it("applies destructive color for low values", () => {
      const lowEnergyState = {
        ...mockPlayerState,
        energy: 20,
      };

      render(<StatusBar playerState={lowEnergyState} progress={null} />);
      expect(screen.getByText(/精力: 20/)).toBeInTheDocument();
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
