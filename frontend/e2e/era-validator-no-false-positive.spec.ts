import { test, expect } from "@playwright/test";
import { ensureAuthenticated } from "./helpers/auth";

const API_URL = "http://localhost:8000";

async function createAncientGame(
  context: import("@playwright/test").BrowserContext
): Promise<number> {
  const createResp = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: "李逍遥",
      life_vision: "成为一代大侠",
      character_settings: {
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
  return game.game_id;
}

test.describe("古代背景时代验证器无 false positive", () => {
  test("古代游戏能正常进入游玩页面且不触发时代误报", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createAncientGame(context);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // 页面应加载成功，不应出现错误提示
    const errorText = page.locator("text=出错了");
    await expect(errorText).not.toBeVisible();

    // 等待故事区域出现（说明后端生成成功）
    const storyArea = page.locator("[data-testid='story-text']").first();
    await expect(storyArea).toBeVisible({ timeout: 30000 });

    // 页面不应包含"检测到现代元素"的验证误报提示
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).not.toContain("检测到现代元素");
  });
});
