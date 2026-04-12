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
  it('getState calls /games/{id} (not /games/{id}/state)', async () => {
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

  it('generateEvent calls POST /games/{id}/events', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse({ story: 'event', options: [] })
    );

    await api.gameplay.generateEvent(42, { custom_choices: ['a'] });

    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('/api/games/42/events');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ custom_choices: ['a'] });
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
    expect(JSON.parse(options.body)).toEqual({ story_text: 'A gentle breeze...', game_id: 10 });
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
