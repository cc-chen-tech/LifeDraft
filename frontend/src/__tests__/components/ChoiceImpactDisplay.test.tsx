/**
 * ChoiceImpactDisplay Component Tests
 * Tests the choice impact display with various effect combinations
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { ChoiceImpactDisplay } from "@/components/game/ChoiceImpactDisplay";

describe("ChoiceImpactDisplay", () => {
  describe("Conditional rendering", () => {
    it("returns null when effects is null", () => {
      const { container } = render(
        <ChoiceImpactDisplay effects={null} />
      );
      expect(container.firstChild).toBeNull();
    });

    it("returns null when effects object is empty", () => {
      const { container } = render(
        <ChoiceImpactDisplay effects={{}} />
      );
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

    it("renders when at least one effect is non-zero", () => {
      render(<ChoiceImpactDisplay effects={{ energy: 5 }} />);
      expect(screen.getByTestId("choice-impact")).toBeInTheDocument();
    });
  });

  describe("Resource display", () => {
    it("renders energy resource with positive value", () => {
      render(<ChoiceImpactDisplay effects={{ energy: 10 }} />);
      expect(screen.getByText("精力")).toBeInTheDocument();
      expect(screen.getByText("10")).toBeInTheDocument();
    });

    it("renders mood resource with positive value", () => {
      render(<ChoiceImpactDisplay effects={{ mood: 5 }} />);
      expect(screen.getByText("情绪")).toBeInTheDocument();
      expect(screen.getByText("5")).toBeInTheDocument();
    });

    it("renders knowledge resource with positive value", () => {
      render(<ChoiceImpactDisplay effects={{ knowledge: 3 }} />);
      expect(screen.getByText("学识")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
    });

    it("renders wealth resource with currency formatting", () => {
      render(
        <ChoiceImpactDisplay
          effects={{ wealth: 1000 }}
          currencyName="金币"
        />
      );
      expect(screen.getByText("财富")).toBeInTheDocument();
      expect(screen.getByText("1,000金币")).toBeInTheDocument();
    });
  });

  describe("Negative effects", () => {
    it("renders negative energy effect", () => {
      render(<ChoiceImpactDisplay effects={{ energy: -5 }} />);
      expect(screen.getByText("精力")).toBeInTheDocument();
      expect(screen.getByText("5")).toBeInTheDocument(); // absolute value
    });

    it("renders negative mood effect", () => {
      render(<ChoiceImpactDisplay effects={{ mood: -8 }} />);
      expect(screen.getByText("情绪")).toBeInTheDocument();
    });

    it("renders negative wealth effect", () => {
      render(
        <ChoiceImpactDisplay
          effects={{ wealth: -500 }}
          currencyName="银两"
        />
      );
      expect(screen.getByText("财富")).toBeInTheDocument();
      expect(screen.getByText("500银两")).toBeInTheDocument();
    });
  });

  describe("Multiple effects", () => {
    it("renders multiple resources simultaneously", () => {
      render(
        <ChoiceImpactDisplay
          effects={{ energy: 3, mood: -2, knowledge: 1, wealth: 100 }}
        />
      );
      expect(screen.getByText("精力")).toBeInTheDocument();
      expect(screen.getByText("情绪")).toBeInTheDocument();
      expect(screen.getByText("学识")).toBeInTheDocument();
      expect(screen.getByText("财富")).toBeInTheDocument();
    });

    it("skips resources with undefined values", () => {
      render(<ChoiceImpactDisplay effects={{ energy: 5 }} />);
      expect(screen.getByText("精力")).toBeInTheDocument();
      expect(screen.queryByText("情绪")).not.toBeInTheDocument();
      expect(screen.queryByText("学识")).not.toBeInTheDocument();
      expect(screen.queryByText("财富")).not.toBeInTheDocument();
    });

    it("skips zero values even when other resources have values", () => {
      render(
        <ChoiceImpactDisplay
          effects={{ energy: 5, mood: 0, knowledge: -3 }}
        />
      );
      expect(screen.getByText("精力")).toBeInTheDocument();
      expect(screen.queryByText("情绪")).not.toBeInTheDocument();
      expect(screen.getByText("学识")).toBeInTheDocument();
    });
  });

  describe("Title and layout", () => {
    it("renders the title", () => {
      render(<ChoiceImpactDisplay effects={{ energy: 1 }} />);
      expect(screen.getByText("选择影响")).toBeInTheDocument();
    });

    it("accepts custom className", () => {
      render(
        <ChoiceImpactDisplay
          effects={{ energy: 1 }}
          className="custom-class"
        />
      );
      const card = screen.getByTestId("choice-impact");
      expect(card.className).toContain("custom-class");
    });
  });

  describe("Default currency name", () => {
    it("uses default currency name '货币'", () => {
      render(<ChoiceImpactDisplay effects={{ wealth: 200 }} />);
      expect(screen.getByText("200货币")).toBeInTheDocument();
    });
  });
});
