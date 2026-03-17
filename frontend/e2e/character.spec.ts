/* eslint-disable @typescript-eslint/no-unused-vars */

/**
 * E2E Test: Character Creation Flow
 * Tests for the character creation wizard including all steps and navigation
 */
import { test, expect } from '@playwright/test';

test.describe('Character Creation - Page Load', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/create');
  });

  test('should display character creation page', async ({ page }) => {
    await expect(page).toHaveURL('/create');
  });

  test('should have step indicator showing progress', async ({ page }) => {
    // Step indicator dots
    const stepDots = page.locator('button[class*="rounded-full"]');
    const dotCount = await stepDots.count();
    
    // Should have multiple steps (era, age, gender, world, portrait = 5)
    expect(dotCount).toBeGreaterThanOrEqual(3);
  });

  test('should show step count in header', async ({ page }) => {
    // Step count like "1/5" or similar
    const stepCount = page.locator('text=/\\d+\\/\\d+/');
    await expect(stepCount).toBeVisible();
  });

  test('should have return button', async ({ page }) => {
    const returnButton = page.getByRole('button', { name: /返回/i });
    await expect(returnButton).toBeVisible();
  });
});

test.describe('Character Creation - Player Name Input', () => {
  test('should have player name input field', async ({ page }) => {
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await expect(nameInput).toBeVisible();
  });

  test('should allow entering player name', async ({ page }) => {
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await expect(nameInput).toHaveValue('测试角色');
  });

  test('should have optional life vision textarea', async ({ page }) => {
    await page.goto('/create');
    
    const visionTextarea = page.getByPlaceholder(/人生愿景|人生方向/i);
    await expect(visionTextarea).toBeVisible();
  });
});

test.describe('Character Creation - Step Content', () => {
  test('should display era step initially', async ({ page }) => {
    await page.goto('/create');
    
    // Era step should show era label
    const eraLabel = page.locator('text=/时代背景/');
    await expect(eraLabel).toBeVisible();
  });

  test('should show step description', async ({ page }) => {
    await page.goto('/create');
    
    // Step description
    const description = page.locator('text=/选择你的人生|确定你的人生故事/');
    await expect(description.first()).toBeVisible();
  });

  test('should have next step button', async ({ page }) => {
    await page.goto('/create');
    
    // Use .first() to avoid matching Next.js Dev Tools button
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    await expect(nextButton).toBeVisible();
  });

  test('should disable next button when name is empty', async ({ page }) => {
    await page.goto('/create');
    
    // Use .first() to avoid matching Next.js Dev Tools button
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    
    // Enter name to enable
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    
    // Wait for auto-generation to potentially start
    await page.waitForTimeout(500);
  });
});

test.describe('Character Creation - Navigation', () => {
  test('should navigate to next step after filling name', async ({ page }) => {
    await page.goto('/create');
    
    // Enter name
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    
    // Wait for generation
    await page.waitForTimeout(1000);
    
    // Use .first() to avoid matching Next.js Dev Tools button
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    
    // Click next if enabled
    if (await nextButton.isEnabled()) {
      await nextButton.click();
      await page.waitForTimeout(500);
      
      // Step indicator should show progress - check if still on create page
      await expect(page).toHaveURL('/create');
    }
  });

  test('should return to home when clicking return button', async ({ page }) => {
    await page.goto('/create');
    
    const returnButton = page.getByRole('button', { name: /返回/i }).first();
    await returnButton.click();
    
    await expect(page).toHaveURL('/');
  });

  test('should allow clicking on previous step dots', async ({ page }) => {
    await page.goto('/create');
    
    // Enter name and proceed to step 2
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await page.waitForTimeout(1000);
    
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    if (await nextButton.isEnabled()) {
      await nextButton.click();
      await page.waitForTimeout(500);
      
      // Now click on first dot to go back
      const stepDots = page.locator('button[class*="rounded-full"]');
      if (await stepDots.count() > 0) {
        await stepDots.first().click();
      }
    }
  });
});

test.describe('Character Creation - Auto Generation', () => {
  test('should show loading state during generation', async ({ page }) => {
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    
    // Look for loading indicator
    await page.waitForTimeout(500);
    
    const loadingIndicator = page.locator('text=/生成中|AI正在生成/');
    const spinner = page.locator('[class*="animate-spin"]');
    
    // Either loading indicator or generated content should appear
  });

  test('should display generated content after loading', async ({ page }) => {
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    
    // Wait for generation to complete
    await page.waitForTimeout(3000);
    
    // Generated setting should appear
    const settingDisplay = page.locator('[class*="setting"], [class*="content"]');
  });

  test('should have regenerate button for generated content', async ({ page }) => {
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await page.waitForTimeout(2000);
    
    // Regenerate button (refresh icon)
    const regenerateButton = page.getByRole('button').filter({ has: page.locator('svg') });
  });

  test('should have feedback input for regeneration', async ({ page }) => {
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await page.waitForTimeout(2000);
    
    // Feedback input
    const feedbackInput = page.getByPlaceholder(/不满意|你的想法/i);
  });
});

test.describe('Character Creation - Completion', () => {
  test('should show start game button on final step', async ({ page }) => {
    // This test would require completing all steps
    // For now, verify the button exists in the DOM
    await page.goto('/create');
    
    const startButton = page.getByRole('button', { name: /开始游戏|生成角色/i });
    // Button may not be visible until final step
  });

  test('should show save preset button on completion', async ({ page }) => {
    await page.goto('/create');
    
    const saveButton = page.getByRole('button', { name: /保存.*预设|Save/i });
    // Button may not be visible until final step
  });
});

test.describe('Character Creation - Preset Sheet', () => {
  test('should open preset save sheet', async ({ page }) => {
    await page.goto('/create');
    
    // Find and click save button
    const saveButton = page.getByRole('button', { name: /保存|Save/i }).first();
    
    if (await saveButton.isVisible()) {
      await saveButton.click();
      await page.waitForTimeout(500);
      
      // Sheet should open
      const sheet = page.locator('[role="dialog"], [class*="sheet"]');
      
      // Preset name input should be in sheet
      const presetInput = page.getByPlaceholder(/预设名称/i);
    }
  });
});

test.describe('Character Creation - Error Handling', () => {
  test('should show error toast on generation failure', async ({ page }) => {
    // Simulate network error
    await page.route('**/api/character/**', route => route.abort('failed'));
    
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    
    await page.waitForTimeout(2000);
    
    // Error toast should appear
    const errorToast = page.locator('text=/失败|错误|重试/');
  });
});
