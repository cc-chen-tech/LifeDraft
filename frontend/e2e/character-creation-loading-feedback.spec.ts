import { test, expect } from "@playwright/test";
import {
  FRONTEND_ORIGIN,
  installEraGenerationFixture,
} from "./helpers/character-setting-fixture";

/**
 * E2E Tests: Character Creation Loading Feedback
 *
 * Problem 2: "返回修改" button has no immediate feedback (feels unresponsive)
 * Problem 3: "完全重生成" button has no loading state during long operation
 */

test.describe("Character Creation - Completion Screen Buttons", () => {
  test("create page loads with expected structure", async ({ page }) => {
    await page.goto("/create");
    await expect(page.getByRole("heading", { name: "时代背景", level: 2 })).toBeVisible();

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
    const requests = await installEraGenerationFixture(page);
    await page.goto("/create");
    await expect(page.getByRole("heading", { name: "时代背景", level: 2 })).toBeVisible();

    const visionInput = page.getByPlaceholder(/人生愿景|人生方向/i);
    await visionInput.fill("测试愿景");
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill("测试角色");

    await expect(page.getByText("刚刚生成")).toBeVisible();
    expect(requests).toEqual([
      {
        method: "POST",
        origin: FRONTEND_ORIGIN,
        path: "/api/character/setting",
        search: "",
        settingType: "era",
      },
    ]);

    // 点击下一步进入下一个步骤
    const nextButton = page.getByRole("button", { name: "下一步" });
    await expect(nextButton).toBeVisible();
    await expect(nextButton).toBeEnabled();
    await nextButton.click();

    // 验证上一步按钮存在且可点击
    await expect(page.getByRole("heading", { name: "年龄阶段", level: 2 })).toBeVisible();
    const prevButton = page.getByRole("button", { name: "上一步" });
    await expect(prevButton).toBeVisible();
    await expect(prevButton).toBeEnabled();
  });
});
