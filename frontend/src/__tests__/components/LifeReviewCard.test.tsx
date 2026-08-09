/**
 * LifeReviewCard Component Tests
 * Tests the life review summary card with all sub-sections
 */
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { LifeReviewCard } from "@/components/game/LifeReviewCard";
import type { LifeReviewData } from "@/components/game/LifeReviewCard";

describe("LifeReviewCard", () => {
  const baseData: LifeReviewData = {
    personality_labels: ["勇敢", "智慧", "仁慈"],
    key_turning_points: [
      { week: 3, description: "Found a hidden treasure", impact_score: 0.85 },
      { week: 10, description: "Defeated the dragon", impact_score: 0.95 },
    ],
    resource_curves: {
      energy: [10, 20, 30, 40, 50],
      mood: [50, 45, 40, 35, 30],
      knowledge: [5, 15, 25, 35, 45],
      wealth: [0, 100, 200, 300, 400],
    },
    achievement_badge_wall: [
      { id: "a1", name: "First Steps", rarity: "common" as const, unlocked_at_week: 1 },
      { id: "a2", name: "Dragon Slayer", rarity: "legendary" as const, unlocked_at_week: 10 },
    ],
    relationship_network: {
      nodes: [
        { name: "Alice", affinity: 0.8 },
        { name: "Bob", affinity: 0.3 },
      ],
      edges: [
        { source: "Alice", target: "Bob", strength: 0.5 },
      ],
    },
    life_motto: "Live and let live",
    play_duration_minutes: 120,
    total_decisions: 42,
    favorite_choice_type: "冒险",
  };

  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe("Basic rendering", () => {
    it("renders the card with test id", () => {
      render(<LifeReviewCard data={baseData} />);
      expect(screen.getByTestId("life-review-card")).toBeInTheDocument();
    });

    it("renders review details without a nested generic card", () => {
      const { container } = render(<LifeReviewCard data={baseData} />);

      expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(0);
    });

    it("renders personality labels", () => {
      render(<LifeReviewCard data={baseData} />);
      expect(screen.getByText("人格标签")).toBeInTheDocument();
      expect(screen.getByText("勇敢")).toBeInTheDocument();
      expect(screen.getByText("智慧")).toBeInTheDocument();
      expect(screen.getByText("仁慈")).toBeInTheDocument();
    });

    it("renders the life motto", () => {
      render(<LifeReviewCard data={baseData} />);
      // Component uses &ldquo;/&rdquo; which render as smart quotes
      expect(screen.getByText(/“Live and let live”/)).toBeInTheDocument();
    });

    it("hides resource curves section", () => {
      render(<LifeReviewCard data={baseData} />);
      expect(screen.queryByText("资源曲线")).not.toBeInTheDocument();
      expect(screen.queryByText("energy")).not.toBeInTheDocument();
      expect(screen.queryByText("mood")).not.toBeInTheDocument();
      expect(screen.queryByText("knowledge")).not.toBeInTheDocument();
      expect(screen.queryByText("wealth")).not.toBeInTheDocument();
    });
  });

  describe("Stats section", () => {
    it("renders total decisions", () => {
      render(<LifeReviewCard data={baseData} />);
      expect(screen.getByText("42")).toBeInTheDocument();
      expect(screen.getByText("总决策数")).toBeInTheDocument();
    });

    it("renders play duration", () => {
      render(<LifeReviewCard data={baseData} />);
      expect(screen.getByText("120")).toBeInTheDocument();
      expect(screen.getByText("游戏时长(分)")).toBeInTheDocument();
    });

    it("renders favorite choice type", () => {
      render(<LifeReviewCard data={baseData} />);
      expect(screen.getByText("冒险")).toBeInTheDocument();
      expect(screen.getByText("偏好风格")).toBeInTheDocument();
    });
  });

  describe("Turning points", () => {
    it("renders turning points when present", () => {
      render(<LifeReviewCard data={baseData} />);
      expect(screen.getByText("人生转折点")).toBeInTheDocument();
      expect(screen.getByText("Found a hidden treasure")).toBeInTheDocument();
      expect(screen.getByText("Defeated the dragon")).toBeInTheDocument();
    });

    it("does not render turning points section when empty", () => {
      const data = { ...baseData, key_turning_points: [] };
      render(<LifeReviewCard data={data} />);
      expect(screen.queryByText("人生转折点")).not.toBeInTheDocument();
    });
  });

  describe("Achievement badge wall", () => {
    it("renders achievements when present", () => {
      render(<LifeReviewCard data={baseData} />);

      act(() => {
        jest.advanceTimersByTime(500);
      });

      expect(screen.getByTestId("achievement-section")).toBeInTheDocument();
      expect(screen.getByText("成就徽章墙 (2)")).toBeInTheDocument();
    });

    it("does not render achievements when empty", () => {
      const data = { ...baseData, achievement_badge_wall: [] };
      render(<LifeReviewCard data={data} />);
      expect(screen.queryByTestId("achievement-section")).not.toBeInTheDocument();
    });
  });

  describe("Edge cases", () => {
    it("renders with single personality label", () => {
      const data = { ...baseData, personality_labels: ["独行侠"] };
      render(<LifeReviewCard data={data} />);
      expect(screen.getByText("独行侠")).toBeInTheDocument();
    });

    it("renders with empty personality labels", () => {
      const data = { ...baseData, personality_labels: [] };
      render(<LifeReviewCard data={data} />);
      expect(screen.getByTestId("life-review-card")).toBeInTheDocument();
    });

    it("renders with single-value resource curves", () => {
      const data = {
        ...baseData,
        resource_curves: {
          energy: [50],
          mood: [50],
          knowledge: [50],
          wealth: [50],
        },
      };
      render(<LifeReviewCard data={data} />);
      // MiniSparkline returns null for less than 2 data points
      expect(screen.getByTestId("life-review-card")).toBeInTheDocument();
    });

    it("renders with empty resource curve arrays", () => {
      const data = {
        ...baseData,
        resource_curves: {
          energy: [],
          mood: [],
          knowledge: [],
          wealth: [],
        },
      };
      render(<LifeReviewCard data={data} />);
      expect(screen.getByTestId("life-review-card")).toBeInTheDocument();
    });

    it("renders with empty life motto", () => {
      const data = { ...baseData, life_motto: "" };
      render(<LifeReviewCard data={data} />);
      expect(screen.queryByText(/“”/)).not.toBeInTheDocument();
    });

    it("does not invent sections for empty review metadata", () => {
      const data: LifeReviewData = {
        personality_labels: [],
        key_turning_points: [],
        resource_curves: { energy: [], mood: [], knowledge: [], wealth: [] },
        achievement_badge_wall: [],
        relationship_network: { nodes: [], edges: [] },
        life_motto: "",
        play_duration_minutes: 0,
        total_decisions: 0,
        favorite_choice_type: "",
      };

      render(<LifeReviewCard data={data} />);

      expect(screen.queryByText("人格标签")).not.toBeInTheDocument();
      expect(screen.queryByText("总决策数")).not.toBeInTheDocument();
      expect(screen.queryByText("游戏时长(分)")).not.toBeInTheDocument();
      expect(screen.queryByText("偏好风格")).not.toBeInTheDocument();
      expect(screen.queryByText(/“”/)).not.toBeInTheDocument();
    });
  });
});
