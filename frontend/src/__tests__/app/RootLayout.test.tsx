import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import RootLayout, { metadata, viewport } from "@/app/layout";

jest.mock("@/app/globals.css", () => ({}));
jest.mock("@/components/ErrorReporter", () => ({
  __esModule: true,
  default: function ErrorReporterTestDouble() {
    return <div data-testid="error-reporter" />;
  },
}));
jest.mock("@/components/game/GlobalMusicPlayerWrapper", () => ({
  __esModule: true,
  default: function GlobalMusicPlayerWrapperTestDouble() {
    return <div data-testid="global-music-player-wrapper" />;
  },
}));

describe("RootLayout AppShell boundary", () => {
  it("keeps route content and the global player inside one persistent AppShell", () => {
    const markup = renderToStaticMarkup(
      <RootLayout>
        <main data-testid="route-page">route page</main>
      </RootLayout>,
    );
    const host = document.createElement("div");
    host.innerHTML = markup;

    const shell = host.querySelector('[data-slot="app-shell"]');
    const content = host.querySelector('[data-slot="app-shell-content"]');
    const fixedRegions = host.querySelector('[data-slot="app-shell-fixed-regions"]');
    const errorReporter = host.querySelector('[data-testid="error-reporter"]');

    expect(shell).not.toBeNull();
    expect(shell?.previousElementSibling).toBe(errorReporter);
    expect(shell).not.toContainElement(errorReporter);
    expect(content).toContainElement(host.querySelector('[data-testid="route-page"]'));
    expect(fixedRegions).toContainElement(
      host.querySelector('[data-testid="global-music-player-wrapper"]'),
    );
  });

  it("publishes the lowercase brand and enables safe-area viewport insets", () => {
    expect(metadata.title).toBe("story101 - 人生模拟器");
    expect(viewport.viewportFit).toBe("cover");
  });
});
