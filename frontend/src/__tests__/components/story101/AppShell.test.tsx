import React from "react";
import { render, screen } from "@testing-library/react";

import { AppShell } from "@/components/story101";

describe("AppShell", () => {
  it("keeps route content and persistent fixed regions in separate shell slots", () => {
    expect(AppShell).toEqual(expect.any(Function));

    render(
      <AppShell
        className="custom-shell"
        fixedRegions={<aside data-testid="fixed-region">声音</aside>}
        id="root-shell"
      >
        <article data-testid="route-content">正文</article>
      </AppShell>,
    );

    const shell = document.querySelector('[data-slot="app-shell"]');
    const content = document.querySelector('[data-slot="app-shell-content"]');
    const fixedRegions = document.querySelector('[data-slot="app-shell-fixed-regions"]');

    expect(shell).toBeInTheDocument();
    expect(shell).toHaveAttribute("id", "root-shell");
    expect(shell).toHaveClass("story101-app-shell", "custom-shell");
    expect(content).toContainElement(screen.getByTestId("route-content"));
    expect(content).not.toContainElement(screen.getByTestId("fixed-region"));
    expect(fixedRegions).toContainElement(screen.getByTestId("fixed-region"));
  });
});
