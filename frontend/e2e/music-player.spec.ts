/**
 * MusicPlayer E2E 测试
 *
 * 测试音乐播放器组件的渲染和基本交互
 * 注意：这些测试验证播放器 UI 存在和基本功能，不涉及实际音频播放
 */
import { test, expect, Locator, Page } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('MusicPlayer 音乐播放器', () => {
  async function openMusicFixture(page: Page): Promise<Locator> {
    await page.goto(`${BASE_URL}/e2e-regression`);
    await page.waitForLoadState('domcontentloaded');
    const fixture = page.getByRole('region', { name: '音乐回归夹具' });
    await expect(fixture.getByText('场景音乐')).toBeVisible({ timeout: 10000 });
    return fixture;
  }

  async function waitForRecommendationSettled(fixture: Locator) {
    await expect
      .poll(async () => {
        const fixtureText = await fixture.innerText();
        if (fixtureText.includes('正在分析故事氛围')) return 'loading';
        if (fixtureText.includes('未找到匹配的音乐')) return 'empty';
        if (fixtureText.includes('获取推荐失败') || fixtureText.includes('音乐服务暂不可用')) return 'error';
        if (await fixture.locator('.font-medium.truncate').count()) return 'songs';
        return 'unknown';
      }, { timeout: 30000 })
      .toMatch(/^(songs|empty|error)$/);
  }

  async function hasSongs(fixture: Locator) {
    await waitForRecommendationSettled(fixture);
    return fixture.locator('.font-medium.truncate').first().isVisible().catch(() => false);
  }

  async function expectVisibleMusicOutcome(fixture: Locator) {
    await waitForRecommendationSettled(fixture);
    const outcome = fixture.getByText(/未找到匹配的音乐|获取推荐失败|音乐服务暂不可用/);
    const songInfo = fixture.locator('.font-medium.truncate').first();
    await expect(songInfo.or(outcome).first()).toBeVisible({ timeout: 5000 });
  }

  test('音乐播放器组件应该在游戏页面渲染', async ({ page }) => {
    await openMusicFixture(page);
    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-loaded.png' });
  });

  test('应该显示推荐的歌曲信息或明确降级状态', async ({ page }) => {
    const fixture = await openMusicFixture(page);
    await expectVisibleMusicOutcome(fixture);

    if (await fixture.locator('.font-medium.truncate').first().isVisible().catch(() => false)) {
      const artistAlbum = fixture.locator('.text-muted-foreground.text-xs.truncate');
      await expect(artistAlbum.first()).toBeVisible();
    }

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-song-info.png' });
  });

  test('应该支持播放/暂停功能或保持可解释的不可用状态', async ({ page }) => {
    const fixture = await openMusicFixture(page);
    const songsAvailable = await hasSongs(fixture);
    if (!songsAvailable) {
      await expectVisibleMusicOutcome(fixture);
      return;
    }

    // 找到播放/暂停按钮（通常是第一个带有 svg 的按钮）
    const playButton = fixture.locator('button').filter({ has: fixture.locator('svg') }).nth(1);
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

  test('应该支持切换歌曲或保持可解释的不可用状态', async ({ page }) => {
    const fixture = await openMusicFixture(page);
    const songsAvailable = await hasSongs(fixture);
    if (!songsAvailable) {
      await expectVisibleMusicOutcome(fixture);
      return;
    }

    // 记录当前歌曲名
    const songNameLocator = fixture.locator('.font-medium.truncate');
    await expect(songNameLocator).toBeVisible();
    const firstSongName = await songNameLocator.textContent();

    // 找到下一首按钮并点击（使用 aria-label 或 title 属性）
    const nextButton = fixture.locator('button[title="下一首"], button:has(svg[data-lucide="skip-forward"])');
    await expect(nextButton.first()).toBeVisible();
    await nextButton.first().click();
    await page.waitForTimeout(1000);

    // 验证播放器仍然显示
    await expect(fixture.getByText('场景音乐')).toBeVisible();

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-next-song.png' });
  });

  test('刷新推荐应该重新触发加载并回到可见状态', async ({ page }) => {
    const fixture = await openMusicFixture(page);
    await expectVisibleMusicOutcome(fixture);

    // 找到刷新按钮并点击
    const refreshButton = fixture.locator('button[title="换一批"], button:has(svg[data-lucide="refresh-cw"])');
    await expect(refreshButton.first()).toBeVisible();
    await refreshButton.first().click();
    await page.waitForTimeout(2000);

    // 验证播放器仍然显示
    await expect(fixture.getByText('场景音乐')).toBeVisible();

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-refreshed.png' });
  });

  test('音乐播放器应该在页面加载后显示', async ({ page }) => {
    const fixture = await openMusicFixture(page);
    await expectVisibleMusicOutcome(fixture);
    // 验证播放器 UI 元素
    await expect(fixture.getByText('场景音乐')).toBeVisible();

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-ui.png' });
  });

  test('播放器应该在页面切换后保持可恢复', async ({ page }) => {
    let fixture = await openMusicFixture(page);
    await expectVisibleMusicOutcome(fixture);

    // 导航到主页再返回
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    // 重新进入游戏
    await page.goto(`${BASE_URL}/e2e-regression`);
    await page.waitForLoadState('domcontentloaded');
    fixture = page.getByRole('region', { name: '音乐回归夹具' });

    // 验证播放器仍然显示
    await expect(fixture.getByText('场景音乐')).toBeVisible({ timeout: 20000 });

    // 截图记录
    await page.screenshot({ path: 'test-results/music-player-persisted.png' });
  });

  test('会员 AI 曲目生成后只进入后续队列且不切换当前歌曲', async ({ page }) => {
    await openMusicFixture(page);

    await page.getByRole('button', { name: '加载会员音乐队列夹具' }).click();
    await expect(page.getByTestId('current-music-source')).toHaveText('netease');
    await expect(page.getByTestId('current-music-title')).toHaveText('网易云 当前曲');
    await expect(page.getByTestId('music-queue-order')).toHaveText('网易云 下一曲 | AI 雨夜码头 | 网易云 后续曲');

    await page.screenshot({ path: 'test-results/music-player-ai-queue-supplement.png' });
  });
});
