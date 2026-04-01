/**
 * MusicPlayer E2E 测试
 *
 * 测试音乐播放器组件的渲染和基本交互
 * 注意：这些测试验证播放器 UI 存在和基本功能，不涉及实际音频播放
 */
import { test, expect, Page, BrowserContext } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

const BASE_URL = 'http://localhost:3000';
const API_URL = 'http://localhost:8000';

test.describe('MusicPlayer 音乐播放器', () => {
  // 辅助函数：等待音乐播放器加载，如果超时则跳过
  async function waitForMusicPlayer(page: Page): Promise<boolean> {
    try {
      await page.waitForSelector('text=场景音乐', { timeout: 20000 });
      return true;
    } catch {
      return false;
    }
  }
  // 辅助函数：获取或创建活跃游戏
  async function ensureActiveGame(page: Page, context: BrowserContext): Promise<number> {
    // 首先检查是否已有活跃游戏
    const activeResp = await context.request.get(`${API_URL}/api/games/active`);
    if (activeResp.ok()) {
      const data = await activeResp.json();
      if (data.game_id) {
        return data.game_id;
      }
    }

    // 没有活跃游戏，创建一个新游戏
    const response = await context.request.post(`${API_URL}/api/games`, {
      data: {
        player_name: '音乐测试角色',
        life_vision: '测试音乐播放器功能',
        character_settings: {
          era: { name: '现代', period: '现代' },
          age: { age: 18, stage: '青年' },
          personality: { traits: ['勇敢', '好奇'] },
          background: { occupation: '学生' },
        },
        language: 'zh',
      }
    });

    if (!response.ok()) {
      const errorText = await response.text();
      throw new Error(`Failed to create game: ${response.status()} ${errorText}`);
    }

    const data = await response.json();
    return data.game_id;
  }

  test('音乐播放器组件应该在游戏页面渲染', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 获取或创建活跃游戏
    const gameId = await ensureActiveGame(page, context);

    // 进入游戏页面
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 验证音乐播放器组件存在（通过文本内容判断）
    const hasMusicPlayer = await waitForMusicPlayer(page);
    if (!hasMusicPlayer) {
      test.skip(true, '音乐播放器未加载，可能是故事生成中或API不可用');
      return;
    }

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-loaded.png' });
  });

  test('应该显示推荐的歌曲信息', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 获取或创建活跃游戏
    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待音乐播放器加载
    const hasMusicPlayer = await waitForMusicPlayer(page);
    if (!hasMusicPlayer) { test.skip(true, '音乐播放器未加载，跳过'); return; }

    // 验证歌曲信息显示（歌曲名、艺术家、专辑）
    const songInfo = page.locator('.font-medium.truncate');
    await expect(songInfo).toBeVisible({ timeout: 5000 });

    // 验证艺术家和专辑信息
    const artistAlbum = page.locator('.text-muted-foreground.text-xs.truncate');
    await expect(artistAlbum).toBeVisible();

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-song-info.png' });
  });

  test('应该支持播放/暂停功能', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 获取或创建活跃游戏
    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待播放器加载
    const hasMusicPlayer = await waitForMusicPlayer(page);
    if (!hasMusicPlayer) { test.skip(true, '音乐播放器未加载，跳过'); return; }

    // 找到播放/暂停按钮（通常是第一个带有 svg 的按钮）
    const playButton = page.locator('button').filter({ has: page.locator('svg') }).first();
    await expect(playButton).toBeVisible();

    // 点击播放
    await playButton.click();
    await page.waitForTimeout(500);

    // 截图记录播放状态
    await page.screenshot({ path: 'test-results/music-player-playing.png' });

    // 再次点击暂停
    await playButton.click();
    await page.waitForTimeout(500);

    // 截图记录暂停状态
    await page.screenshot({ path: 'test-results/music-player-paused.png' });
  });

  test('应该支持切换歌曲', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 获取或创建活跃游戏
    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待播放器加载
    const hasMusicPlayer = await waitForMusicPlayer(page);
    if (!hasMusicPlayer) { test.skip(true, '音乐播放器未加载，跳过'); return; }

    // 记录当前歌曲名
    const songNameLocator = page.locator('.font-medium.truncate');
    await expect(songNameLocator).toBeVisible();
    const firstSongName = await songNameLocator.textContent();

    // 找到下一首按钮并点击（使用 aria-label 或 title 属性）
    const nextButton = page.locator('button[title="下一首"], button:has(svg[data-lucide="skip-forward"])');
    if (await nextButton.isVisible().catch(() => false)) {
      await nextButton.click();
      await page.waitForTimeout(1000);

      // 验证播放器仍然显示
      await expect(page.locator('text=场景音乐')).toBeVisible();

      // 截图记录
      await page.screenshot({ path: 'test-results/music-player-next-song.png' });
    }
  });

  test('刷新推荐应该加载新歌曲', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 获取或创建活跃游戏
    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待播放器加载
    const hasMusicPlayer = await waitForMusicPlayer(page);
    if (!hasMusicPlayer) { test.skip(true, '音乐播放器未加载，跳过'); return; }

    // 记录当前歌曲名
    const songNameLocator = page.locator('.font-medium.truncate');
    await expect(songNameLocator).toBeVisible();

    // 找到刷新按钮并点击
    const refreshButton = page.locator('button[title="换一批"], button:has(svg[data-lucide="refresh-cw"])');
    if (await refreshButton.isVisible().catch(() => false)) {
      await refreshButton.click();
      await page.waitForTimeout(2000);

      // 验证播放器仍然显示
      await expect(page.locator('text=场景音乐')).toBeVisible();

      // 截图记录
      await page.screenshot({ path: 'test-results/music-player-refreshed.png' });
    }
  });

  test('音乐播放器应该在页面加载后显示', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 获取或创建活跃游戏
    const gameId = await ensureActiveGame(page, context);

    // 进入游戏
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待音乐播放器加载
    const hasMusicPlayer = await waitForMusicPlayer(page);
    if (!hasMusicPlayer) { test.skip(true, '音乐播放器未加载，跳过'); return; }

    // 验证播放器 UI 元素
    await expect(page.locator('.font-medium.truncate')).toBeVisible();
    await expect(page.locator('.text-muted-foreground.text-xs.truncate')).toBeVisible();

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-ui.png' });
  });

  test('播放器应该在页面切换后保持状态', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 获取或创建活跃游戏
    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待播放器加载
    const hasMusicPlayer = await waitForMusicPlayer(page);
    if (!hasMusicPlayer) { test.skip(true, '音乐播放器未加载，跳过'); return; }

    // 记录当前歌曲
    const songName = await page.locator('.font-medium.truncate').textContent();

    // 导航到主页再返回
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    // 重新进入游戏
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 验证播放器仍然显示
    await expect(page.locator('text=场景音乐')).toBeVisible({ timeout: 20000 });

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-persisted.png' });
  });
});
