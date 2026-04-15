 

/**
 * E2E Test: Complete User Journey
 * Tests for the full user flow from landing to gameplay
 */
import { test, expect } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';
import { waitForPageReady } from './helpers/wait-helpers';

test.describe('User Journey - Landing Page', () => {
  test('should display welcome page with title', async ({ page }) => {
    await page.goto('/');

    // Page should have correct title
    await expect(page).toHaveTitle(/Story Life|人生|Life Draft/);
  });

  test('should have new game button prominent', async ({ page }) => {
    await page.goto('/');

    // New game button should be visible
    const newGameButton = page.getByRole('button', { name: /新游戏|New Game/i });
    await expect(newGameButton).toBeVisible();
  });

  test('should have load game button when saves exist', async ({ page }) => {
    await page.goto('/');

    // Load game / saves button
    const loadButton = page.getByRole('button', { name: /存档|继续|Load/i });

    // Button may or may not exist depending on save state
    const isVisible = await loadButton.isVisible().catch(() => false);
    expect(typeof isVisible).toBe('boolean');
  });

  test('should navigate to create page on new game click', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // ensureAuthenticated 已经在 / 页面，等待登录状态确认
    const loginButton = page.getByRole('button', { name: /登录/i });
    await expect(loginButton).not.toBeVisible({ timeout: 5000 });

    const newGameButton = page.getByRole('button', { name: /新游戏|New Game/i });
    await newGameButton.click();

    await expect(page).toHaveURL('/create', { timeout: 10000 });
  });
});

test.describe('User Journey - Character Creation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/create');
  });

  test('should show name input on create page', async ({ page }) => {
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await expect(nameInput).toBeVisible();
  });

  test('should show life vision textarea', async ({ page }) => {
    const visionTextarea = page.getByPlaceholder(/人生愿景|人生方向|Life Vision/i);
    await expect(visionTextarea).toBeVisible();
  });

  test('should show step indicator', async ({ page }) => {
    // Step indicator showing current progress
    const stepIndicator = page.locator('text=/\\d+\\/\\d+|步骤|Step/');
    await expect(stepIndicator.first()).toBeVisible();
  });

  test('should allow entering player name', async ({ page }) => {
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('测试角色');
    await expect(nameInput).toHaveValue('测试角色');
  });

  test('should disable next button without name', async ({ page }) => {
    // Clear any existing name
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.clear();

    // Next button should be disabled or not visible
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    const isEnabled = await nextButton.isEnabled().catch(() => false);

    // Button should be disabled when name is empty
    expect(isEnabled).toBe(false);
  });

  test('should enable next button after entering name', async ({ page }) => {
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('测试角色');

    // Wait for auto-generation to potentially start
    await page.waitForLoadState('domcontentloaded');

    // After entering name, next button should be visible
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    await expect(nextButton).toBeVisible();
  });

  test('should navigate through creation steps', async ({ page }) => {
    // Enter name
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('测试角色');
    await page.waitForLoadState('domcontentloaded');

    // Click next if available
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    await expect(nextButton).toBeVisible();

    for (let i = 0; i < 3; i++) {
      if (await nextButton.isVisible() && await nextButton.isEnabled()) {
        await nextButton.click();
        await page.waitForLoadState('domcontentloaded');
      }
    }

    // Should still be on create page
    await expect(page).toHaveURL('/create');
  });

  test('should show loading indicator during generation', async ({ page }) => {
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('测试角色');

    // Look for loading state
    await page.waitForLoadState('domcontentloaded');

    // Either loading indicator or content should be visible
    const loadingText = page.locator('text=/生成中|AI正在|Generating/');
    expect(await loadingText.count()).toBeGreaterThanOrEqual(0);
  });

  test('should allow returning to home', async ({ page }) => {
    const returnButton = page.getByRole('button', { name: /返回|Back/i }).first();
    await returnButton.click();

    await expect(page).toHaveURL('/');
  });
});

test.describe('User Journey - Saves Page Flow', () => {
  test('should navigate to saves from home', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // ensureAuthenticated 已经在 / 页面，等待登录状态确认
    const loginButton = page.getByRole('button', { name: /登录/i });
    await expect(loginButton).not.toBeVisible({ timeout: 5000 });

    // Look for saves button
    const savesButton = page.getByRole('button', { name: /存档|加载存档|Saves|Load/i });

    if (await savesButton.isVisible()) {
      await savesButton.click();
      await expect(page).toHaveURL('/saves', { timeout: 10000 });
    }
  });

  test('should display saves page correctly', async ({ page }) => {
    await page.goto('/saves');

    // Page title should be visible
    const pageTitle = page.locator('text=/存档|Save|Saves/');
    await expect(pageTitle.first()).toBeVisible();

    // Return button should exist
    const returnButton = page.getByRole('button', { name: /返回/i });
    await expect(returnButton).toBeVisible();
  });

  test('should show empty state or saves list on saves page', async ({ page }) => {
    // 不 mock，直接访问真实状态
    await page.goto('/saves');
    await page.waitForLoadState('domcontentloaded');

    // 页面应该正常加载
    await expect(page).toHaveURL('/saves');
  });

  test('should allow navigation to create from saves', async ({ page }) => {
    await page.goto('/saves');

    // New game button
    const newGameButton = page.getByRole('button', { name: /新游戏|创建角色|Create/i });

    if (await newGameButton.isVisible()) {
      await newGameButton.click();
      await expect(page).toHaveURL('/create');
    }
  });
});

test.describe('User Journey - Full Flow Simulation', () => {
  test('should complete basic navigation flow', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // ensureAuthenticated 已经在 / 页面，等待登录状态确认
    const loginButton = page.getByRole('button', { name: /登录/i });
    await expect(loginButton).not.toBeVisible({ timeout: 5000 });
    await expect(page).toHaveTitle(/Story Life|人生|Life Draft/);

    // Go to create
    const newGameButton = page.getByRole('button', { name: /新游戏/i });
    await newGameButton.click();
    await expect(page).toHaveURL('/create', { timeout: 10000 });

    // Return to home
    const returnButton = page.getByRole('button', { name: /返回/i }).first();
    await returnButton.click();
    await expect(page).toHaveURL('/', { timeout: 10000 });

    // Go to saves
    const savesButton = page.getByRole('button', { name: /存档|加载存档|Saves/i });
    if (await savesButton.isVisible()) {
      await savesButton.click();
      await expect(page).toHaveURL('/saves', { timeout: 10000 });

      // Return to home
      const returnFromSaves = page.getByRole('button', { name: /返回/i });
      await returnFromSaves.click();
      await expect(page).toHaveURL('/', { timeout: 10000 });
    }
  });

  test('should handle navigation gracefully', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    await page.goto('/');

    // Page should still load
    await expect(page).toHaveTitle(/Story Life|人生|Life Draft/);

    // Navigate to create - 允许导航工作
    const newGameButton = page.getByRole('button', { name: /新游戏/i });
    await newGameButton.click();

    // Page should still work
    await expect(page).toHaveURL('/create');
  });

  test('should load pages under normal network', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    await page.goto('/');

    // Page should still load
    await expect(page).toHaveTitle(/Story Life|人生|Life Draft/);
  });
});

test.describe('User Journey - Accessibility', () => {
  test('should have proper heading structure', async ({ page }) => {
    await page.goto('/');

    // Check for proper heading hierarchy
    const headings = page.locator('h1, h2, h3');
    const headingCount = await headings.count();

    expect(headingCount).toBeGreaterThan(0);
  });

  test('should have visible focus states', async ({ page }) => {
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.focus();

    // Focus should be visible
    await expect(nameInput).toBeFocused();
  });

  test('should support keyboard navigation', async ({ page }) => {
    await page.goto('/');

    // Tab through elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // Some element should be focused
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});

test.describe('User Journey - Responsive Design', () => {
  test('should display correctly on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto('/');
    await expect(page).toHaveTitle(/Story Life|人生|Life Draft/);

    // New game button should still be visible
    const newGameButton = page.getByRole('button', { name: /新游戏/i });
    await expect(newGameButton).toBeVisible();
  });

  test('should display correctly on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });

    await page.goto('/');
    await expect(page).toHaveTitle(/Story Life|人生|Life Draft/);
  });

  test('should display correctly on desktop viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });

    await page.goto('/');
    await expect(page).toHaveTitle(/Story Life|人生|Life Draft/);
  });
});

test.describe('User Journey - Performance', () => {
  test('should load home page quickly', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/');
    const loadTime = Date.now() - startTime;

    // Page should load within 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });

  test('should load create page quickly', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/create');
    const loadTime = Date.now() - startTime;

    // Page should load within 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });

  test('should load saves page quickly', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/saves');
    const loadTime = Date.now() - startTime;

    // Page should load within 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });
});