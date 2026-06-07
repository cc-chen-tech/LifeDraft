import { test, expect } from "@playwright/test";
import { ensureAuthenticated, API_URL } from "./helpers/auth";

// 通过 API 直接创建测试游戏
async function createTestGame(
  context: import("@playwright/test").BrowserContext
): Promise<number> {
  const createResp = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: "测试玩家",
      life_vision: "成为优秀的人",
      character_settings: {
        era: { name: "2024年", period: "现代", world_description: "人工智能全面融入日常生活的时代" },
        age: { age: 22, stage: "青年" },
        gender: { gender: "男", pronouns: "他" },
        world: { name: "普通现代", description: "与现实世界相似" },
        family: { description: "普通家庭" },
        relationships: { key_people: [], relationships_description: "暂无" },
        traits: { traits: ["勇敢", "好奇"] },
        wealth: { level: "中等", description: "普通家庭收入" },
      },
      language: "zh",
    },
  });

  if (!createResp.ok()) {
    throw new Error(`创建游戏失败: ${createResp.status()} ${await createResp.text()}`);
  }

  const game = await createResp.json();
  return game.game_id;
}

test.describe("叙事质量设置", () => {
  test("齿轮按钮下拉菜单可切换三级模式", async ({ page, context }) => {
    // 登录并创建游戏
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 直接访问 /play 页面
    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // 点击右上角齿轮按钮（设置）
    const settingsButton = page.locator("button[title='设置']").first();
    await expect(settingsButton).toBeVisible({ timeout: 20000 });
    await settingsButton.click();

    // 断言 DropdownMenu 可见且包含"设置"和"叙事质量"
    await expect(page.locator("text=设置").first()).toBeVisible();
    await expect(page.locator("text=叙事质量").first()).toBeVisible();

    // Hover 到"叙事质量"上展开子菜单
    await page.locator("text=叙事质量").first().hover();
    await page.waitForTimeout(300);

    // 子菜单中应包含三个选项
    await expect(page.locator("text=快速").first()).toBeVisible();
    await expect(page.locator("text=专家").first()).toBeVisible();
    await expect(page.locator("text=大师").first()).toBeVisible();

    // 选择"大师"
    const masterItem = page.locator("[role='menuitemradio']:has-text('大师')");
    await masterItem.click();

    // 验证"大师"项带有选中标记
    await expect(masterItem).toHaveAttribute("data-state", "checked");
  });
});
