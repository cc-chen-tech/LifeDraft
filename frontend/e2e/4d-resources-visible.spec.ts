import { test, expect, type Page } from "@playwright/test";
import { ensureAuthenticated, API_URL } from "./helpers/auth";

function observeUnexpectedGenerationRequests(page: Page, gameId: number): string[] {
  const generationPaths = new Set([
    `/api/games/${gameId}/event`,
    `/api/games/${gameId}/event-sync`,
  ]);
  const requests: string[] = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (generationPaths.has(url.pathname)) {
      requests.push(`${request.method()} ${request.url()}`);
    }
  });

  return requests;
}

async function createTestGame(
  context: import("@playwright/test").BrowserContext
): Promise<{ gameId: number; createdState: Record<string, unknown> }> {
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

  const game = (await createResp.json()) as Record<string, unknown>;
  return { gameId: game.game_id as number, createdState: game };
}

async function routeActionableGameState(
  page: Page,
  gameId: number,
  createdState: Record<string, unknown>,
): Promise<{ exactGameGetHits: number }> {
  const browserOrigin = new URL(page.url()).origin;
  const usage = { exactGameGetHits: 0 };

  await page.route(
    (url) =>
      url.origin === browserOrigin &&
      url.pathname === `/api/games/${gameId}` &&
      url.search === "",
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }

      usage.exactGameGetHits += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...createdState,
          current_event: {
            event_description: "资源展示测试已经准备好，可以继续当前生活。",
            story_text: "资源展示测试已经准备好，可以继续当前生活。",
            options: [
              { text: "继续当前生活", effects: {}, likely_choice: true },
              { text: "先整理已有信息", effects: {}, likely_choice: false },
            ],
          },
        }),
      });
    },
  );

  return usage;
}

test.describe("内部资源隐藏", () => {
  test("生成请求守卫覆盖带查询参数与直连后端的请求", async ({ page }) => {
    await page.goto("/");
    const gameId = 900001;
    const generationRequests = observeUnexpectedGenerationRequests(page, gameId);
    const browserOrigin = new URL(page.url()).origin;
    const queriedBrowserUrl = `${browserOrigin}/api/games/${gameId}/event?resume=1`;
    const directBackendUrl = `${API_URL}/api/games/${gameId}/event-sync?source=direct`;

    for (const targetUrl of [queriedBrowserUrl, directBackendUrl]) {
      await page.route(
        (url) => url.href === targetUrl,
        async (route) => {
          await route.fulfill({ status: 204 });
        },
      );
    }

    await page.evaluate(async ({ browserUrl, backendUrl }) => {
      await fetch(browserUrl, { method: "POST" });
      await fetch(backendUrl, { method: "GET", mode: "no-cors" });
    }, { browserUrl: queriedBrowserUrl, backendUrl: directBackendUrl });

    expect(generationRequests).toEqual([
      `POST ${queriedBrowserUrl}`,
      `GET ${directBackendUrl}`,
    ]);
  });

  test("游戏页面顶部状态栏隐藏内部资源", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const { gameId, createdState } = await createTestGame(context);
    const unexpectedGenerationRequests = observeUnexpectedGenerationRequests(page, gameId);
    const fixtureUsage = await routeActionableGameState(page, gameId, createdState);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");

    // 等待状态栏加载（playerState 需要时间从 API 获取）
    await page.waitForSelector("[data-testid='status-bar']", { timeout: 20000 });
    const statusBar = page.locator("[data-testid='status-bar']").first();
    await expect(statusBar).toBeVisible();
    await expect(page.getByRole("button", { name: /继续当前生活/ })).toBeVisible();

    await expect(statusBar).toContainText("岁");
    await expect(statusBar.locator("text=/精力|情绪|学识|财富|energy|mood|knowledge|wealth/i")).toHaveCount(0);
    expect(fixtureUsage.exactGameGetHits).toBe(1);
    expect(unexpectedGenerationRequests).toEqual([]);
  });

  test("API 仅保留三项内部资源且页面不展示资源数值", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const { gameId, createdState } = await createTestGame(context);
    const unexpectedGenerationRequests = observeUnexpectedGenerationRequests(page, gameId);
    const fixtureUsage = await routeActionableGameState(page, gameId, createdState);

    // 获取游戏状态 API
    const stateResp = await context.request.get(`${API_URL}/api/games/${gameId}/state`);
    expect(stateResp.status()).toBe(200);
    const state = await stateResp.json();
    const playerState = state.player_state || {};

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");

    // 等待状态栏加载完成
    await page.waitForSelector("[data-testid='status-bar']", { timeout: 15000 });
    await expect(page.getByRole("button", { name: /继续当前生活/ })).toBeVisible();

    expect(playerState).toHaveProperty("energy");
    expect(playerState).toHaveProperty("mood");
    expect(playerState).toHaveProperty("knowledge");
    expect(playerState).not.toHaveProperty("wealth");

    const energyValue = String(playerState.energy ?? "");
    if (energyValue) {
      await expect(page.locator(`text=精力: ${energyValue}`).first()).toHaveCount(0);
    }
    expect(fixtureUsage.exactGameGetHits).toBe(1);
    expect(unexpectedGenerationRequests).toEqual([]);
  });
});
