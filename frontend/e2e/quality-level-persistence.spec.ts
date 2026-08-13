import { test, expect } from "@playwright/test";
import { ensureAuthenticated, API_URL } from "./helpers/auth";
import { openPlayTools } from "./helpers/play-tools";

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

    // 从当前视口的真实入口打开统一游戏工具面板
    const toolsDialog = await openPlayTools(page);

    // 选择大师
    const masterItem = toolsDialog.getByRole("radio", { name: "大师", exact: true });
    const settingsUpdate = page.waitForResponse((response) =>
      response.url().includes(`/api/games/${gameId}/settings`) &&
      response.request().method() === "PATCH" &&
      response.ok()
    );
    await masterItem.check();
    await settingsUpdate;

    // Selecting a radio item closes the Radix menu. Verify the durable API
    // value now; the rendered checked state is asserted after a full reload.
    const updatedStateResponse = await context.request.get(
      `${API_URL}/api/games/${gameId}`
    );
    expect(updatedStateResponse.ok()).toBeTruthy();
    const updatedState = await updatedStateResponse.json();
    expect(updatedState.constraint_level).toBe("master");

    // 刷新页面
    await page.reload();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // 再次打开工具面板验证
    const toolsDialogAfterReload = await openPlayTools(page);

    const masterItemAfterReload = toolsDialogAfterReload.getByRole("radio", {
      name: "大师",
      exact: true,
    });
    await expect(masterItemAfterReload).toBeChecked();
  });
});
