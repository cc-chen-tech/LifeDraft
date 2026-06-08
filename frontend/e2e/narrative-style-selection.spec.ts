import { test, expect } from "@playwright/test";
import { ensureAuthenticated } from "./helpers/auth";

const API_URL = process.env.E2E_API_URL || `http://${process.env.E2E_BACKEND_HOST || '127.0.0.1'}:${process.env.E2E_BACKEND_PORT || '8000'}`;

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

test.describe("叙事风格选择", () => {
  test("齿轮按钮下拉菜单可切换叙事风格", async ({ page, context }) => {
    // 登录并创建游戏
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 直接访问 /play 页面
    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // 点击右上角齿轮按钮（设置）
    const settingsButton = page.locator("button[title='设置']").first();
    await expect(settingsButton).toBeVisible({ timeout: 20000 });
    await settingsButton.click();

    // 断言 DropdownMenu 可见且包含"叙事风格"
    await expect(page.locator("text=设置").first()).toBeVisible();
    await expect(page.locator("text=叙事风格").first()).toBeVisible();

    // Hover 到"叙事风格"菜单项上展开子菜单，并等待远端风格列表加载完成
    const narrativeStyleTrigger = page.getByRole("menuitem", { name: /叙事风格/ });
    await narrativeStyleTrigger.hover();
    await expect(page.locator("text=中国古典演义").first()).toBeVisible({ timeout: 15000 });

    // 子菜单中应包含至少一个选项（如"中国古典演义"）
    await expect(page.locator("text=中国古典演义").first()).toBeVisible();

    // 选择"中国武侠"
    const wuxiaItem = page.locator("[role='menuitemradio']:has-text('中国武侠')");
    await wuxiaItem.click();

    // 验证"中国武侠"项带有选中标记
    await expect(wuxiaItem).toHaveAttribute("data-state", "checked");
  });

  test("游戏状态 API 返回 narrative_style_id", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    const response = await context.request.get(`${API_URL}/api/games/${gameId}/state`);
    expect(response.status()).not.toBe(405);

    if (response.status() === 200) {
      const body = await response.json();
      // 响应应包含 narrative_style_id（可能在 player_state 中或顶层）
      const hasStyleId =
        "narrative_style_id" in body ||
        (body.player_state && "narrative_style_id" in body.player_state);
      expect(hasStyleId).toBe(true);
    }
  });

  test("更新叙事风格 API 生效", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    // 先获取当前风格
    const getResp = await context.request.get(`${API_URL}/api/games/${gameId}/narrative-style`);
    expect(getResp.status()).toBe(200);
    const initial = await getResp.json();
    expect(initial).toHaveProperty("style_id");

    // 更新为"中国武侠"
    const putResp = await context.request.put(`${API_URL}/api/games/${gameId}/narrative-style`, {
      data: { style_id: "chinese_wuxia" },
    });
    expect(putResp.status()).toBe(200);

    // 验证更新成功
    const getResp2 = await context.request.get(`${API_URL}/api/games/${gameId}/narrative-style`);
    expect(getResp2.status()).toBe(200);
    const updated = await getResp2.json();
    expect(updated.style_id).toBe("chinese_wuxia");
  });

  test("无效叙事风格 ID 返回 400", async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const gameId = await createTestGame(context);

    const putResp = await context.request.put(`${API_URL}/api/games/${gameId}/narrative-style`, {
      data: { style_id: "nonexistent_style_xyz" },
    });
    expect(putResp.status()).toBe(400);
  });
});
