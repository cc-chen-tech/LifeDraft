/**
 * 异步实体识别 E2E 测试
 * 
 * 测试用户交互流程：
 * 1. 用户点击智能识别 -> 显示识别结果对话框
 * 2. 识别结果展示（有结果 / 无结果）
 * 3. 取消识别对话框
 * 4. 收集面板基本交互
 */

import { test, expect, type Locator, type Page } from '@playwright/test';
import { ensureActiveGame } from './helpers/auth';
import { openPlayTools } from './helpers/play-tools';

function collectionDialog(page: Page) {
  return page.getByRole('dialog', { name: '收集', exact: true });
}

// 从当前 viewport 的真实工具入口打开收集面板。
async function openCollectionPanel(page: Page): Promise<Locator> {
  const tools = await openPlayTools(page);
  await tools.getByRole('button', { name: '打开收集', exact: true }).click();

  const dialog = collectionDialog(page);
  await expect(dialog).toBeVisible({ timeout: 5000 });
  await expect(
    dialog.getByText('人物、物品和标志物收集记录', { exact: true })
  ).toBeVisible({ timeout: 5000 });
  return dialog;
}

async function closeCollectionPanel(page: Page) {
  const dialog = collectionDialog(page);
  await dialog.getByRole('button', { name: '关闭收集', exact: true }).click();
  await expect(dialog).not.toBeVisible({ timeout: 3000 });
}

test.describe('异步实体识别功能', () => {
  test.beforeEach(async ({ page, context }) => {
    // 登录并确保有活跃游戏（同一会话）
    await ensureActiveGame(page, context, { player_name: 'E2E测试角色' });
  });

  test('用户点击智能识别 -> 显示识别对话框 -> 展示识别结果', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    // 打开收集面板
    const collection = await openCollectionPanel(page);
    
    // 点击智能识别按钮
    const recognizeButton = collection.getByRole('button', { name: '智能识别', exact: true });
    await expect(recognizeButton).toBeVisible();
    await recognizeButton.click();
    
    // 验证识别对话框显示
    const dialog = page.getByRole('dialog', { name: '智能识别' });
    await expect(dialog).toBeVisible({ timeout: 10000 });
  });

  test('新游戏识别结果为空时显示提示', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    const collection = await openCollectionPanel(page);
    
    // 点击智能识别
    await collection.getByRole('button', { name: '智能识别', exact: true }).click();
    
    // 等待识别对话框出现
    const dialog = page.getByRole('dialog', { name: '智能识别' });
    await expect(dialog).toBeVisible({ timeout: 10000 });
    
    // 新游戏故事很短，应显示"未识别到新的实体"或显示识别结果
    const noResultsText = dialog.locator('text=未识别到新的实体');
    const resultsArea = dialog.locator('text=从历史故事中识别');
    
    // 至少一个应该可见
    const hasNoResults = await noResultsText.isVisible().catch(() => false);
    const hasDescription = await resultsArea.isVisible().catch(() => false);
    expect(hasNoResults || hasDescription).toBeTruthy();
    
    // 如果无结果，添加按钮应被禁用或不存在
    if (hasNoResults) {
      const addButton = dialog.getByRole('button', { name: /添加到收集/ });
      const isButtonVisible = await addButton.isVisible().catch(() => false);
      if (isButtonVisible) {
        const isEnabled = await addButton.isEnabled().catch(() => true);
        expect(isEnabled).toBe(false);
      }
    }
  });

  test('收集面板可以关闭并重新打开', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    // 打开收集面板
    let collection = await openCollectionPanel(page);
    
    // 验证面板内容
    await expect(
      collection.getByText('人物、物品和标志物收集记录', { exact: true })
    ).toBeVisible();
    
    // 关闭面板
    await closeCollectionPanel(page);
    
    // 重新打开
    collection = await openCollectionPanel(page);
    
    // 面板应重新显示
    await expect(
      collection.getByText('人物、物品和标志物收集记录', { exact: true })
    ).toBeVisible({ timeout: 5000 });
  });

  test('收集面板显示分类标签', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    const collection = await openCollectionPanel(page);
    
    // 应有人物、物品、标志物三个分类标签
    await expect(collection.getByRole('tab', { name: /人物.*\(/ })).toBeVisible();
    await expect(collection.getByRole('tab', { name: /物品.*\(/ })).toBeVisible();
    await expect(collection.getByRole('tab', { name: /标志物.*\(/ })).toBeVisible();
  });

  test('取消识别对话框后可重新打开', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    
    const collection = await openCollectionPanel(page);
    
    // 点击智能识别
    const recognizeButton = collection.getByRole('button', { name: '智能识别', exact: true });
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
    
    const collectionDialog = await openCollectionPanel(page);
    
    // 新创建的游戏应该显示主角
    // 检查人物标签有计数
    const characterTab = collectionDialog.getByRole('tab', { name: /人物.*\(/ });
    await expect(characterTab).toBeVisible();

    const playerCard = collectionDialog.getByRole('button', {
      name: '查看人物：E2E测试角色',
      exact: true,
    });
    await expect(playerCard).toBeVisible();
    await expect(playerCard.getByText('主角', { exact: true })).toBeVisible();
  });
});
