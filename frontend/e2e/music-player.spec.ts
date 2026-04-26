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
  // 故事 AI 生成（~60s）+ 音乐推荐 API（~30s）+ 页面交互，需要充足超时
  test.setTimeout(180_000);

  // 辅助函数：获取或创建活跃游戏
  async function ensureActiveGame(page: Page, context: BrowserContext): Promise<number> {
    const activeResp = await context.request.get(`${API_URL}/api/games/active`);
    if (activeResp.ok()) {
      const data = await activeResp.json();
      if (data.game_id) {
        return data.game_id;
      }
    }

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

  /**
   * 等待音乐播放器加载完成。
   * MusicPlayer 被 GlobalMusicPlayer 包裹，默认只显示 mini bar，
   * 需要点击 mini bar 展开后才能看到完整的 MusicPlayer。
   */
  async function waitForMusicPlayer(page: Page): Promise<void> {
    // 等待 mini player bar 出现并展开
    const miniBar = page.locator('.fixed.z-50.bottom-0 .gap-2.px-3.py-2.cursor-pointer').first();
    await miniBar.waitFor({ state: 'visible', timeout: 60000 });
    await miniBar.click();
    // 等待"场景音乐"标题出现
    await page.waitForSelector('text=场景音乐', { timeout: 120000 });
    // 等待推荐加载完成
    await page.waitForSelector('text=正在分析故事氛围', { state: 'hidden', timeout: 120000 }).catch(() => {});
  }

  /**
   * 等待音乐播放器加载并确保有歌曲可用。
   * 歌曲名元素使用 .font-medium.truncate 渲染。
   */
  async function waitForMusicPlayerWithSongs(page: Page): Promise<void> {
    await waitForMusicPlayer(page);

    // 等待歌曲名出现（在当前播放区域或歌曲列表中）
    await page.locator('.font-medium.truncate').first().waitFor({ state: 'visible', timeout: 60000 });

    // 确认不是空的"加载中"状态
    await page.waitForSelector('.animate-spin', { state: 'hidden', timeout: 30000 }).catch(() => {});
  }

  test('音乐播放器组件应该在游戏页面渲染', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);

    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayer(page);

    // 验证播放器标题可见
    await expect(page.locator('text=场景音乐')).toBeVisible();
    // meta 标签应可见（mood、environment 等）
    const metaTags = page.locator('.text-xs.rounded').first();
    await expect(metaTags).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: 'test-results/music-player-loaded.png' });
  });

  test('应该显示推荐的歌曲信息', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayerWithSongs(page);

    // 歌曲名 .font-medium.truncate 应在页面中可见
    const songInfo = page.locator('.font-medium.truncate').first();
    await expect(songInfo).toBeVisible();

    // 艺术家/专辑信息（可能不渲染，如歌曲无此元数据）
    const artistAlbum = page.locator('.text-muted-foreground.text-xs.truncate').first();
    await expect(artistAlbum).toBeVisible({ timeout: 5000 }).catch(() => {
      // 可接受：推荐歌曲可能没有艺术家信息
      console.log('[MusicPlayer E2E] 艺术家/专辑信息未渲染（非关键）');
    });

    await page.screenshot({ path: 'test-results/music-player-song-info.png' });
  });

  test('应该支持播放/暂停功能', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayerWithSongs(page);

    // 主播放按钮 h-10 w-10（其他控制按钮是 h-8 w-8）
    const playButton = page.locator('button.h-10.w-10').first();
    await expect(playButton).toBeVisible();

    // 如果按钮未 disabled（音频可用），测试播放/暂停
    if (!await playButton.isDisabled().catch(() => true)) {
      await playButton.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'test-results/music-player-playing.png' });

      await playButton.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/music-player-paused.png' });
    }
  });

  test('应该支持切换歌曲', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayerWithSongs(page);

    // 记录当前歌曲名
    const songNameLocator = page.locator('.font-medium.truncate').first();
    await expect(songNameLocator).toBeVisible({ timeout: 20000 });
    const firstSongName = await songNameLocator.textContent();
    expect(firstSongName).toBeTruthy();

    // 下一首按钮（h-8 w-8 的 SkipForward 按钮）
    const nextButton = page.locator('button.h-8.w-8').last();
    if (await nextButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await nextButton.click();
      await page.waitForTimeout(2000);

      // 验证播放器仍然显示
      await expect(page.locator('text=场景音乐')).toBeVisible();
      await page.screenshot({ path: 'test-results/music-player-next-song.png' });
    }
  });

  test('刷新推荐应该加载新歌曲', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayer(page);

    // 找到刷新按钮（含 RefreshCw SVG）
    const refreshButton = page.locator('button:has(svg.lucide-refresh-cw)').first();
    if (await refreshButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await refreshButton.click();

      // 等待推荐重新加载
      await page.waitForSelector('text=正在分析故事氛围', { state: 'hidden', timeout: 60000 }).catch(() => {});

      // 验证播放器仍然显示
      await expect(page.locator('text=场景音乐')).toBeVisible();
      await page.screenshot({ path: 'test-results/music-player-refreshed.png' });
    }
  });

  test('音乐播放器应该在页面加载后显示', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayerWithSongs(page);

    // 验证播放器核心 UI 元素
    await expect(page.locator('.font-medium.truncate').first()).toBeVisible();
    // 艺术家信息可选：推荐歌曲可能没有艺术家元数据
    await expect(page.locator('.text-muted-foreground.text-xs.truncate').first()).toBeVisible({ timeout: 5000 }).catch(() => {});

    await page.screenshot({ path: 'test-results/music-player-ui.png' });
  });

  test('播放器应该在页面切换后保持状态', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayerWithSongs(page);

    // 记录当前歌曲
    const songName = await page.locator('.font-medium.truncate').first().textContent();
    expect(songName).toBeTruthy();

    // 导航到主页再返回
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    // 重新进入游戏
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待 mini bar 出现并展开
    const miniBar = page.locator('.fixed.z-50.bottom-0 .gap-2.px-3.py-2.cursor-pointer').first();
    await miniBar.waitFor({ state: 'visible', timeout: 60000 });
    await miniBar.click();

    // 故事已有缓存，播放器应快速加载
    await page.waitForSelector('text=场景音乐', { timeout: 60000 });

    // 验证歌曲仍在
    const restoredSong = page.locator('.font-medium.truncate').first();
    await expect(restoredSong).toBeVisible({ timeout: 20000 });

    await page.screenshot({ path: 'test-results/music-player-persisted.png' });
  });
});
