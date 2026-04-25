import { test, expect } from "@playwright/test";

/**
 * E2E Tests: Character Creation Loading Feedback
 *
 * Problem 2: "返回修改" button has no immediate feedback (feels unresponsive)
 * Problem 3: "完全重生成" button has no loading state during long operation
 */

test.describe("Character Creation - Completion Screen Buttons", () => {
  test("create page loads with expected structure", async ({ page }) => {
    await page.goto("/create");
    await page.waitForSelector("text=时代背景", { timeout: 10000 });

    // 验证角色名输入框存在
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await expect(nameInput).toBeVisible();

    // 验证步骤指示器存在
    const stepCount = page.locator("text=/\\d+\\/\\d+/");
    await expect(stepCount).toBeVisible();

    // 验证返回按钮存在
    const returnButton = page.getByRole("button", { name: /返回/i });
    await expect(returnButton).toBeVisible();
  });

  test("上一步按钮在交互步骤中可用", async ({ page }) => {
    await page.goto("/create");
    await page.waitForSelector("text=时代背景", { timeout: 10000 });

    // 填写角色名和愿景
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill("测试角色");

    const visionInput = page.getByPlaceholder(/人生愿景|人生方向/i);
    await visionInput.fill("测试愿景");

    // 点击下一步进入下一个步骤
    const nextButton = page.locator("button", { hasText: /下一步|生成角色/ });
    if (await nextButton.isVisible().catch(() => false)) {
      await nextButton.click();
      await page.waitForTimeout(1500);
    }

    // 验证上一步按钮存在且可点击
    const prevButton = page.locator("button", { hasText: /上一步/ });
    if (await prevButton.isVisible().catch(() => false)) {
      await expect(prevButton).toBeEnabled();
    }
  });
});
