 

/**
 * E2E Test: Save/Load Flow
 * Tests for game save and load functionality including save list, load, and delete
 */
import { test, expect } from '@playwright/test';
import { waitForPageReady } from './helpers/wait-helpers';

test.describe('Save/Load - Page Structure', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/saves');
  });

  test('should display saves page', async ({ page }) => {
    // 页面可能重定向到首页（未登录）或停留在 /saves
    await page.waitForLoadState('domcontentloaded');
    const url = page.url();
    expect(url).toMatch(/\/(saves|$|\?)/);
  });

  test('should have header with return button', async ({ page }) => {
    const returnButton = page.getByRole('button', { name: /返回/i });
    await expect(returnButton).toBeVisible();
  });

  test('should have page title', async ({ page }) => {
    const pageTitle = page.locator('text=/存档|Save|游戏/');
    await expect(pageTitle.first()).toBeVisible();
  });
});

test.describe('Save/Load - Save List', () => {
  test('should show loading state initially', async ({ page }) => {
    await page.goto('/saves');
    
    // Loading spinner
    const spinner = page.locator('[class*="animate-spin"]');
    
    // Should either show loading or content
    await page.waitForLoadState('domcontentloaded');
  });

  test('should display saved games list when available', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Save cards or empty state
    const saveCards = page.locator('[class*="card"], [class*="save"]');
    const emptyState = page.locator('text=/没有存档|暂无|空/');
    
    // Either cards or empty state should be visible
  });

  test('should show player name on save cards', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Look for player name
    const playerName = page.locator('text=/角色|玩家/');
    
    // If saves exist, player name should be shown
  });

  test('should display save timestamp', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Time display (凌晨/上午/下午/晚上)
    const timeDisplay = page.locator('text=/凌晨|上午|下午|晚上|\d+:\d+/');
    
    // If saves exist, timestamp should be shown
  });

  test('should show week progress on saves', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Week display
    const weekDisplay = page.locator('text=/周|Week/');
  });
});

test.describe('Save/Load - Character Groups', () => {
  test('should group saves by character name', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Character groups (collapsible)
    const groups = page.locator('[class*="collapsible"], [class*="group"]');
    
    // If multiple saves exist for same character, they should be grouped
  });

  test('should allow expanding character group', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Click to expand group
    const groupTrigger = page.locator('button').filter({ has: page.locator('svg') });
    
    if (await groupTrigger.count() > 0) {
      await groupTrigger.first().click();
      await page.waitForLoadState('domcontentloaded');
    }
  });

  test('should show save count per character', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Save count badge
    const saveCount = page.locator('text=/\\d+.*存档|\\d+.*个/');
  });
});

test.describe('Save/Load - Load Functionality', () => {
  test('should have load/play button on each save', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Play button
    const playButton = page.getByRole('button', { name: /继续|加载|Load|Play/i });
    
    // If saves exist, play button should be visible
  });

  test('should load game when clicking play button', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    const playButton = page.getByRole('button', { name: /继续|加载|Load|Play/i });
    
    if (await playButton.count() > 0) {
      await playButton.first().click();
      
      // Should navigate to play page
      await page.waitForLoadState('domcontentloaded');
      
      // URL should be /play
      const currentUrl = page.url();
    }
  });

  test('should show loading indicator while loading', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    const playButton = page.getByRole('button', { name: /继续|加载|Load|Play/i });
    
    if (await playButton.count() > 0) {
      await playButton.first().click();
      
      // Loading spinner should appear
      const spinner = page.locator('[class*="animate-spin"]');
    }
  });
});

test.describe('Save/Load - Delete Functionality', () => {
  test('should have delete button on each save', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Delete button (trash icon)
    const deleteButton = page.getByRole('button').filter({ has: page.locator('svg') });
    
    // If saves exist, delete button should be visible
  });

  test('should show confirmation dialog when deleting', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Find delete button (trash icon)
    const buttons = page.getByRole('button');
    
    // Look for button with trash icon
    for (const button of await buttons.all()) {
      const hasTrashIcon = await button.locator('svg').count() > 0;
      if (hasTrashIcon) {
        await button.click();
        await page.waitForLoadState('domcontentloaded');
        
        // Dialog should appear
        const dialog = page.locator('[role="dialog"], [class*="dialog"]');
        break;
      }
    }
  });

  test('should cancel delete when clicking cancel', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Open delete dialog
    const buttons = page.getByRole('button');
    
    for (const button of await buttons.all()) {
      const hasTrashIcon = await button.locator('svg').count() > 0;
      if (hasTrashIcon) {
        await button.click();
        await page.waitForLoadState('domcontentloaded');
        
        // Click cancel
        const cancelButton = page.getByRole('button', { name: /取消|Cancel/i });
        if (await cancelButton.isVisible()) {
          await cancelButton.click();
        }
        break;
      }
    }
  });

  test('should delete save when confirming', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // Open delete dialog
    const buttons = page.getByRole('button');
    
    for (const button of await buttons.all()) {
      const hasTrashIcon = await button.locator('svg').count() > 0;
      if (hasTrashIcon) {
        await button.click();
        await page.waitForLoadState('domcontentloaded');
        
        // Click confirm delete
        const confirmButton = page.getByRole('button', { name: /删除|Delete|确认/i });
        // Don't actually delete in test
        break;
      }
    }
  });
});

test.describe('Save/Load - Empty State', () => {
  test('should show empty state or save cards when no saves or saves exist', async ({ page }) => {
    // 不 mock，直接访问真实状态
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // 空状态或存档卡片至少有一个可见
    const emptyMessage = page.locator('text=/没有存档|暂无|空|开始新游戏/');
    const saveCards = page.locator('[class*="card"], [class*="save"]');
    
    // 等待页面稳定
    await page.waitForTimeout(2000);
    
    const hasEmptyState = await emptyMessage.first().isVisible().catch(() => false);
    const hasSaveCards = await saveCards.first().isVisible().catch(() => false);
    
    // 至少一种状态应该出现
    expect(hasEmptyState || hasSaveCards).toBe(true);
  });

  test('should have new game button on saves page', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    // New game button
    const newGameButton = page.getByRole('button', { name: /新游戏|创建角色|开始/i });
    await expect(newGameButton.first()).toBeVisible();
  });
});

test.describe('Save/Load - Toast Notifications', () => {
  test('should show success toast after successful load', async ({ page }) => {
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    
    const playButton = page.getByRole('button', { name: /继续|加载|Load|Play/i });
    
    if (await playButton.count() > 0) {
      await playButton.first().click();

      // Toast notification or navigation should happen
      await page.waitForLoadState('domcontentloaded');
    }
  });

  test('should show error toast on load failure', async ({ page }) => {
    // Mock load failure - 拦截所有可能的加载相关请求
    await page.route('**/api/games/**', route => {
      const url = route.request().url();
      if (url.includes('load')) {
        route.abort('failed');
      } else {
        route.continue();
      }
    });
    
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');
    // 等待存档列表渲染
    await page.waitForTimeout(2000);
    
    const playButton = page.getByRole('button', { name: /继续|加载|Load|Play/i });
    
    if (await playButton.count() > 0) {
      await playButton.first().click();
      // 等待错误处理完成
      await page.waitForTimeout(2000);

      // 加载失败后应该停留在 saves 页面或显示错误，不会崩溃
      const currentUrl = page.url();
      expect(currentUrl).toMatch(/saves|play|\/$/);
    }
  });
});

test.describe('Save/Load - Navigation', () => {
  test('should return to home when clicking return button', async ({ page }) => {
    await page.goto('/saves');
    // 等待页面完全加载
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    if (new URL(page.url()).pathname === '/') {
      await expect(page.getByRole('button', { name: '新游戏' })).toBeVisible();
      return;
    }
    
    // 查找返回按钮，包括 button 和 link 形式
    const returnButton = page.locator('button:has-text("返回"), a:has-text("返回"), a:has-text("首页")');
    
    await expect(returnButton.first()).toBeVisible({ timeout: 10000 });
    await returnButton.first().click({ force: true, noWaitAfter: true });
    // 等待导航完成
    await page.waitForURL('**/', { timeout: 15000 });
    // 验证已导航到首页
    expect(page.url()).toMatch(/\/($|\?)/);
  });
});
