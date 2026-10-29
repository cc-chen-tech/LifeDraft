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
          start_date: "1200-01-01",
          starting_age: 22,
          era_description: "南宋时期的江南城镇",
          life_stage_description: "初入江湖的青年阶段",
          world_context: "古代中国的江湖世界，驿路和坊市连接地方社会",
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
  return game.game_id;
}

test.describe("古代背景时代验证器无 false positive", () => {
  test("古代游戏能正常进入游玩页面且不触发时代误报", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createAncientGame(context);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    const listening = page.getByTestId("story-listening-experience");
    await expect(listening.locator('[data-slot="choice-branch-row"]').first())
      .toBeEnabled({ timeout: 90_000 });

    const stateResponse = await context.request.get(`${API_URL}/api/games/${gameId}`);
    expect(stateResponse.ok()).toBe(true);
    const state = await stateResponse.json();
    expect(state.player_state.timeline.current_date).toBe("1200-01-01");
    expect(state.current_event.event_description.length).toBeGreaterThan(100);
    await expect(page.getByTestId("status-bar")).toContainText("公元 1200 年");

    await listening.getByRole("button", { name: "查看故事正文", exact: true }).click();
    const transcript = listening.getByRole("region", { name: "故事正文", exact: true });
    await expect(transcript).toBeVisible();
    await expect(transcript.getByRole("button", { name: /^从第 \d+ 段开始朗读$/ }))
      .toHaveText(state.current_event.event_description.split(/\n\s*\n/)
        .map((text: string) => text.trim()).filter(Boolean));

    // 页面不应包含"检测到现代元素"的验证误报提示
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).not.toContain("检测到现代元素");
  });
});
