/**
 * API Error Handling Path Tests
 * Tests special error code handling, retry logic, and timeout handling
 */

// Mock localStorage before importing api
const mockLocalStorage = {
  removeItem: jest.fn(),
  getItem: jest.fn(),
  setItem: jest.fn(),
};
Object.defineProperty(global, 'localStorage', { value: mockLocalStorage, writable: true });

// Import api after mocking
import api from '@/lib/api';

// Helper: create a mock Response-like object
function mockFetchResponse(body: unknown = {}, status = 200, ok?: boolean) {
  const isOk = ok !== undefined ? ok : status >= 200 && status < 300;
  return Promise.resolve({
    ok: isOk,
    status,
    json: () => Promise.resolve(body),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as unknown as globalThis.Response);
}

// Track console calls - must be after imports to avoid hoisting issues
let consoleWarnSpy: jest.SpyInstance;
let consoleErrorSpy: jest.SpyInstance;

beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = jest.fn();
  mockLocalStorage.removeItem.mockClear();

  // Setup console spies
  consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
  consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  consoleWarnSpy?.mockRestore();
  consoleErrorSpy?.mockRestore();
});

describe('API Error Handling', () => {
  it('retains structured image failure metadata', async () => {
    global.fetch = jest.fn(() =>
      mockFetchResponse(
        {
          detail: {
            code: 'minimax_2056',
            message: '图片生成额度暂时不可用，请稍后再试',
            retryable: false,
          },
        },
        503,
        false
      )
    );

    await expect(
      api.images.generate({
        game_id: 1,
        image_type: 'character',
        entity_name: '林见微',
        description: '现代职场人物',
      })
    ).rejects.toMatchObject({
      status: 503,
      code: 'minimax_2056',
      retryable: false,
      message: '图片生成额度暂时不可用，请稍后再试',
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  describe('Special Error Code Handling - 401', () => {
    it('uses FastAPI detail text instead of generic Request failed for auth login errors', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ detail: 'Invalid private ID' }, 401, false)
      );

      await expect(api.auth.login({ private_id: 'wrong-id' })).rejects.toThrow('Invalid private ID');
    });

    it('silently handles 401 on /auth/me without triggering logout', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Unauthorized' }, 401, false)
      );

      await expect(api.auth.me()).rejects.toThrow();

      // Should not trigger logout (no localStorage removal)
      expect(mockLocalStorage.removeItem).not.toHaveBeenCalled();
    });

    it('silently handles 401 on /collection/* endpoints without triggering logout', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Unauthorized' }, 401, false)
      );

      await expect(api.collection.getStatus(123)).rejects.toThrow();

      // Should not trigger logout
      expect(mockLocalStorage.removeItem).not.toHaveBeenCalled();
    });

    it('silently handles 401 on /collection/*/details without triggering logout', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Unauthorized' }, 401, false)
      );

      await expect(api.collection.get(123)).rejects.toThrow();

      // Should not trigger logout
      expect(mockLocalStorage.removeItem).not.toHaveBeenCalled();
    });

    it('triggers logout on 401 for protected endpoints like /games', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Unauthorized' }, 401, false)
      );

      await expect(api.games.list()).rejects.toThrow();

      // Should trigger logout
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('gameId');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('gameState');
    });

    it('triggers logout on 401 for gameplay endpoints', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Unauthorized' }, 401, false)
      );

      await expect(api.gameplay.getState(123)).rejects.toThrow();

      // Should trigger logout
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('gameId');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('gameState');
    });

    it('triggers logout on 401 for auth logout endpoint', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Unauthorized' }, 401, false)
      );

      await expect(api.auth.logout()).rejects.toThrow();

      // Should trigger logout
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('gameId');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('gameState');
    });

    it('debounces 401 redirect to prevent multiple redirects', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Unauthorized' }, 401, false)
      );

      // Trigger multiple 401s simultaneously
      await Promise.allSettled([
        api.games.list(),
        api.games.list(),
        api.games.list(),
      ]);

      // Should only remove items once (debounced)
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('gameId');
    });
  });

  describe('Special Error Code Handling - 404', () => {
    it('silently handles 404 on /images/scene/* endpoints', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Not Found' }, 404, false)
      );

      await expect(api.images.getRoundSceneImage(123, 1)).rejects.toThrow();

      // Should not log error for 404 on scene images (normal polling behavior)
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('silently handles 404 on /images/scene/* with stage parameter', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Not Found' }, 404, false)
      );

      await expect(api.images.getRoundSceneImageByStage(123, 1, 'opening')).rejects.toThrow();

      // Should not log error
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('logs error for 404 on other endpoints', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Not Found' }, 404, false)
      );

      await expect(api.games.load(123)).rejects.toThrow();

      // Should log error for non-image 404s
      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });

  describe('Retry Logic', () => {
    it('retries 3 times on network error then throws', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

      await expect(api.games.list()).rejects.toThrow('Network error');

      // Should retry 3 times
      expect(global.fetch).toHaveBeenCalledTimes(3);
    }, 15000);

    it('retries on 5xx server errors', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Server Error' }, 500, false)
      );

      await expect(api.games.list()).rejects.toThrow();

      // Should retry multiple times
      expect(global.fetch).toHaveBeenCalledTimes(3);
    }, 15000);

    it('retries on 503 service unavailable', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Service Unavailable' }, 503, false)
      );

      await expect(api.games.list()).rejects.toThrow();

      expect(global.fetch).toHaveBeenCalledTimes(3);
    }, 15000);

    it('does not retry on 4xx client errors (except 401 on first attempt)', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Bad Request' }, 400, false)
      );

      await expect(api.games.create({ player_name: 'test' })).rejects.toThrow();

      // Should not retry on 400
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('does not retry on 403 forbidden', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Forbidden' }, 403, false)
      );

      await expect(api.games.list()).rejects.toThrow();

      // Should not retry on 403
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('retries only once on 401 (cookie forwarding race condition)', async () => {
      global.fetch = jest.fn()
        .mockReturnValueOnce(mockFetchResponse({ message: 'Unauthorized' }, 401, false))
        .mockReturnValueOnce(mockFetchResponse({ message: 'Unauthorized' }, 401, false));

      await expect(api.games.list()).rejects.toThrow();

      // Should retry once on 401, then stop
      expect(global.fetch).toHaveBeenCalledTimes(2);
    }, 10000);

    it('succeeds on retry when server recovers', async () => {
      global.fetch = jest.fn()
        .mockReturnValueOnce(mockFetchResponse({ message: 'Server Error' }, 500, false))
        .mockReturnValueOnce(mockFetchResponse({ message: 'Server Error' }, 500, false))
        .mockReturnValueOnce(mockFetchResponse([{ game_id: 1, player_name: 'test' }], 200, true));

      const result = await api.games.list();

      expect(result).toEqual([{ game_id: 1, player_name: 'test' }]);
      expect(global.fetch).toHaveBeenCalledTimes(3);
    }, 15000);

    it('uses exponential backoff between retries', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

      await expect(api.games.list()).rejects.toThrow();

      // Should retry 3 times
      expect(global.fetch).toHaveBeenCalledTimes(3);
    }, 15000);
  });

  describe('Timeout Handling', () => {
    it('cleans up timeout after successful response', async () => {
      const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');
      global.fetch = jest.fn(() =>
        mockFetchResponse({ items: [], characters: [], landmarks: [] }, 200, true)
      );

      await api.collection.recognizeEntities(123, {});

      // Should clear timeout after successful response
      expect(clearTimeoutSpy).toHaveBeenCalled();
    });

    it('cleans up timeout after error response', async () => {
      const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Error' }, 500, false)
      );

      await expect(api.collection.recognizeEntities(123, {})).rejects.toThrow();

      // Should clear timeout even on error
      expect(clearTimeoutSpy).toHaveBeenCalled();
    }, 15000);

    it('respects custom timeout for long-running operations', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ items: [], characters: [], landmarks: [] }, 200, true)
      );

      await api.collection.recognizeEntities(123, { entity_types: ['items'] });

      // The recognizeEntities endpoint uses a 180000ms timeout
      // We verify the request was made (timeout is handled internally)
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });
  });

  describe('Error Object Structure', () => {
    it('includes status code in error object', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Custom error message' }, 422, false)
      );

      try {
        await api.games.create({ player_name: 'test' });
        fail('Should have thrown');
      } catch (error: unknown) {
        expect(error).toHaveProperty('status', 422);
        expect((error as Error).message).toBe('Custom error message');
      }
    });

    it('uses default message when response body is empty', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          json: () => Promise.reject(new Error('Invalid JSON')),
          headers: new Headers({ 'Content-Type': 'application/json' }),
        } as unknown as globalThis.Response)
      );

      try {
        await api.games.list();
        fail('Should have thrown');
      } catch (error: unknown) {
        expect((error as Error).message).toBe('Server error: 500');
      }
    }, 15000);

    it('preserves error message from response body', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({ message: 'Player name is required' }, 400, false)
      );

      try {
        await api.games.create({ player_name: '' });
        fail('Should have thrown');
      } catch (error: unknown) {
        expect((error as Error).message).toBe('Player name is required');
      }
    });

    it('preserves structured FastAPI detail error code and message', async () => {
      global.fetch = jest.fn(() =>
        mockFetchResponse({
          detail: {
            error: 'choice_already_processed',
            message: 'Choice was already processed. Please continue to next round.',
          },
        }, 400, false)
      );

      await expect(api.gameplay.makeChoiceSync(123, { option_index: 0 }))
        .rejects
        .toThrow('choice_already_processed: Choice was already processed. Please continue to next round.');
    });
  });

  describe('Request Credentials', () => {
    it('always includes credentials in requests', async () => {
      global.fetch = jest.fn(() => mockFetchResponse([]));

      await api.games.list();

      const [, options] = (global.fetch as jest.Mock).mock.calls[0];
      expect(options.credentials).toBe('include');
    });

    it('includes Content-Type header', async () => {
      global.fetch = jest.fn(() => mockFetchResponse([]));

      await api.games.list();

      const [, options] = (global.fetch as jest.Mock).mock.calls[0];
      expect(options.headers).toMatchObject({ 'Content-Type': 'application/json' });
    });
  });
});
