import { test, expect } from "@playwright/test";
import { ensureAuthenticated, API_URL } from "./helpers/auth";

type EventVersion = { event_id: string; revision: number };

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

async function seedEventForGame(
  context: import("@playwright/test").BrowserContext,
  gameId: number
): Promise<EventVersion> {
  const eventResp = await context.request.post(`${API_URL}/api/games/${gameId}/event-sync`, {
    data: {},
  });
  expect(eventResp.status(), await eventResp.text()).toBe(200);
  const event = await eventResp.json();
  expect(event.event_id).toEqual(expect.any(String));
  expect(event.revision).toEqual(expect.any(Number));
  return { event_id: event.event_id, revision: event.revision };
}

async function applyFirstChoiceForGame(
  context: import("@playwright/test").BrowserContext,
  gameId: number,
  event: EventVersion,
): Promise<Record<string, unknown>> {
  const choiceResp = await context.request.post(`${API_URL}/api/games/${gameId}/choice-sync`, {
    data: { option_index: 0, ...event },
  });
  expect(choiceResp.status(), await choiceResp.text()).toBe(200);
  return await choiceResp.json();
}

async function getSavedPlayerState(
  context: import("@playwright/test").BrowserContext,
  gameId: number
): Promise<Record<string, unknown>> {
  const stateResp = await context.request.get(`${API_URL}/api/games/${gameId}/state`);
  expect(stateResp.status()).toBe(200);
  const state = await stateResp.json();
  const playerState = state.player_state;
  expect(playerState).toBeTruthy();
  expect(typeof playerState).toBe("object");
  return playerState as Record<string, unknown>;
}

test.describe("选择影响资源隐藏", () => {
  test("选择后状态栏不显示资源变化", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);
    const event = await seedEventForGame(context, gameId);
    const result = await applyFirstChoiceForGame(context, gameId, event);
    expect(result).toHaveProperty("effects_applied");
    const savedPlayerState = await getSavedPlayerState(context, gameId);
    const savedEnergy = savedPlayerState.energy;
    expect(typeof savedEnergy).toBe("number");

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");

    const statusBar = page.getByTestId("status-bar").first();
    await expect(statusBar).toBeVisible({ timeout: 30000 });
    await expect(statusBar).not.toContainText(`精力: ${savedEnergy}`);
    await expect(statusBar).not.toContainText(/情绪|学识|财富/);
  });

  test("同步选择 API 返回 effects_applied", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 先生成一个事件
    const event = await seedEventForGame(context, gameId);

    // 做同步选择
    const result = await applyFirstChoiceForGame(context, gameId, event);
    // 结果中应包含 effects_applied（即使是空对象）
    expect(result).toHaveProperty("effects_applied");
    expect(typeof result.effects_applied).toBe("object");
  });
});
