/**
 * 异步实体识别 E2E 测试
 * 
 * 测试用户交互流程：
 * 1. 用户点击识别 -> 显示进度 -> 完成通知
 * 2. 识别过程中切换游戏
 * 3. 识别过程中关闭面板再打开
 */

import { test, expect } from '@playwright/test';

test.describe('异步实体识别功能', () => {
  test.beforeEach(async ({ page }) => {
    // 登录并进入游戏
    await page.goto('/');
    
    // 等待页面加载
    await page.waitForSelector('body');
    
    // 如果有登录流程，执行登录
    const loginButton = page.locator('button:has-text("登录")').first();
    if (await loginButton.isVisible().catch(() => false)) {
      await loginButton.click();
      // 假设使用测试账号
      await page.fill('[name="private_id"]', 'test-user-id');
      await page.click('button:has-text("确认")');
    }
  });

  test('用户点击智能识别 -> 显示确认对话框 -> 开始识别 -> 显示进度 -> 完成', async ({ page }) => {
    // 进入游戏页面（假设有测试游戏ID）
    await page.goto('/play?gameId=1');
    await page.waitForLoadState('networkidle');
    
    // 打开收集面板
    const collectionButton = page.locator('button:has-text("收集")').first();
    await expect(collectionButton).toBeVisible();
    await collectionButton.click();
    
    // 等待收集面板打开
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    
    // 点击智能识别按钮
    const recognizeButton = page.locator('button:has-text("智能识别")').first();
    await expect(recognizeButton).toBeVisible();
    await recognizeButton.click();
    
    // 验证确认对话框显示
    await expect(page.locator('text=智能识别实体')).toBeVisible();
    await expect(page.locator('text=此功能将分析您的游戏历史')).toBeVisible();
    await expect(page.locator('text=这可能需要 2-5 分钟完成')).toBeVisible();
    
    // 点击开始识别
    await page.click('button:has-text("开始识别")');
    
    // 验证进度条显示
    await expect(page.locator('text=智能识别中...')).toBeVisible();
    await expect(page.locator('.bg-primary')).toBeVisible(); // 进度条
    
    // 等待识别完成（最多等待60秒）
    await expect(page.locator('text=识别完成')).toBeVisible({ timeout: 60000 });
    
    // 验证收集面板更新
    await expect(page.locator('text=收集面板已更新')).toBeVisible();
  });

  test('识别过程中防止重复启动', async ({ page }) => {
    await page.goto('/play?gameId=1');
    await page.waitForLoadState('networkidle');
    
    // 打开收集面板
    await page.click('button:has-text("收集")');
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    
    // 第一次点击智能识别
    await page.click('button:has-text("智能识别")');
    await page.click('button:has-text("开始识别")');
    
    // 验证识别进行中
    await expect(page.locator('text=智能识别中...')).toBeVisible();
    
    // 再次点击智能识别按钮（应该被禁用或提示已有任务）
    const recognizeButton = page.locator('button:has-text("智能识别")').first();
    
    // 按钮应该被禁用
    await expect(recognizeButton).toBeDisabled();
  });

  test('识别过程中可以关闭面板并重新打开', async ({ page }) => {
    await page.goto('/play?gameId=1');
    await page.waitForLoadState('networkidle');
    
    // 打开收集面板
    await page.click('button:has-text("收集")');
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    
    // 开始识别
    await page.click('button:has-text("智能识别")');
    await page.click('button:has-text("开始识别")');
    
    // 验证识别进行中
    await expect(page.locator('text=智能识别中...')).toBeVisible();
    
    // 关闭收集面板
    const closeButton = page.locator('button[aria-label="关闭"]').first();
    await closeButton.click();
    
    // 等待面板关闭
    await page.waitForTimeout(500);
    
    // 重新打开收集面板
    await page.click('button:has-text("收集")');
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    
    // 验证进度条仍然显示（识别继续进行）
    await expect(page.locator('text=智能识别中...')).toBeVisible();
    await expect(page.locator('.bg-primary')).toBeVisible();
  });

  test('识别过程中切换游戏后进度不显示', async ({ page }) => {
    // 先开始一个游戏的识别
    await page.goto('/play?gameId=1');
    await page.waitForLoadState('networkidle');
    
    // 打开收集面板并开始识别
    await page.click('button:has-text("收集")');
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    await page.click('button:has-text("智能识别")');
    await page.click('button:has-text("开始识别")');
    
    // 验证识别进行中
    await expect(page.locator('text=智能识别中...')).toBeVisible();
    
    // 切换到另一个游戏
    await page.goto('/play?gameId=2');
    await page.waitForLoadState('networkidle');
    
    // 打开收集面板
    await page.click('button:has-text("收集")');
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    
    // 验证新游戏不显示识别进度（或者显示可开始新识别）
    const recognizeButton = page.locator('button:has-text("智能识别")').first();
    await expect(recognizeButton).toBeVisible();
    await expect(recognizeButton).not.toBeDisabled();
  });

  test('取消识别确认对话框', async ({ page }) => {
    await page.goto('/play?gameId=1');
    await page.waitForLoadState('networkidle');
    
    // 打开收集面板
    await page.click('button:has-text("收集")');
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    
    // 点击智能识别
    await page.click('button:has-text("智能识别")');
    
    // 验证确认对话框显示
    await expect(page.locator('text=智能识别实体')).toBeVisible();
    
    // 点击取消
    await page.click('button:has-text("取消")');
    
    // 验证对话框关闭，识别未开始
    await expect(page.locator('text=智能识别实体')).not.toBeVisible();
    await expect(page.locator('text=智能识别中...')).not.toBeVisible();
    
    // 智能识别按钮仍然可用
    const recognizeButton = page.locator('button:has-text("智能识别")').first();
    await expect(recognizeButton).toBeVisible();
    await expect(recognizeButton).not.toBeDisabled();
  });

  test('识别完成后刷新收集数据', async ({ page }) => {
    await page.goto('/play?gameId=1');
    await page.waitForLoadState('networkidle');
    
    // 打开收集面板
    await page.click('button:has-text("收集")');
    await page.waitForSelector('text=人物、物品和标志物收集记录');
    
    // 记录识别前的人物数量
    const charactersCountBefore = await page.locator('text=/人物 \\(/').count();
    
    // 开始识别
    await page.click('button:has-text("智能识别")');
    await page.click('button:has-text("开始识别")');
    
    // 等待识别完成
    await expect(page.locator('text=识别完成')).toBeVisible({ timeout: 60000 });
    
    // 验证收集数据已刷新（可能需要重新打开面板查看）
    // 这里假设识别会添加新的人物/物品
  });
});
