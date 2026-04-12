import { test, expect } from "@playwright/test";

test.describe("叙事质量设置", () => {
  test("齿轮按钮下拉菜单可切换三级模式", async ({ page }) => {
    // 访问首页并等待加载
    await page.goto("/");
    await page.waitForSelector("text=新游戏", { timeout: 10000 });

    // 点击开始新游戏进入角色创建流程
    await page.click("text=新游戏");
    await page.waitForTimeout(500);

    // 处理可能的登录/创建账户弹窗
    const createAccountModal = page.locator("text=创建账户").first();
    if (await createAccountModal.isVisible({ timeout: 3000 }).catch(() => false)) {
      await page.fill("input[placeholder='你的名字']", "测试用户");
      await page.locator("button:has-text('创建账户')").last().click();
      await page.waitForTimeout(1500);
    }

    // 快速完成创建流程（选择时代、年龄、性别、世界观）
    // Step 1: 时代
    await page.waitForSelector("text=选择时代背景", { timeout: 10000 });
    await page.click("button:has-text('现代都市')");
    await page.waitForTimeout(300);

    // Step 2: 年龄阶段
    await page.waitForSelector("text=选择年龄阶段", { timeout: 10000 });
    await page.click("button:has-text('青年')");
    await page.waitForTimeout(300);

    // Step 3: 性别
    await page.waitForSelector("text=选择性别", { timeout: 10000 });
    await page.click("button:has-text('男')");
    await page.waitForTimeout(300);

    // Step 4: 世界观
    await page.waitForSelector("text=选择世界观", { timeout: 10000 });
    await page.click("button:has-text('普通现代')");
    await page.waitForTimeout(300);

    // Step 5: 输入玩家名称和人生愿景
    await page.waitForSelector("input[placeholder*='名字']", { timeout: 10000 });
    await page.fill("input[placeholder*='名字']", "测试玩家");
    await page.fill("textarea", "成为优秀的人");
    await page.click("text=开始游戏");

    // 等待进入 /play 页面
    await page.waitForURL(/\/play/, { timeout: 30000 });
    await page.waitForTimeout(2000);

    // 点击右上角齿轮按钮
    const settingsButton = page.locator("button[title='设置']").first();
    await expect(settingsButton).toBeVisible({ timeout: 20000 });
    await settingsButton.click();

    // 断言 DropdownMenu 可见且包含"叙事质量"
    await expect(page.locator("text=叙事质量").first()).toBeVisible();
    await expect(page.locator("text=快速").first()).toBeVisible();
    await expect(page.locator("text=专家").first()).toBeVisible();
    await expect(page.locator("text=大师").first()).toBeVisible();

    // 选择"大师"
    await page.locator("text=叙事质量").first().hover();
    await page.waitForTimeout(300);
    await page.locator("[role='menuitemradio']:has-text('大师')").click();

    // 再次打开菜单，验证"大师"带有选中标记
    await settingsButton.click();
    await page.locator("text=叙事质量").first().hover();
    await page.waitForTimeout(300);

    const masterItem = page.locator("[role='menuitemradio']:has-text('大师')");
    await expect(masterItem).toHaveAttribute("data-state", "checked");
  });
});
