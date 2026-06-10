import { expect, test } from "@playwright/test";

test.describe("Unified sound console", () => {
  test("shows music and story reading in one expanded sound console", async ({ page }) => {
    await page.goto("/e2e-regression?globalVoice=1");

    await expect(page.getByTestId("global-music-mini-bar")).toBeVisible();
    await page.getByRole("button", { name: "展开声音" }).click();

    const panel = page.getByTestId("unified-sound-panel");
    await expect(panel).toBeVisible();
    const controls = panel.getByTestId("sound-console-unified-controls");
    await expect(controls).toBeVisible();
    await expect(controls.getByTestId("sound-music-console")).toBeVisible();
    await expect(controls.getByTestId("story-voice-console")).toBeVisible();

    await expect(panel.getByRole("button", { name: /^播放(音乐)?$/ })).toBeVisible();
    await expect(panel.getByRole("button", { name: "朗读故事" })).toBeVisible();
    await expect(panel.getByRole("combobox", { name: "选择朗读声音" })).toBeVisible();
    await expect(panel.getByRole("checkbox", { name: "自动朗读" })).toBeVisible();
    await expect(panel.getByTestId("sound-music-row")).toHaveCount(0);
    await expect(panel.getByTestId("sound-reading-row")).toHaveCount(0);

    await page.screenshot({ path: "test-results/unified-sound-console.png", fullPage: false });
  });
});
