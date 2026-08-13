import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import ErrorPage from "@/app/error";
import GlobalError from "@/app/global-error";
import Loading from "@/app/loading";
import NotFound from "@/app/not-found";
import * as Sentry from "@sentry/nextjs";

jest.mock("@sentry/nextjs", () => ({
  captureException: jest.fn(),
}));
jest.mock("@/app/globals.css", () => ({}));

describe("Story101 global states", () => {
  let consoleError: jest.SpiedFunction<typeof console.error>;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    consoleError = jest.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    consoleError.mockRestore();
    jest.useRealTimers();
  });

  it("keeps route loading silent through 249ms before exposing one hydrate status at 250ms", () => {
    render(<Loading />);

    expect(screen.queryAllByRole("status")).toHaveLength(0);
    act(() => jest.advanceTimersByTime(249));
    expect(screen.queryAllByRole("status")).toHaveLength(0);

    act(() => jest.advanceTimersByTime(1));
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByTestId("narrative-loading-screen")).toBeInTheDocument();
  });

  it.each([
    ["route error", ErrorPage],
    ["global error", GlobalError],
  ])("calls reset exactly once from the named %s button", (_name, StatePage) => {
    const reset = jest.fn();
    const failure = new Error("failed");

    render(<StatePage error={failure} reset={reset} />);
    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    expect(reset).toHaveBeenCalledTimes(1);
    expect(Sentry.captureException).toHaveBeenCalledWith(failure);
  });

  it("exposes a named not-found link to the home route", () => {
    render(<NotFound />);

    const homeLink = screen.getByRole("link", { name: "返回首页" });
    expect(homeLink).toHaveAttribute("href", "/");
    expect(homeLink).not.toHaveAttribute("type");
  });

  it("keeps the global-error fallback rooted at html and body", () => {
    const markup = renderToStaticMarkup(
      <GlobalError error={new Error("failed")} reset={jest.fn()} />
    );

    expect(markup).toMatch(/^<html><head><\/head><body>/);
    expect(markup).toMatch(
      /<main[^>]*class="[^"]*story101-page-transition[^"]*min-h-\[100dvh\][^"]*"/
    );
  });

  it("declares the app stylesheet for root-layout-independent rendering", () => {
    const source = readFileSync(resolve(process.cwd(), "src/app/global-error.tsx"), "utf8");

    expect(source).toMatch(/import ["']\.\/globals\.css["'];/);
  });
});
