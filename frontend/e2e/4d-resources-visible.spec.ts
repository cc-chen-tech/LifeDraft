import { test, expect } from "@playwright/test";
import { ensureAuthenticated } from "./helpers/auth";

const API_URL = "http://localhost:8000";

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

test.describe("4D 资源可见性", () => {
  test("游戏页面顶部状态栏显示 4D 资源", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");

    // 等待状态栏加载（playerState 需要时间从 API 获取）
    await page.waitForSelector("[data-testid='status-bar']", { timeout: 20000 });
    const statusBar = page.locator("[data-testid='status-bar']").first();
    await expect(statusBar).toBeVisible();

    // 4D 资源中至少有一个应可见（精力、情绪、学识、财富）
    const resourceLabels = page.locator("text=/精力|情绪|学识|财富|energy|mood|knowledge|wealth/i");
    const count = await resourceLabels.count();
    expect(count).toBeGreaterThan(0);
  });

  test("资源数值与 API 返回一致", async ({ page, context }) => {
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

    // 页面应显示 player_state 中的资源值（StatusBar 格式: "精力: 70"）
    const energyValue = String(playerState.energy ?? "");
    if (energyValue) {
      // StatusBar 以 "精力: 70" 格式渲染，text= 做子串匹配能找到
      await expect(page.locator(`text=精力: ${energyValue}`).first()).toBeVisible({ timeout: 10000 });
    }
  });
});
