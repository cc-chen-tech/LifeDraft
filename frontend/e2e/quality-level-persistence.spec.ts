import { test, expect } from "@playwright/test";
import { ensureAuthenticated } from "./helpers/auth";

const API_URL = "http://localhost:8000";

// 通过 API 直接创建测试游戏
async function createTestGame(
  context: import("@playwright/test").BrowserContext
): Promise<number> {
  const createResp = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: "持久化测试玩家",
      life_vision: "测试刷新后保持大师模式",
      character_settings: {
        era: { name: "2024年", period: "现代", world_description: "人工智能时代" },
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

test.describe("叙事质量持久化", () => {
  test("选择大师后刷新页面仍保持大师", async ({ page, context }) => {
    // 登录并创建游戏
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 访问 /play 页面
    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // 打开齿轮按钮菜单
    const settingsButton = page.locator("button[title='设置']").first();
    await expect(settingsButton).toBeVisible({ timeout: 20000 });
    await settingsButton.click();

    // 展开叙事质量子菜单
    await page.locator("text=叙事质量").first().hover();
    await page.waitForTimeout(300);

    // 选择大师
    const masterItem = page.locator("[role='menuitemradio']:has-text('大师')");
    const settingsUpdate = page.waitForResponse((response) =>
      response.url().includes(`/api/games/${gameId}/settings`) &&
      response.request().method() === "PATCH" &&
      response.ok()
    );
    await masterItem.click();
    await settingsUpdate;

    // 验证已选中
    await expect(masterItem).toHaveAttribute("data-state", "checked");

    // 刷新页面
    await page.reload();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // 再次打开菜单验证
    await settingsButton.click();
    await page.locator("text=叙事质量").first().hover();
    await page.waitForTimeout(300);

    const masterItemAfterReload = page.locator("[role='menuitemradio']:has-text('大师')");
    await expect(masterItemAfterReload).toHaveAttribute("data-state", "checked");
  });
});
