import React from "react";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  FeedbackNotice,
  FormField,
  PageTransition,
  Surface,
} from "@/components/story101";

describe("Story101 foundation components", () => {
  it("wires a render-prop field to its visible label, description, and error without a fake tab stop", () => {
    render(
      <FormField
        id="character-name"
        label="角色姓名"
        description="将在故事中这样称呼你"
        error="请填写角色姓名"
        required
      >
        {({ describedBy, invalid, required }) => (
          <input
            id="character-name"
            aria-describedby={describedBy}
            aria-invalid={invalid}
            aria-required={required}
            required={required}
          />
        )}
      </FormField>
    );

    const input = screen.getByRole("textbox", { name: "角色姓名" });
    const description = screen.getByText("将在故事中这样称呼你");
    const error = screen.getByText("请填写角色姓名");

    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toBeRequired();
    expect(input).toHaveAttribute("aria-required", "true");
    expect(input).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining(description.id)
    );
    expect(input).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining(error.id)
    );
    expect(document.querySelectorAll("[tabindex]")).toHaveLength(0);
  });

  it.each([
    ["success", "status"],
    ["warning", "status"],
    ["danger", "alert"],
    ["info", "status"],
  ] as const)("uses one %s live region for %s feedback and keeps its action real", (tone, role) => {
    render(
      <FeedbackNotice
        tone={tone}
        title="保存状态"
        action={<button type="button">撤销</button>}
      >
        这项更改已记录。
      </FeedbackNotice>
    );

    const liveRegion = screen.getByRole(role);
    expect(screen.getAllByRole(role)).toHaveLength(1);
    expect(liveRegion).toHaveTextContent("保存状态");
    expect(liveRegion).toHaveTextContent("这项更改已记录。");
    if (tone === "danger") {
      expect(liveRegion).not.toHaveAttribute("aria-live");
    } else {
      expect(liveRegion).toHaveAttribute("aria-live", "polite");
    }
    expect(screen.getByRole("button", { name: "撤销" })).toBeInTheDocument();
  });

  it("preserves semantic props and selected variants for surfaces and page transitions", () => {
    render(
      <>
        <Surface asChild variant="raised">
          <article aria-label="角色卡片" id="character-card" data-owner="story101" />
        </Surface>
        <PageTransition aria-label="人生开篇" id="opening-page">
          <p>序章</p>
        </PageTransition>
      </>
    );

    const surface = screen.getByRole("article", { name: "角色卡片" });
    expect(surface).toHaveAttribute("id", "character-card");
    expect(surface).toHaveAttribute("data-owner", "story101");
    expect(surface).toHaveAttribute("data-variant", "raised");

    const transition = screen.getByRole("main", { name: "人生开篇" });
    expect(transition).toHaveAttribute("id", "opening-page");
    expect(transition).toHaveAttribute("data-slot", "page-transition");
    expect(transition).toHaveClass("story101-page-transition");

    const stylesheet = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
    expect(stylesheet).toMatch(
      /\.story101-page-transition\s*\{[^}]*animation:\s*story101-page-enter 200ms ease-out backwards/
    );
    expect(stylesheet).not.toMatch(
      /\.story101-page-transition\s*\{[^}]*animation:[^;}]*\b(?:forwards|both)\b/
    );
    expect(stylesheet).toMatch(
      /@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.story101-page-transition\s*\{[^}]*animation:\s*none/
    );
  });
});
