import { test, expect } from "@playwright/test";
import { ensureAuthenticated, API_URL } from "./helpers/auth";

async function createAncientGame(
  context: import("@playwright/test").BrowserContext
): Promise<number> {
  const createResp = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: "李逍遥",
      life_vision: "成为一代大侠",
      character_settings: {
        story_origin: {
          revision: 1,
          start_date: "1150-01-01",
          starting_age: 22,
          era_description: "南宋，古代中国",
          life_stage_description: "青年江湖人士",
          world_context: "南宋时期的江湖，无现代科技",
        },
        era: {
          name: "南宋",
          period: "古代",
          world_description: "中国历史上的南宋时期",
        },
        age: { age: 22, stage: "青年" },
        gender: { gender: "男", pronouns: "他" },
        world: {
          name: "古代中国",
          description: "武侠小说中的江湖世界",
        },
        family: { description: "普通家庭" },
        relationships: {
          key_people: [{ name: "赵灵儿", relation: "知己" }],
          relationships_description: "与赵灵儿相识于江湖",
        },
        traits: { traits: ["勇敢", "正义"] },
        wealth: { level: "中等", description: "普通江湖人士" },
      },
      language: "zh",
    },
  });

  if (!createResp.ok()) {
    throw new Error(`创建古代背景游戏失败: ${createResp.status()} ${await createResp.text()}`);
  }

  const game = await createResp.json();
  expect(game.player_state.character_settings.era.year).toBe(1150);
  expect(game.player_state.timeline.start_date).toBe("1150-01-01");
  return game.game_id;
}

test.describe("古代背景时代验证器无 false positive", () => {
  test("古代游戏能正常进入游玩页面且不触发时代误报", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createAncientGame(context);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole('heading', { name: '听故事', exact: true })).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: '查看故事正文', exact: true }).click();
    const storyArea = page.getByRole('region', { name: '故事正文', exact: true });
    await expect(storyArea).toBeVisible({ timeout: 30000 });
    await expect(storyArea).toContainText("李逍遥");
    await expect(storyArea).toContainText("赵灵儿");
    const stateResponse = await context.request.get(`${API_URL}/api/games/${gameId}`);
    expect(stateResponse.status()).toBe(200);
    const state = await stateResponse.json();
    expect(state.current_event.options.length).toBeGreaterThan(0);
    expect(state.player_state.character_settings.era.year).toBe(1150);

    // 页面不应包含"检测到现代元素"的验证误报提示
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).not.toContain("检测到现代元素");
  });
});
