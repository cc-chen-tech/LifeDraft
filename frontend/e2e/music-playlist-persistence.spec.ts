/**
 * E2E: Music playlist persistence across page navigation.
 *
 * Verifies:
 * 1. Music player is globally mounted (visible on /play and survives navigation to /)
 * 2. Current song remains unchanged when playlist is updated with new recommendations
 * 3. Playlist state is restored after page reload
 */
import { test, expect } from '@playwright/test';
import { ensureActiveGame } from './helpers/auth';

const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
const API_URL = process.env.E2E_API_URL || `http://${process.env.E2E_BACKEND_HOST || '127.0.0.1'}:${process.env.E2E_BACKEND_PORT || '8000'}`;

test.describe('Music Playlist Persistence', () => {
  test.setTimeout(180_000);

  test('music player should survive navigation from /play to / and back', async ({ page }) => {
    const gameId = await ensureActiveGame(page, page.context(), {
      player_name: '播放列表测试角色',
      life_vision: '测试音乐播放列表持久化',
    });

    // Seed a playlist via API so the global player has something to render
    const putResp = await page.request.put(`${API_URL}/api/music/playlist/${gameId}`, {
      data: {
        songs: [
          { id: 2001, name: '导航测试歌曲A', artists: ['歌手A'], album: '专辑X', duration: 180 },
          { id: 2002, name: '导航测试歌曲B', artists: ['歌手B'], album: '专辑Y', duration: 200 },
        ],
        mood: '测试',
        keywords: ['测试'],
      },
    });
    expect(putResp.ok()).toBe(true);

    // Set gameId in localStorage so GlobalMusicPlayer loads the persisted playlist
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');
    await page.evaluate((id) => localStorage.setItem('gameId', String(id)), gameId);

    // Reload so GlobalMusicWrapper picks up the gameId and loads the playlist
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // Wait for mini player bar and expand it
    const miniBar = page.locator('[data-testid="global-music-mini-bar"]').first();
    await miniBar.waitFor({ state: 'visible', timeout: 30000 });
    await expect(page.locator('[data-testid="global-music-player"]')).toHaveClass(/top-16/);
    await expect(page.locator('[data-testid="global-music-player"]')).not.toHaveClass(/top-0/);
    await expect(page.locator('[data-testid="global-music-player"]')).not.toHaveClass(/bottom-0/);
    await expect(page.locator('[data-testid="global-music-player"]')).not.toHaveClass(/md:bottom-4/);
    await miniBar.click();

    // Wait for the expanded music player content (either "场景音乐" or "播放列表")
    const fullPlayer = page.locator('text=/场景音乐|播放列表/').first();
    await fullPlayer.waitFor({ state: 'visible', timeout: 30000 });

    // Song name should be visible (current song from seeded playlist)
    const songNameLocator = page.locator('.font-medium.truncate').first();
    await expect(songNameLocator).toBeVisible({ timeout: 30000 });
    const firstSongName = await songNameLocator.textContent();
    expect(firstSongName).toBeTruthy();

    // Navigate away to home
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    // Navigate back to game
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // Expand mini bar again
    const miniBar2 = page.locator('[data-testid="global-music-mini-bar"]').first();
    await miniBar2.waitFor({ state: 'visible', timeout: 30000 });
    await miniBar2.click();

    // Music player expanded content should still be present
    const fullPlayer2 = page.locator('text=/场景音乐|播放列表/').first();
    await fullPlayer2.waitFor({ state: 'visible', timeout: 30000 });

    const restoredSongName = page.locator('.font-medium.truncate').first();
    await expect(restoredSongName).toBeVisible({ timeout: 30000 });

    await page.screenshot({ path: 'test-results/playlist-persisted-navigation.png' });
  });

  test('playlist API should return state after PUT merge', async ({ page }) => {
    const gameId = await ensureActiveGame(page, page.context(), {
      player_name: '播放列表测试角色',
      life_vision: '测试音乐播放列表持久化',
    });

    // Seed a playlist via API
    const putResp = await page.request.put(`${API_URL}/api/music/playlist/${gameId}`, {
      data: {
        songs: [
          { id: 1001, name: 'Persisted Song A', artists: ['Artist A'], album: 'Album X', duration: 200 },
          { id: 1002, name: 'Persisted Song B', artists: ['Artist B'], album: 'Album Y', duration: 180 },
        ],
        mood: '测试心情',
        keywords: ['测试'],
      },
    });
    expect(putResp.ok()).toBe(true);
    const putData = await putResp.json();
    expect(putData.current_song).not.toBeNull();
    expect(putData.current_song.id).toBe(1001);
    expect(putData.queue.length).toBe(1);
    expect(putData.queue[0].id).toBe(1002);

    // GET should return the same state
    const getResp = await page.request.get(`${API_URL}/api/music/playlist/${gameId}`);
    expect(getResp.ok()).toBe(true);
    const getData = await getResp.json();
    expect(getData.current_song.id).toBe(1001);
    expect(getData.queue[0].id).toBe(1002);

    // PUT with new songs should preserve current
    const putResp2 = await page.request.put(`${API_URL}/api/music/playlist/${gameId}`, {
      data: {
        songs: [
          { id: 1001, name: 'Persisted Song A', artists: ['Artist A'], album: 'Album X', duration: 200 },
          { id: 1003, name: 'New Song C', artists: ['Artist C'], album: 'Album Z', duration: 210 },
        ],
        mood: '更新心情',
      },
    });
    expect(putResp2.ok()).toBe(true);
    const putData2 = await putResp2.json();
    expect(putData2.current_song.id).toBe(1001); // preserved
    expect(putData2.queue.length).toBe(1);
    expect(putData2.queue[0].id).toBe(1003); // new queue

    // Advance should move to next
    const advanceResp = await page.request.post(`${API_URL}/api/music/playlist/${gameId}/advance`);
    expect(advanceResp.ok()).toBe(true);
    const advanceData = await advanceResp.json();
    expect(advanceData.current_song.id).toBe(1003);
    expect(advanceData.played_songs.length).toBe(1);
    expect(advanceData.played_songs[0].id).toBe(1001);
  });
});
