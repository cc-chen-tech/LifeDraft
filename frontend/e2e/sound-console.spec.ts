import { expect, test } from "@playwright/test";

test.describe("Unified sound console", () => {
  test("shows music and story reading in one expanded sound console", async ({ page }) => {
    await page.goto("/e2e-regression?globalVoice=1");

    const miniBar = page.getByTestId("global-music-mini-bar");
    await expect(miniBar).toBeVisible();
    await miniBar.click();

    const panel = page.getByTestId("unified-sound-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("sound-console-unified-controls")).toBeVisible();
    await expect(page.getByTestId("sound-music-console")).toBeVisible();
    await expect(page.getByTestId("story-voice-console")).toBeVisible();

    await expect(panel.getByRole("button", { name: "播放" })).toBeVisible();
    await expect(panel.getByRole("button", { name: "朗读故事" })).toBeVisible();
    await expect(panel.getByRole("combobox", { name: "选择朗读声音" })).toBeVisible();
    await expect(panel.getByRole("checkbox", { name: "自动朗读" })).toBeVisible();
    await expect(panel.getByTestId("sound-music-row")).toHaveCount(0);
    await expect(panel.getByTestId("sound-reading-row")).toHaveCount(0);

    await page.screenshot({ path: "test-results/unified-sound-console.png", fullPage: false });
  });
});
