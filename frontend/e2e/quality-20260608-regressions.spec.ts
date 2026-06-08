import { expect, test } from "@playwright/test";
import { API_URL, ensureAuthenticated } from "./helpers/auth";

test.describe("2026-06-08 quality regressions", () => {
  test("new game keeps configured yuan wealth through API and status bar", async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const createResp = await context.request.post(`${API_URL}/api/games`, {
      data: {
        player_name: "测试小可",
        life_vision: "成为可靠的产品经理",
        language: "zh",
        character_settings: {
          era: { era_description: "2026 年现代互联网职场" },
          age: { age: 24 },
          gender: { gender: "女" },
          occupation: { occupation: "产品经理", employer: "AI 协作平台" },
          family: { family_economy: "中产" },
          relationships: {
            key_people: [
              { name: "陆昊然", role: "导师", relationship_desc: "产品导师" },
              { name: "陈晓雨", role: "闺蜜", relationship_desc: "大学好友" },
              { name: "林一凡", role: "同期", relationship_desc: "同期产品经理" },
            ],
          },
          traits: { personality: ["务实", "好奇"] },
          wealth: {
            wealth: 50000,
            currency: "¥",
            currency_name: "元",
            wealth_description: "个人储蓄和家庭支持合计五万元。",
          },
        },
      },
    });
    expect(createResp.ok()).toBe(true);
    const created = await createResp.json();
    const gameId = created.game_id;

    const stateResp = await context.request.get(`${API_URL}/api/games/${gameId}/state`);
    expect(stateResp.status()).toBe(200);
    const state = await stateResp.json();
    expect(state.player_state.wealth).toBe(50000);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByTestId("status-bar")).toContainText("财富: ¥50,000", {
      timeout: 20000,
    });
    await expect(page.getByTestId("status-bar")).not.toContainText("10,000货币");
  });
});
