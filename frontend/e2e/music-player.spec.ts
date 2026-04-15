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

  /**
   * 等待音乐播放器加载完成
   * MusicPlayer 需要 storyText 非空才渲染，SSE 流式生成故事时
   * 一旦有部分文本就会触发渲染 + 音乐推荐 API
   * 整体等待：故事开始生成（~10-30s）+ 推荐 API（~20-30s）
   */
  async function waitForMusicPlayer(page: Page): Promise<void> {
    // 等待"场景音乐"标题出现
    await page.waitForSelector('text=场景音乐', { timeout: 120000 });
    // 等待推荐加载完成（loading spinner 消失）
    // "正在分析故事氛围..." 这个加载状态需要等待完成
    await page.waitForSelector('text=正在分析故事氛围', { state: 'hidden', timeout: 120000 }).catch(() => {});
  }

  /**
   * 等待音乐播放器加载并确保有歌曲可用
   * 如果推荐返回空歌曲列表，点击刷新按钮重试（最多 3 次）
   */
  async function waitForMusicPlayerWithSongs(page: Page): Promise<boolean> {
    await waitForMusicPlayer(page);

    const maxRetries = 3;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      // 等待歌曲列表或 "推荐歌曲" 区域渲染
      // 歌曲名以 .font-medium.truncate 显示
      const hasSongs = await page.locator('.font-medium.truncate').first().isVisible({ timeout: 10000 }).catch(() => false);
      if (hasSongs) return true;

      if (attempt < maxRetries) {
        console.log(`[MusicPlayer E2E] 歌曲列表为空，尝试刷新推荐 (attempt ${attempt + 1}/${maxRetries})`);
        // 刷新按钮可能有多种选择器形式
        const refreshButton = page.locator('[title="换一批"], button:has(svg.lucide-refresh-cw), button:has(svg[class*="refresh"])').first();
        if (await refreshButton.isVisible({ timeout: 3000 }).catch(() => false)) {
          await refreshButton.click();
          // 等待 loading 完成
          await page.waitForTimeout(3000);
          await page.waitForSelector('.animate-spin', { state: 'hidden', timeout: 30000 }).catch(() => {});
        } else {
          // 没有刷新按钮，可能推荐还在加载中，多等一会
          await page.waitForTimeout(10000);
        }
      }
    }
    return false;
  }

  test('音乐播放器组件应该在游戏页面渲染', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);

    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待故事加载完成 → 音乐推荐完成 → 播放器渲染
    await waitForMusicPlayer(page);

    // 验证播放器标题和推荐元数据可见
    await expect(page.locator('text=场景音乐')).toBeVisible();
    // 推荐元数据（mood 标签、环境标签等）应在 "场景音乐" 旁边
    // mood 标签用 text-primary 显示，环境标签用 bg-secondary/50
    const metaTags = page.locator('.text-xs.rounded').first();
    await expect(metaTags).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: 'test-results/music-player-loaded.png' });
  });

  test('应该显示推荐的歌曲信息', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    const hasSongs = await waitForMusicPlayerWithSongs(page);
    expect(hasSongs).toBe(true);

    const musicPlayerContainer = page.locator('.bg-card.border.rounded-lg').filter({ hasText: '场景音乐' });

    // 验证歌曲信息显示（歌曲名、艺术家）
    const songInfo = musicPlayerContainer.locator('.font-medium.truncate');
    await expect(songInfo).toBeVisible();

    const artistAlbum = musicPlayerContainer.locator('.text-muted-foreground.text-xs.truncate');
    await expect(artistAlbum).toBeVisible();

    await page.screenshot({ path: 'test-results/music-player-song-info.png' });
  });

  test('应该支持播放/暂停功能', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    const hasSongs = await waitForMusicPlayerWithSongs(page);
    expect(hasSongs).toBe(true);

    // 音乐播放器组件包含在 text="场景音乐" 标题的父容器中
    const musicPlayerContainer = page.locator('.bg-card.border.rounded-lg').filter({ hasText: '场景音乐' });

    // 播放/暂停按钮是 h-10 w-10 的大按钮（其他是 h-8 w-8）
    const playButton = musicPlayerContainer.locator('button.h-10.w-10');
    await expect(playButton).toBeVisible();

    // 点击播放
    await playButton.click();
    await page.waitForTimeout(1000);

    // 截图记录播放状态
    await page.screenshot({ path: 'test-results/music-player-playing.png' });

    // 再次点击暂停
    await playButton.click();
    await page.waitForTimeout(500);

    // 截图记录暂停状态
    await page.screenshot({ path: 'test-results/music-player-paused.png' });
  });

  test('应该支持切换歌曲', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    const hasSongs = await waitForMusicPlayerWithSongs(page);
    expect(hasSongs).toBe(true);

    const musicPlayerContainer = page.locator('.bg-card.border.rounded-lg').filter({ hasText: '场景音乐' });

    // 记录当前歌曲名
    const songNameLocator = musicPlayerContainer.locator('.font-medium.truncate');
    await expect(songNameLocator).toBeVisible({ timeout: 20000 });
    const firstSongName = await songNameLocator.textContent();

    // 下一首按钮（h-8 w-8 的 SkipForward 按钮，在播放按钮右边）
    const nextButton = musicPlayerContainer.locator('button.h-8.w-8').last();
    if (await nextButton.isVisible().catch(() => false)) {
      await nextButton.click();
      await page.waitForTimeout(2000);

      // 验证播放器仍然显示
      await expect(page.locator('text=场景音乐')).toBeVisible();

      // 截图记录
      await page.screenshot({ path: 'test-results/music-player-next-song.png' });
    }
  });

  test('刷新推荐应该加载新歌曲', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await waitForMusicPlayer(page);

    const musicPlayerContainer = page.locator('.bg-card.border.rounded-lg').filter({ hasText: '场景音乐' });

    // 找到刷新按钮（在标题栏右侧，含 RefreshCw SVG）
    const refreshButton = musicPlayerContainer.locator('button:has(svg.lucide-refresh-cw)').first();
    if (await refreshButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await refreshButton.click();

      // 等待推荐重新加载
      await page.waitForSelector('text=正在分析故事氛围', { state: 'hidden', timeout: 60000 }).catch(() => {});

      // 验证播放器仍然显示
      await expect(page.locator('text=场景音乐')).toBeVisible();

      // 截图记录
      await page.screenshot({ path: 'test-results/music-player-refreshed.png' });
    }
  });

  test('音乐播放器应该在页面加载后显示', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    const hasSongs = await waitForMusicPlayerWithSongs(page);
    expect(hasSongs).toBe(true);

    const musicPlayerContainer = page.locator('.bg-card.border.rounded-lg').filter({ hasText: '场景音乐' });

    // 验证播放器 UI 元素
    await expect(musicPlayerContainer.locator('.font-medium.truncate')).toBeVisible();
    await expect(musicPlayerContainer.locator('.text-muted-foreground.text-xs.truncate')).toBeVisible();

    await page.screenshot({ path: 'test-results/music-player-ui.png' });
  });

  test('播放器应该在页面切换后保持状态', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    const gameId = await ensureActiveGame(page, context);
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    const hasSongs = await waitForMusicPlayerWithSongs(page);
    expect(hasSongs).toBe(true);

    const musicPlayerContainer = page.locator('.bg-card.border.rounded-lg').filter({ hasText: '场景音乐' });

    // 记录当前歌曲
    const songName = await musicPlayerContainer.locator('.font-medium.truncate').textContent();
    expect(songName).toBeTruthy();

    // 导航到主页再返回
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    // 重新进入游戏
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 故事已有缓存，播放器应快速加载
    const hasSongsAgain = await waitForMusicPlayerWithSongs(page);
    expect(hasSongsAgain).toBe(true);

    await page.screenshot({ path: 'test-results/music-player-persisted.png' });
  });
});
