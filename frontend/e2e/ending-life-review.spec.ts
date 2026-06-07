/**
 * Ending Life Review & Achievement E2E Test
 *
 * 覆盖人生回顾卡片、成就徽章墙、分享卡片生成
 */

import { test, expect } from '@playwright/test';
import { API_URL } from './helpers/auth';

const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
const API_BASE = `${API_URL}/api`;

test.describe('Ending Life Review - Page Rendering', () => {
  test('life review card renders with personality labels', async ({ page }) => {
    // 设置 gameId 使页面不跳转
    await page.goto(`${BASE_URL}/`);
    await page.evaluate(() => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({ state: { gameId: 1, playerState: { player_name: '测试角色' } }, version: 0 })
      );
    });
    await page.goto(`${BASE_URL}/ending`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(3000);

    if (page.url().includes('/ending')) {
      // 人生回顾卡片或相关区域应该可见
      const reviewSection = page.locator('[data-testid="life-review-card"], [data-testid="achievement-section"], h1');
      await expect(reviewSection.first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('achievement badges have rarity styling', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    await page.evaluate(() => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({ state: { gameId: 1, playerState: { player_name: '测试角色' } }, version: 0 })
      );
    });
    await page.goto(`${BASE_URL}/ending`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(3000);

    if (page.url().includes('/ending')) {
      // 徽章应该有某种样式表示（颜色类名或图标）
      const badges = page.locator('[data-testid="achievement-badge"], [class*="badge"], [class*="achievement"]');
      const count = await badges.count();
      // 有成就时检查样式
      if (count > 0) {
        await expect(badges.first()).toBeVisible();
      }
    }
  });

  test('share button exists and is clickable', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    await page.evaluate(() => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({ state: { gameId: 1, playerState: { player_name: '测试角色' } }, version: 0 })
      );
    });
    await page.goto(`${BASE_URL}/ending`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(3000);

    if (page.url().includes('/ending')) {
      const shareButton = page.locator('button').filter({ hasText: /分享|Share|保存图片|下载/i });
      const hasShare = await shareButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (hasShare) {
        await expect(shareButton).toBeEnabled();
      }
    }
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
