/**
 * API client tests
 */
import api from '@/lib/api';
import { fetchMusicRecommendation, fetchSongUrl } from '@/stores/useMusicStore';

// Helper: create a mock Response-like object that fetch resolves to
function mockFetchResponse(body: unknown = {}, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as unknown as globalThis.Response);
}

beforeEach(() => {
  // Reset fetch mock before each test
  global.fetch = jest.fn(() => mockFetchResponse({}));
});

afterEach(() => {
  jest.restoreAllMocks();
});

// ─── existing tests ────────────────────────────────────────────
describe('auth', () => {
  describe('logout', () => {
    it('throws on API failure', async () => {
      // Mock fetch to simulate network error for all retry attempts
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

      await expect(api.auth.logout()).rejects.toThrow('Network error');
    }, 15000); // Increase timeout to account for retry delays
  });
});

// ─── gameplay API path verification ────────────────────────────
describe('gameplay', () => {
  it('getState calls /games/{id}/state for live session state', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ player_state: {}, progress: {}, round_info: {}, current_event: null })
    );

    await api.gameplay.getState(296);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('/api/games/296');
    // Default method should be GET (undefined or 'GET')
    expect(options.method).toBeUndefined();
  });

  it('getState returns contract-compliant response with constraint_level and narrative_style fields', async () => {
    // Backend contract: GameStateResponse must include constraint_level,
    // narrative_style_id, and narrative_style_name
    const backendShape = {
      player_state: { player_name: 'Test', age: 25 },
      progress: { current_round: 1, current_week: 0 },
      round_info: { week_display: 'Week 1', season: 'Spring' },
      current_event: null,
      constraint_level: 'expert',
      narrative_style_id: 'chinese_classic_saga',
      narrative_style_name: 'Chinese Classic Saga',
    };
    global.fetch = jest.fn(() => mockFetchResponse(backendShape));

    const result = await api.gameplay.getState(42);

    expect(result.constraint_level).toBe('expert');
    expect(result.narrative_style_id).toBe('chinese_classic_saga');
    expect(result.narrative_style_name).toBe('Chinese Classic Saga');
    expect(result.player_state).toEqual({ player_name: 'Test', age: 25 });
  });

  it('generateEvent calls POST /games/{id}/event-sync', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ event_description: 'event', options: [] })
    );

    await api.gameplay.generateEvent(42, { custom_choices: ['a'] });

    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('/api/games/42/event-sync');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ custom_choices: ['a'] });
  });

  it('makeChoiceSync calls POST /games/{id}/choice-sync and returns backend-shaped response', async () => {
    const backendResponse = {
      story_continuation: 'The story continues...',
      summary: 'Round summary',
      effects_applied: { energy: 2, mood: -1 },
      need_weekly_summary: false,
      game_over: false,
    };
    global.fetch = jest.fn(() => mockFetchResponse(backendResponse));

    const result = await api.gameplay.makeChoiceSync(7, { option_index: 1 });

    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('/api/games/7/choice-sync');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ option_index: 1 });

    // Verify the response shape matches backend contract
    expect(result.story_continuation).toBe('The story continues...');
    expect(result.summary).toBe('Round summary');
    expect(result.effects_applied).toEqual({ energy: 2, mood: -1 });
    expect(result.need_weekly_summary).toBe(false);
    expect(result.game_over).toBe(false);
  });

  it('submitChoice calls POST /games/{id}/choices', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ result: 'ok', new_event: null })
    );

    await api.gameplay.submitChoice(7, { choice_index: 1 });

    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('/api/games/7/choices');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ choice_index: 1 });
  });
});

// ─── character API contract verification ────────────────────────
describe('character', () => {
  it('generateSetting era returns backend-contract fields: year, era_description, world_context', async () => {
    // Backend contract: era setting returns { year, era_description, world_context }
    // NOT era_name — that's a frontend-only display fallback
    const backendEraResponse = {
      year: 2024,
      era_description: '信息时代',
      world_context: '科技高速发展的现代社会',
    };
    global.fetch = jest.fn(() => mockFetchResponse(backendEraResponse));

    const result = await api.character.generateSetting({
      setting_type: 'era',
      player_name: 'TestPlayer',
      language: 'zh',
    });

    expect(result.year).toBe(2024);
    expect(result.era_description).toBe('信息时代');
    expect(result.world_context).toBe('科技高速发展的现代社会');
    // era_name should NOT be in backend response
    expect(result.era_name).toBeUndefined();
  });
});

// ─── music API path verification ───────────────────────────────
describe('music', () => {
  it('fetchMusicRecommendation calls POST /api/music/recommend', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ keywords: [], mood: 'calm', scene_type: 'forest', songs: [] })
    );

    await fetchMusicRecommendation('A gentle breeze...', 10);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    // Music API uses full URL (API_BASE_URL + /api/music/recommend)
    expect(url).toContain('/api/music/recommend');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ story_text: 'A gentle breeze...', game_id: 10, refresh: false });
  });

  it('fetchSongUrl calls GET /api/music/song-url with song_id param', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ url: 'https://example.com/song.mp3' })
    );

    await fetchSongUrl(12345);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain('/api/music/song-url?song_id=12345');
    // Should be GET (no method specified or 'GET')
    expect(options?.method).toBeUndefined();
  });
});

// ─── credentials: 'include' verification ───────────────────────
describe('credentials', () => {
  it('gameplay API requests include credentials', async () => {
    global.fetch = jest.fn(() => mockFetchResponse({}));

    await api.gameplay.getState(1);

    const [, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  it('auth API requests include credentials', async () => {
    global.fetch = jest.fn(() => mockFetchResponse({ user_id: 1 }));

    await api.auth.me();

    const [, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  it('games API requests include credentials', async () => {
    global.fetch = jest.fn(() => mockFetchResponse([]));

    await api.games.list();

    const [, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  it('music recommend request includes credentials', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ keywords: [], mood: '', scene_type: '', songs: [] })
    );

    await fetchMusicRecommendation('text');

    const [, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  it('music song-url request includes credentials', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ url: 'https://example.com/song.mp3' })
    );

    await fetchSongUrl(1);

    const [, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(options.credentials).toBe('include');
  });
});

describe('production API base safety', () => {
  const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

  afterEach(() => {
    if (originalApiUrl === undefined) {
      delete process.env.NEXT_PUBLIC_API_URL;
    } else {
      process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
    }
    jest.resetModules();
  });

  it('keeps voice settings on the same-origin proxy when a loopback URL leaks into the public build', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://127.0.0.1:3010/api';
    jest.resetModules();
    const { api: isolatedApi } = await import('@/lib/api');
    global.fetch = jest.fn(() => mockFetchResponse({ auto_read_enabled: false }));

    await isolatedApi.voice_reading.getSettings();

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/voice-reading/settings',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('keeps music recommendations on the same-origin proxy when a loopback URL leaks into the public build', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://127.0.0.1:3010/api';
    jest.resetModules();
    const { fetchMusicRecommendation: isolatedFetchMusicRecommendation } = await import('@/stores/useMusicStore');
    global.fetch = jest.fn(() => mockFetchResponse({ keywords: [], mood: 'calm', scene_type: 'study', songs: [] }));

    await isolatedFetchMusicRecommendation('雨夜的图书馆里，你决定继续整理证据。', 7);

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/music/recommend',
      expect.objectContaining({ credentials: 'include' }),
    );
  });
});

// ─── 204 No Content handling ───────────────────────────────────
// 204 handling was removed — backend no longer returns 204 on these endpoints
describe('204 No Content', () => {
  it('throws on 204 response (no special handling)', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error('Unexpected end of JSON input')),
        headers: new Headers(),
      } as unknown as globalThis.Response)
    );

    await expect(api.games.list()).rejects.toThrow();
  });

  it('throws on 204 for scene image endpoint (no special handling)', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error('Unexpected end of JSON input')),
        headers: new Headers(),
      } as unknown as globalThis.Response)
    );

    await expect(api.images.getRoundSceneImage(1, 0, 0)).rejects.toThrow();
  });
});
