import { test, expect } from "@playwright/test";
import { ensureAuthenticated, API_URL } from "./helpers/auth";
import { openPlayTools } from "./helpers/play-tools";

// 通过 API 直接创建测试游戏
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

test.describe("叙事质量设置", () => {
  test("游戏工具可切换三级模式", async ({ page, context }) => {
    // 登录并创建游戏
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 直接访问 /play 页面
    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // 从当前视口的真实入口打开统一游戏工具面板
    const toolsDialog = await openPlayTools(page);
    await expect(toolsDialog.getByText("叙事质量", { exact: true })).toBeVisible();
    await expect(page.locator('[data-testid="chat-bar-panel"]')).not.toBeVisible();

    // 面板中直接提供三个原生 radio 选项
    await expect(toolsDialog.getByRole("radio", { name: "快速", exact: true })).toBeVisible();
    await expect(toolsDialog.getByRole("radio", { name: "专家", exact: true })).toBeVisible();
    await expect(toolsDialog.getByRole("radio", { name: "大师", exact: true })).toBeVisible();

    // 选择"大师"
    const masterItem = toolsDialog.getByRole("radio", { name: "大师", exact: true });
    await masterItem.check();

    // 验证"大师"原生 radio 已选中
    await expect(masterItem).toBeChecked();
  });
});
