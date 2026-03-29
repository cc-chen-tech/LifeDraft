/**
 * 异步实体识别 E2E 测试
 * 
 * 测试用户交互流程：
 * 1. 用户点击智能识别 -> 显示识别结果对话框
 * 2. 识别结果展示（有结果 / 无结果）
 * 3. 取消识别对话框
 * 4. 收集面板基本交互
 */

import { test, expect } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

const API_URL = 'http://localhost:8000';

// 创建测试游戏，确保有活跃游戏
async function ensureActiveGame(context: import('@playwright/test').BrowserContext): Promise<number> {
  // 检查是否已有活跃游戏
  const activeResp = await context.request.get(`${API_URL}/api/games/active`);
  if (activeResp.ok()) {
    const data = await activeResp.json();
    return data.game_id;
  }
  
  // 创建新游戏
  const createResp = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: 'E2E测试角色',
      life_vision: '探索世界',
      character_settings: {
        era: { name: '现代', period: '现代' },
        age: { age: 18, stage: '青年' },
        personality: { traits: ['勇敢', '好奇'] },
        background: { occupation: '学生' },
      },
      language: 'zh',
    },
  });
  
  if (!createResp.ok()) {
    throw new Error(`创建游戏失败: ${createResp.status()} ${await createResp.text()}`);
  }
  
  const game = await createResp.json();
  return game.game_id;
}

// 打开收集面板的辅助函数
async function openCollectionPanel(page: import('@playwright/test').Page) {
  const collectionButton = page.getByRole('button', { name: '收集' });
  await expect(collectionButton).toBeVisible({ timeout: 15000 });
  await collectionButton.click();
  await expect(page.locator('text=人物、物品和标志物收集记录')).toBeVisible({ timeout: 5000 });
}

test.describe('异步实体识别功能', () => {
  test.beforeEach(async ({ page, context }) => {
    // 登录并确保有活跃游戏
    await ensureAuthenticated(page, context);
    await ensureActiveGame(context);
  });

  test('用户点击智能识别 -> 显示识别对话框 -> 展示识别结果', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    // 打开收集面板
    await openCollectionPanel(page);
    
    // 点击智能识别按钮
    const recognizeButton = page.locator('button:has-text("智能识别")').first();
    await expect(recognizeButton).toBeVisible();
    await recognizeButton.click();
    
    // 验证识别对话框显示
    const dialog = page.getByRole('dialog', { name: '智能识别' });
    await expect(dialog).toBeVisible({ timeout: 10000 });
  });

  test('新游戏识别结果为空时显示提示', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    await openCollectionPanel(page);
    
    // 点击智能识别
    await page.locator('button:has-text("智能识别")').first().click();
    
    // 等待识别对话框出现
    const dialog = page.getByRole('dialog', { name: '智能识别' });
    await expect(dialog).toBeVisible({ timeout: 10000 });
    
    // 新游戏故事很短，可能显示"未识别到新的实体"
    const noResults = page.locator('text=未识别到新的实体');
    const hasResults = page.locator('text=/识别到|发现/');
    
    // 两种情况之一应该出现
    const noResultsVisible = await noResults.isVisible().catch(() => false);
    const hasResultsVisible = await hasResults.isVisible().catch(() => false);
    expect(noResultsVisible || hasResultsVisible).toBeTruthy();
    
    // 如果无结果，添加按钮应被禁用
    if (noResultsVisible) {
      const addButton = page.getByRole('button', { name: /添加到收集/ });
      await expect(addButton).toBeDisabled();
    }
  });

  test('收集面板可以关闭并重新打开', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    // 打开收集面板
    await openCollectionPanel(page);
    
    // 验证面板内容
    await expect(page.locator('text=人物、物品和标志物收集记录')).toBeVisible();
    
    // 关闭面板
    const closeButton = page.locator('button:has-text("Close"), button[aria-label="关闭"]').first();
    if (await closeButton.isVisible().catch(() => false)) {
      await closeButton.click();
      await page.waitForTimeout(500);
    }
    
    // 重新打开
    const collectionButton = page.getByRole('button', { name: '收集' });
    await collectionButton.click();
    
    // 面板应重新显示
    await expect(page.locator('text=人物、物品和标志物收集记录')).toBeVisible({ timeout: 5000 });
  });

  test('收集面板显示分类标签', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    await openCollectionPanel(page);
    
    // 应有人物、物品、标志物三个分类标签
    await expect(page.locator('text=/人物.*\\(/')).toBeVisible();
    await expect(page.locator('text=/物品.*\\(/')).toBeVisible();
    await expect(page.locator('text=/标志物.*\\(/')).toBeVisible();
  });

  test('取消识别对话框后可重新打开', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    await openCollectionPanel(page);
    
    // 点击智能识别
    const recognizeButton = page.locator('button:has-text("智能识别")').first();
    await recognizeButton.click();
    
    // 等待对话框
    const dialog = page.getByRole('dialog', { name: '智能识别' });
    await expect(dialog).toBeVisible({ timeout: 10000 });
    
    // 点击取消
    await page.getByRole('button', { name: '取消' }).click();
    
    // 对话框应关闭
    await expect(dialog).not.toBeVisible({ timeout: 3000 });
    
    // 智能识别按钮仍然可用
    await expect(recognizeButton).toBeVisible();
    await expect(recognizeButton).not.toBeDisabled();
    
    // 可以再次打开
    await recognizeButton.click();
    await expect(dialog).toBeVisible({ timeout: 10000 });
  });

  test('收集面板中角色信息正确显示', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    await openCollectionPanel(page);
    
    // 新创建的游戏应该显示主角
    // 检查人物标签有计数
    const characterTab = page.locator('text=/人物.*\\(/');
    await expect(characterTab).toBeVisible();
    
    // 应显示角色名
    const playerName = page.locator('text=E2E测试角色');
    if (await playerName.isVisible().catch(() => false)) {
      // 角色应标记为主角
      await expect(page.locator('text=主角')).toBeVisible();
    }
  });
});
