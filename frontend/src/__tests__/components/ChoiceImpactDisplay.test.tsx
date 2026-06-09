/**
 * ChoiceImpactDisplay Component Tests
 * Tests that hidden resource metrics do not render as visible choice effects.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { ChoiceImpactDisplay } from "@/components/game/ChoiceImpactDisplay";

describe("ChoiceImpactDisplay", () => {
  describe("Conditional rendering", () => {
    it("returns null when effects is null", () => {
      const { container } = render(<ChoiceImpactDisplay effects={null} />);
      expect(container.firstChild).toBeNull();
    });

    it("returns null when effects object is empty", () => {
      const { container } = render(<ChoiceImpactDisplay effects={{}} />);
      expect(container.firstChild).toBeNull();
    });

    it("returns null when all effects are zero", () => {
      const { container } = render(
        <ChoiceImpactDisplay
          effects={{ energy: 0, mood: 0, knowledge: 0, wealth: 0 }}
        />
      );
      expect(container.firstChild).toBeNull();
    });

    it("returns null when effects only contain hidden resource metrics", () => {
      const { container } = render(
        <ChoiceImpactDisplay
          effects={{ energy: 5, mood: -2, knowledge: 1, wealth: 100 }}
          currencyName="金币"
        />
      );

      expect(container.firstChild).toBeNull();
      expect(screen.queryByText("选择影响")).not.toBeInTheDocument();
      expect(screen.queryByText("精力")).not.toBeInTheDocument();
      expect(screen.queryByText("情绪")).not.toBeInTheDocument();
      expect(screen.queryByText("学识")).not.toBeInTheDocument();
      expect(screen.queryByText("财富")).not.toBeInTheDocument();
      expect(screen.queryByText("100金币")).not.toBeInTheDocument();
    });
  });

  describe("Non-resource effects", () => {
    it("renders non-resource effects without hidden resource metrics", () => {
      render(
        <ChoiceImpactDisplay
          effects={{ energy: 5, relationship: 3, reputation: -2 }}
        />
      );

      expect(screen.getByTestId("choice-impact")).toBeInTheDocument();
      expect(screen.getByText("选择影响")).toBeInTheDocument();
      expect(screen.getByText("relationship")).toBeInTheDocument();
      expect(screen.getByText("reputation")).toBeInTheDocument();
      expect(screen.queryByText("精力")).not.toBeInTheDocument();
      expect(screen.queryByText("情绪")).not.toBeInTheDocument();
      expect(screen.queryByText("学识")).not.toBeInTheDocument();
      expect(screen.queryByText("财富")).not.toBeInTheDocument();
    });

    it("accepts custom className when visible effects remain", () => {
      render(
        <ChoiceImpactDisplay
          effects={{ reputation: 1 }}
          className="custom-class"
        />
      );
      const card = screen.getByTestId("choice-impact");
      expect(card.className).toContain("custom-class");
    });
  });
});
