/**
 * AchievementBadge Component Tests
 * Tests rendering with different rarities, animation, and edge cases
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { AchievementBadge } from "@/components/game/AchievementBadge";

describe("AchievementBadge", () => {
  const baseProps = {
    id: "test-achievement",
    name: "First Steps",
    description: "Completed your first week",
    rarity: "common" as const,
  };

  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe("Basic rendering", () => {
    it("renders the achievement name", () => {
      render(<AchievementBadge {...baseProps} />);
      expect(screen.getByText("First Steps")).toBeInTheDocument();
    });

    it("renders the achievement description", () => {
      render(<AchievementBadge {...baseProps} />);
      expect(screen.getByText("Completed your first week")).toBeInTheDocument();
    });

    it("renders the rarity label", () => {
      render(<AchievementBadge {...baseProps} />);
      expect(screen.getByText("普通")).toBeInTheDocument();
    });

    it("has the test id", () => {
      render(<AchievementBadge {...baseProps} />);
      expect(screen.getByTestId("achievement-badge")).toBeInTheDocument();
    });
  });

  describe("Rarity variants", () => {
    it("renders common variant", () => {
      render(<AchievementBadge {...baseProps} rarity="common" />);
      expect(screen.getByText("普通")).toBeInTheDocument();
      const badge = screen.getByTestId("achievement-badge");
      expect(badge).toHaveAttribute("data-rarity", "common");
      expect(badge.className).toContain("border-[var(--border-default)]");
    });

    it("renders rare variant", () => {
      render(
        <AchievementBadge
          {...baseProps}
          rarity="rare"
          name="Rare Achievement"
        />
      );
      expect(screen.getByText("稀有")).toBeInTheDocument();
      const badge = screen.getByTestId("achievement-badge");
      expect(badge).toHaveAttribute("data-rarity", "rare");
      expect(badge.className).toContain("border-[var(--border-default)]");
    });

    it("renders epic variant", () => {
      render(
        <AchievementBadge
          {...baseProps}
          rarity="epic"
          name="Epic Achievement"
        />
      );
      expect(screen.getByText("史诗")).toBeInTheDocument();
      const badge = screen.getByTestId("achievement-badge");
      expect(badge).toHaveAttribute("data-rarity", "epic");
      expect(badge.className).toContain("border-[var(--border-default)]");
    });

    it("renders legendary variant", () => {
      render(
        <AchievementBadge
          {...baseProps}
          rarity="legendary"
          name="Legendary Achievement"
        />
      );
      expect(screen.getByText("传说")).toBeInTheDocument();
      const badge = screen.getByTestId("achievement-badge");
      expect(badge).toHaveAttribute("data-rarity", "legendary");
      expect(badge.className).toContain("border-[var(--border-default)]");
    });

    it.each(["common", "rare", "epic", "legendary"] as const)(
      "keeps the %s badge on one neutral ink row without glow",
      (rarity) => {
        render(<AchievementBadge {...baseProps} rarity={rarity} />);
        const badge = screen.getByTestId("achievement-badge");

        expect(badge.className).not.toMatch(/bg-(?:slate|sky|violet|amber)-/);
        expect(badge.className).not.toMatch(/shadow(?:-|\b)/);
      },
    );
  });

  describe("Static presentation", () => {
    it("is immediately visible without its own timer, opacity, transform, or transition", () => {
      render(<AchievementBadge {...baseProps} />);
      const badge = screen.getByTestId("achievement-badge");

      expect(jest.getTimerCount()).toBe(0);
      expect(badge.className).not.toMatch(/(?:opacity|translate|scale|transition|duration)-/);
    });
  });

  describe("Unlocked at week", () => {
    it("shows unlocked week when provided", () => {
      render(<AchievementBadge {...baseProps} unlockedAtWeek={15} />);
      expect(screen.getByText("第 15 周解锁")).toBeInTheDocument();
    });

    it("does not show unlocked week when undefined", () => {
      render(<AchievementBadge {...baseProps} unlockedAtWeek={undefined} />);
      expect(screen.queryByText(/周解锁/)).not.toBeInTheDocument();
    });
  });

  describe("Edge cases", () => {
    it("renders with long name and description", () => {
      render(
        <AchievementBadge
          id="long"
          name="Master of All Trades and Beyond the Stars Achievement Title"
          description="This is a very long description that should still render properly without breaking the layout or causing any overflow issues in the component"
          rarity="legendary"
        />
      );
      expect(screen.getByTestId("achievement-badge")).toBeInTheDocument();
    });

    it("renders with empty description", () => {
      render(
        <AchievementBadge
          id="no-desc"
          name="Silent Achievement"
          description=""
          rarity="common"
        />
      );
      expect(screen.getByTestId("achievement-badge")).toBeInTheDocument();
      expect(screen.getByText("Silent Achievement")).toBeInTheDocument();
    });
  });
});
