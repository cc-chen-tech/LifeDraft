import { test, expect } from "@playwright/test";
import { ensureAuthenticated, API_URL } from "./helpers/auth";

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

test.describe("内部资源隐藏", () => {
  test("游戏页面顶部状态栏隐藏内部资源", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");

    // 等待状态栏加载（playerState 需要时间从 API 获取）
    await page.waitForSelector("[data-testid='status-bar']", { timeout: 20000 });
    const statusBar = page.locator("[data-testid='status-bar']").first();
    await expect(statusBar).toBeVisible();

    await expect(statusBar).toContainText("岁");
    await expect(statusBar.locator("text=/精力|情绪|学识|财富|energy|mood|knowledge|wealth/i")).toHaveCount(0);
  });

  test("API 仅保留三项内部资源且页面不展示资源数值", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 获取游戏状态 API
    const stateResp = await context.request.get(`${API_URL}/api/games/${gameId}/state`);
    expect(stateResp.status()).toBe(200);
    const state = await stateResp.json();
    const playerState = state.player_state || {};

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");

    // 等待状态栏加载完成
    await page.waitForSelector("[data-testid='status-bar']", { timeout: 15000 });

    expect(playerState).toHaveProperty("energy");
    expect(playerState).toHaveProperty("mood");
    expect(playerState).toHaveProperty("knowledge");
    expect(playerState).not.toHaveProperty("wealth");

    const energyValue = String(playerState.energy ?? "");
    if (energyValue) {
      await expect(page.locator(`text=精力: ${energyValue}`).first()).toHaveCount(0);
    }
  });
});
