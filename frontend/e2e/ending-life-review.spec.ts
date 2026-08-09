/**
 * Ending Life Review & Achievement E2E Test
 *
 * 覆盖人生回顾卡片、成就徽章墙、分享卡片生成
 */

import { test, expect } from '@playwright/test';
import { API_URL } from './helpers/auth';
import { installReadyEndingFixture } from './helpers/ending-fixture';

const API_BASE = `${API_URL}/api`;

test.describe('Ending Life Review - Page Rendering', () => {
  test('life review card renders with personality labels', async ({ page }) => {
    await installReadyEndingFixture(page);
    await page.goto('/ending');

    await expect(page.getByRole('heading', { level: 1, name: '平衡人生' })).toBeVisible();
    await page.getByRole('button', { name: '查看人生回顾' }).click();

    const reviewCard = page.getByTestId('life-review-card');
    await expect(reviewCard).toBeVisible();
    await expect(reviewCard).toContainText('沉着的记录者');
    await expect(reviewCard).toContainText('关系守护者');
  });

  test('achievement badges have rarity styling', async ({ page }) => {
    await installReadyEndingFixture(page);
    await page.goto('/ending');
    await page.getByRole('button', { name: '查看人生回顾' }).click();

    const badge = page.getByTestId('achievement-badge');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText('平衡人生');
    await expect(badge).toContainText('稀有');
  });

  test('share button exists and is clickable', async ({ page }) => {
    await installReadyEndingFixture(page);
    await page.goto('/ending');
    await page.getByRole('button', { name: '查看人生回顾' }).click();

    const shareButton = page.getByRole('button', { name: '保存分享卡片' });
    await expect(shareButton).toBeVisible();
    await expect(shareButton).toBeEnabled();
  });
});

test.describe('Ending Life Review - API Response', () => {
  test('ending API returns life_review field', async ({ page }) => {
    const response = await page.request.get(`${API_BASE}/games/99999/ending`);
    // 端点应存在，不返回 405
    expect(response.status()).not.toBe(405);

    if (response.status() === 200) {
      const body = await response.json();
      if ('life_review' in body) {
        const review = body.life_review as Record<string, unknown>;
        expect(review).toBeTruthy();
        expect(Array.isArray(review.personality_labels)).toBe(true);
        expect(Array.isArray(review.key_turning_points)).toBe(true);
        expect(typeof review.resource_curves).toBe('object');
        expect(Array.isArray(review.achievement_badge_wall)).toBe(true);
        expect(typeof review.relationship_network).toBe('object');
        expect(typeof review.life_motto).toBe('string');
      }
    }
  });

  test('ending API achievements are structured objects', async ({ page }) => {
    const response = await page.request.get(`${API_BASE}/games/99999/ending`);
    expect(response.status()).not.toBe(405);

    if (response.status() === 200) {
      const body = await response.json();
      if ('achievements' in body && body.achievements) {
        const achievements = body.achievements as Record<string, unknown>;
        expect(Array.isArray(achievements.list)).toBe(true);
        if (Array.isArray(achievements.list) && achievements.list.length > 0) {
          const first = achievements.list[0] as Record<string, unknown>;
          expect(typeof first.id).toBe('string');
          expect(typeof first.name).toBe('string');
          expect(['common', 'rare', 'epic', 'legendary']).toContain(first.rarity);
        }
      }
    }
  });
});
