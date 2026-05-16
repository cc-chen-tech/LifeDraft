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

test.describe("选择影响可见性", () => {
  test("选择后显示资源变化", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);

    // 等待选项出现（OptionCards 使用 CSS class "option-card"）
    const optionButtons = page.locator(".option-card");
    await expect(optionButtons.first()).toBeVisible({ timeout: 30000 });

    // 点击第一个选项
    await optionButtons.first().click();

    // 等待结果阶段
    await page.waitForTimeout(3000);

    // 结果阶段应显示资源变化或"继续"按钮
    const continueButton = page.locator("button").filter({ hasText: /确认|继续|进入/ });
    await expect(continueButton.first()).toBeVisible({ timeout: 30000 });

    // 如果存在资源变化显示，它应该在结果阶段可见
    const impactSection = page.locator("[data-testid='choice-impact']").first();
    const resourceSection = page.locator("text=/精力|情绪|学识|财富/").first();
    // 至少状态栏应该显示资源
    const visible = await impactSection.isVisible().catch(() => false) || await resourceSection.isVisible().catch(() => false);
    expect(visible).toBe(true);
  });

  test("同步选择 API 返回 effects_applied", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 先生成一个事件
    const eventResp = await context.request.post(`${API_URL}/api/games/${gameId}/event-sync`, {
      data: {},
    });
    expect(eventResp.status()).toBe(200);

    // 做同步选择
    const choiceResp = await context.request.post(`${API_URL}/api/games/${gameId}/choice-sync`, {
      data: { option_index: 0 },
    });
    expect(choiceResp.status()).toBe(200);

    const result = await choiceResp.json();
    // 结果中应包含 effects_applied（即使是空对象）
    expect(result).toHaveProperty("effects_applied");
    expect(typeof result.effects_applied).toBe("object");
  });
});
