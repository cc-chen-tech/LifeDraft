import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  NarrativeLoadingState,
  resolveNarrativeLoadingCopy,
} from "@/components/narrative-loading/NarrativeLoadingState";

describe("resolveNarrativeLoadingCopy", () => {
  it.each([
    ["hydrate", "正在打开这一页"],
    ["character-step", "角色设定，正在成形"],
    ["character-auto", "角色背景，正在补全"],
    ["opening", "人生开篇，正在落笔"],
    ["gameplay", "下一页，正在展开"],
    ["ending", "这一生，正在收束"],
  ] as const)("uses the approved title for %s", (context, title) => {
    expect(resolveNarrativeLoadingCopy({ context })).toMatchObject({ title });
  });

  it.each([
    ["preparing", "正在准备"],
    ["resuming", "正在准备"],
    ["initializing", "正在准备"],
    ["loading_context", "正在梳理"],
    ["building_world", "正在梳理"],
    ["generating", "正在写作"],
    ["generating_story", "正在写作"],
    ["retry", "正在写作"],
    ["retrying", "正在写作"],
    ["validating", "正在校对"],
    ["generating_options", "正在准备选择"],
  ] as const)("groups real phase %s as %s", (phase, status) => {
    expect(resolveNarrativeLoadingCopy({ context: "gameplay", phase })).toMatchObject({ status });
  });

  it("prefers a real step label and falls back by operation for an unknown phase", () => {
    expect(
      resolveNarrativeLoadingCopy({
        context: "character-step",
        phase: "building_world",
        stepLabel: "正在确认成长地点",
      })
    ).toMatchObject({ status: "正在确认成长地点" });
    expect(
      resolveNarrativeLoadingCopy({ context: "gameplay", phase: "unknown", operation: "event" })
    ).toMatchObject({ status: "正在继续写作" });
    expect(
      resolveNarrativeLoadingCopy({ context: "gameplay", phase: "unknown", operation: "choice" })
    ).toMatchObject({ status: "正在继续推演" });
  });

  it("keeps hydration free of normal phase copy", () => {
    expect(resolveNarrativeLoadingCopy({ context: "hydrate", phase: "preparing" })).toMatchObject({
      status: undefined,
    });
  });

  it("does not surface stale labels after completion", () => {
    expect(
      resolveNarrativeLoadingCopy({
        context: "gameplay",
        phase: "completed",
        stepLabel: "正在生成",
        contextLabel: "正在整理",
      })
    ).toMatchObject({ status: undefined });
  });

  it("uses a restrained delayed copy and only exposes transport actions for an abnormal transport", () => {
    expect(resolveNarrativeLoadingCopy({ context: "opening", delayed: true })).toMatchObject({
      delayedCopy: "这一页仍在继续写作",
      actionLabel: undefined,
    });
    expect(resolveNarrativeLoadingCopy({ context: "gameplay", transport: "reconnecting" })).toMatchObject({
      actionLabel: "重新连接",
    });
    expect(resolveNarrativeLoadingCopy({ context: "gameplay", transport: "polling" })).toMatchObject({
      actionLabel: "重新连接",
    });
    expect(resolveNarrativeLoadingCopy({ context: "ending", transport: "failed" })).toMatchObject({
      actionLabel: "重试",
    });
  });

  it("keeps copy free of forbidden time, range, percentage, quality, and AI language", () => {
    const copy = resolveNarrativeLoadingCopy({
      context: "gameplay",
      phase: "generating",
      delayed: true,
    });
    expect(Object.values(copy).filter((value): value is string => typeof value === "string").join(" "))
      .not.toMatch(/AI|\d|%|分钟|秒|预计|fast|expert|master/i);
  });
});

describe("NarrativeLoadingState", () => {
  it.each([
    ["screen", "narrative-loading--screen"],
    ["section", "narrative-loading--section"],
    ["inline", "narrative-loading--inline"],
  ] as const)("renders the %s layout", (layout, layoutClass) => {
    const { container } = render(<NarrativeLoadingState context="gameplay" layout={layout} />);
    expect(container.firstElementChild).toHaveClass(layoutClass);
  });

  it("has exactly one live status region and no normal action", () => {
    render(<NarrativeLoadingState context="gameplay" layout="section" phase="generating" delayed />);
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders real transport actions outside the live region", () => {
    const onAction = jest.fn();
    render(
      <NarrativeLoadingState
        context="ending"
        layout="screen"
        transport="failed"
        onAction={onAction}
      />
    );
    const action = screen.getByRole("button", { name: "重试" });
    expect(action.closest('[role="status"]')).toBeNull();
    fireEvent.click(action);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("uses only the divider breath, never spinner, skeleton, pulse, or shimmer semantics", () => {
    const { container } = render(<NarrativeLoadingState context="opening" layout="inline" />);
    expect(container.querySelector(".narrative-loading-divider")).toBeInTheDocument();
    expect(container.querySelector(".animate-spin, .animate-pulse, .skeleton-shimmer, [class*='spinner'], [class*='skeleton'], [class*='shimmer']")).toBeNull();
  });

  it("keeps the divider completely static for reduced motion", () => {
    const stylesheet = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
    expect(stylesheet).toMatch(
      /@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*?\.narrative-loading-divider\s*\{[\s\S]*?animation:\s*none/
    );
  });
});
