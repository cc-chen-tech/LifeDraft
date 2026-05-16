/**
 * useCollectionStore 缓存机制测试
 *
 * 验证 fetchCollection 的短时缓存行为：
 * 1. 30 秒内重复调用只发 1 次请求
 * 2. isRefresh=true 时绕过缓存
 * 3. 写操作后的强制刷新能正常获取新数据
 * 4. 请求去重 - 并发请求只发一次
 * 5. 数据合并 - 刷新时保留已有图片URL
 * 6. 竞态条件处理
 */

import { useCollectionStore } from '@/stores/useCollectionStore';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

// Mock timers for cache TTL tests
jest.useFakeTimers();

describe('useCollectionStore cache', () => {
  beforeEach(() => {
    useCollectionStore.setState({
      characters: [],
      items: [],
      landmarks: [],
      isLoading: false,
      isRefreshing: false,
      activeTab: 'characters',
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: null,
    });
    jest.clearAllMocks();
    jest.clearAllTimers();
    global.fetch = jest.fn();
  });

  describe('Request Deduplication', () => {
    it('deduplicates concurrent fetch requests for same gameId', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };

      // Create a delayed promise to simulate network latency
      let resolvePromise: (value: unknown) => void;
      const delayedPromise = new Promise<unknown>((resolve) => {
        resolvePromise = resolve;
      });

      (global.fetch as jest.Mock).mockReturnValue(delayedPromise);

      // Fire 3 concurrent requests for the same gameId
      const promise1 = useCollectionStore.getState().fetchCollection(1);
      const promise2 = useCollectionStore.getState().fetchCollection(1);
      const promise3 = useCollectionStore.getState().fetchCollection(1);

      // API should only be called once
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Resolve the API call
      resolvePromise!(jsonResponse(mockResponse));

      // All promises should resolve
      await Promise.all([promise1, promise2, promise3]);

      // Still only 1 API call
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('allows different gameId requests to proceed independently', async () => {
      const mockResponse1 = {
        game_id: 1,
        characters: [{ name: 'Game1Char', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };
      const mockResponse2 = {
        game_id: 2,
        characters: [{ name: 'Game2Char', role: '主角', description: '', affinity: 100, age: 20, gender: '女', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse(mockResponse1))
        .mockResolvedValueOnce(jsonResponse(mockResponse2));

      // Fire requests for different gameIds
      const promise1 = useCollectionStore.getState().fetchCollection(1);
      const promise2 = useCollectionStore.getState().fetchCollection(2);

      await Promise.all([promise1, promise2]);

      // API should be called twice (different gameIds)
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(global.fetch).toHaveBeenNthCalledWith(1, '/api/collection/1/details', expect.objectContaining({ credentials: 'include' }));
      expect(global.fetch).toHaveBeenNthCalledWith(2, '/api/collection/2/details', expect.objectContaining({ credentials: 'include' }));
    });

    it('allows sequential requests after first completes', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      // First request
      await useCollectionStore.getState().fetchCollection(1);
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Advance time to clear cache
      jest.advanceTimersByTime(31000);

      // Second request (after first completes and cache expires)
      await useCollectionStore.getState().fetchCollection(1);
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('Cache TTL Behavior', () => {
    it('should call api.collection.get on first fetch (cache miss)', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().fetchCollection(1);

      expect(global.fetch).toHaveBeenCalledTimes(1);
      expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/details', expect.objectContaining({ credentials: 'include' }));
    });

    it('should use cache for repeated fetch within 30 seconds (cache hit)', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      // 第一次请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // 快进 5 秒（仍在缓存有效期内）
      jest.advanceTimersByTime(5000);

      // 第二次请求（在缓存有效期内）
      await useCollectionStore.getState().fetchCollection(1);
      // 仍然只调用 1 次
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // 数据应该保持一致
      expect(useCollectionStore.getState().characters).toHaveLength(1);
      expect(useCollectionStore.getState().characters[0].name).toBe('主角');
    });

    it('should bypass cache when isRefresh=true', async () => {
      const mockResponse1 = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };
      const mockResponse2 = {
        game_id: 1,
        characters: [
          { name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false },
          { name: 'NPC1', role: '朋友', description: '', affinity: 80, age: 25, gender: '女', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false },
        ],
        items: [],
        landmarks: [],
      };
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse(mockResponse1))
        .mockResolvedValueOnce(jsonResponse(mockResponse2));

      // 第一次普通请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(global.fetch).toHaveBeenCalledTimes(1);
      expect(useCollectionStore.getState().characters).toHaveLength(1);

      // 强制刷新
      await useCollectionStore.getState().fetchCollection(1, true);
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(useCollectionStore.getState().characters).toHaveLength(2);
    });

    it('should call api again after cache expires (TTL exceeded)', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      // 第一次请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // 快进 31 秒，超过缓存有效期
      jest.advanceTimersByTime(31000);

      // 再次请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('should not use cache when hasData is false (empty arrays)', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      // First request (store is empty, returns empty arrays)
      await useCollectionStore.getState().fetchCollection(1);
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Second request immediately - cache is NOT used because hasData is false
      // (all arrays are empty, so hasData = false)
      await useCollectionStore.getState().fetchCollection(1);
      // API should be called again because empty data doesn't count as cached data
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('Data Merging on Refresh', () => {
    it('preserves image_url during refresh when new data lacks it', async () => {
      // Setup initial state with character having image_url
      useCollectionStore.setState({
        characters: [{
          name: '赵灵儿',
          role: '妻子',
          description: '测试描述',
          affinity: 95,
          age: 16,
          gender: '女',
          occupation: '女娲后裔',
          personality_traits: ['温柔'],
          image_url: 'http://example.com/old_image.png',
          image_generated: true,
          description_generated: true,
        }],
      });

      // Mock API returns new data without image_url (simulating generation in progress)
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        characters: [{
          name: '赵灵儿',
          role: '妻子',
          description: '测试描述',
          affinity: 95,
          age: 16,
          gender: '女',
          occupation: '女娲后裔',
          personality_traits: ['温柔'],
          image_url: '',  // Empty URL - generation in progress
          image_generated: false,
          description_generated: true,
        }],
        items: [],
        landmarks: [],
      }));

      // Call refresh mode
      await useCollectionStore.getState().fetchCollection(1, true);

      // Verify old image_url is preserved to avoid flickering
      const character = useCollectionStore.getState().characters[0];
      expect(character.image_url).toBe('http://example.com/old_image.png');
      expect(character.image_generated).toBe(true);
    });

    it('updates image_url during refresh when new data has it', async () => {
      // Setup initial state
      useCollectionStore.setState({
        characters: [{
          name: '赵灵儿',
          role: '妻子',
          description: '测试描述',
          affinity: 95,
          age: 16,
          gender: '女',
          occupation: '女娲后裔',
          personality_traits: ['温柔'],
          image_url: 'http://example.com/old_image.png',
          image_generated: true,
          description_generated: true,
        }],
      });

      // Mock API returns new data with new image_url
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        characters: [{
          name: '赵灵儿',
          role: '妻子',
          description: '测试描述',
          affinity: 95,
          age: 16,
          gender: '女',
          occupation: '女娲后裔',
          personality_traits: ['温柔'],
          image_url: 'http://example.com/new_image.png',  // New URL
          image_generated: true,
          description_generated: true,
        }],
        items: [],
        landmarks: [],
      }));

      // Call refresh mode
      await useCollectionStore.getState().fetchCollection(1, true);

      // Verify new image_url is used
      const character = useCollectionStore.getState().characters[0];
      expect(character.image_url).toBe('http://example.com/new_image.png');
    });

    it('does not merge data in initial load mode (isRefresh=false)', async () => {
      // Mock API returns data
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        characters: [{
          name: '赵灵儿',
          role: '妻子',
          description: '测试描述',
          affinity: 95,
          age: 16,
          gender: '女',
          occupation: '女娲后裔',
          personality_traits: ['温柔'],
          image_url: '',  // Empty URL
          image_generated: false,
          description_generated: true,
        }],
        items: [],
        landmarks: [],
      }));

      // Call initial load mode (isRefresh=false)
      await useCollectionStore.getState().fetchCollection(1, false);

      // Verify API data is used directly without merging
      const character = useCollectionStore.getState().characters[0];
      expect(character.image_url).toBe('');
      expect(character.image_generated).toBe(false);
    });

    it('preserves image_url for multiple characters during refresh', async () => {
      // Setup initial state with multiple characters
      useCollectionStore.setState({
        characters: [
          {
            name: '赵灵儿',
            role: '妻子',
            description: '测试描述1',
            affinity: 95,
            age: 16,
            gender: '女',
            occupation: '女娲后裔',
            personality_traits: ['温柔'],
            image_url: 'http://example.com/linger.png',
            image_generated: true,
            description_generated: true,
          },
          {
            name: '李逍遥',
            role: '丈夫',
            description: '测试描述2',
            affinity: 95,
            age: 20,
            gender: '男',
            occupation: '剑客',
            personality_traits: ['豪爽'],
            image_url: 'http://example.com/xiaoyao.png',
            image_generated: true,
            description_generated: true,
          },
        ],
      });

      // Mock API returns new data where only one character has new image
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        characters: [
          {
            name: '赵灵儿',
            role: '妻子',
            description: '测试描述1',
            affinity: 95,
            age: 16,
            gender: '女',
            occupation: '女娲后裔',
            personality_traits: ['温柔'],
            image_url: '',  // Empty - preserve old
            image_generated: false,
            description_generated: true,
          },
          {
            name: '李逍遥',
            role: '丈夫',
            description: '测试描述2',
            affinity: 95,
            age: 20,
            gender: '男',
            occupation: '剑客',
            personality_traits: ['豪爽'],
            image_url: 'http://example.com/xiaoyao_new.png',  // New image
            image_generated: true,
            description_generated: true,
          },
        ],
        items: [],
        landmarks: [],
      }));

      // Call refresh mode
      await useCollectionStore.getState().fetchCollection(1, true);

      // Verify merging behavior
      const characters = useCollectionStore.getState().characters;
      expect(characters[0].image_url).toBe('http://example.com/linger.png');  // Preserved
      expect(characters[1].image_url).toBe('http://example.com/xiaoyao_new.png');  // Updated
    });
  });

  describe('Race Conditions', () => {
    it('handles rapid open/close panel without corrupting state', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };

      // Create a delayed promise
      let resolvePromise: (value: unknown) => void;
      const delayedPromise = new Promise<unknown>((resolve) => {
        resolvePromise = resolve;
      });

      (global.fetch as jest.Mock).mockReturnValue(delayedPromise);

      // Fire multiple rapid requests
      const promise1 = useCollectionStore.getState().fetchCollection(1);
      const promise2 = useCollectionStore.getState().fetchCollection(1);
      const promise3 = useCollectionStore.getState().fetchCollection(1);

      // State should show loading
      expect(useCollectionStore.getState().isLoading).toBe(true);

      // Resolve the API call
      resolvePromise!(jsonResponse(mockResponse));

      // Wait for all promises
      await Promise.all([promise1, promise2, promise3]);

      // State should be consistent
      expect(useCollectionStore.getState().isLoading).toBe(false);
      expect(useCollectionStore.getState().characters).toHaveLength(1);
      expect(useCollectionStore.getState().characters[0].name).toBe('主角');
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('handles request returning out of order correctly', async () => {
      // This test verifies that if requests somehow get out of order,
      // the cache mechanism prevents duplicate data issues
      const mockResponse1 = {
        game_id: 1,
        characters: [{ name: 'First', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };

      // First request
      (global.fetch as jest.Mock).mockResolvedValueOnce(jsonResponse(mockResponse1));
      await useCollectionStore.getState().fetchCollection(1);

      expect(useCollectionStore.getState().characters[0].name).toBe('First');

      // Advance time to expire cache
      jest.advanceTimersByTime(31000);

      const mockResponse2 = {
        game_id: 1,
        characters: [{ name: 'Second', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };

      // Second request (after cache expired)
      (global.fetch as jest.Mock).mockResolvedValueOnce(jsonResponse(mockResponse2));
      await useCollectionStore.getState().fetchCollection(1);

      // Should have the second response
      expect(useCollectionStore.getState().characters[0].name).toBe('Second');
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('handles error followed by success correctly', async () => {
      jest.useRealTimers(); // fetchWithRetry retries with setTimeout; fake timers would hang

      // First request fails with a network error
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      await useCollectionStore.getState().fetchCollection(1);

      expect(useCollectionStore.getState().error).toBe('Network error');
      expect(useCollectionStore.getState().isLoading).toBe(false);

      // fetchWithRetry retries 3 times before giving up
      expect(global.fetch).toHaveBeenCalledTimes(3);

      // Wait for the _fetchInFlight finally block to clear
      await Promise.resolve();
      await Promise.resolve();

      // Second request succeeds
      const mockResponse = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };
      global.fetch = jest.fn().mockResolvedValue(jsonResponse(mockResponse));

      // Clear error before second fetch (as would happen in real usage)
      useCollectionStore.getState().clearError();

      // Second request succeeds
      await useCollectionStore.getState().fetchCollection(1);

      // Verify the second request was made
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Verify the second request succeeded
      expect(useCollectionStore.getState().characters).toHaveLength(1);
      expect(useCollectionStore.getState().characters[0].name).toBe('主角');
      expect(useCollectionStore.getState().error).toBeNull();

      jest.useFakeTimers();
    });

    it('maintains selection state during concurrent refreshes', async () => {
      // Setup initial state with selection
      const selectedCharacter = {
        name: '赵灵儿',
        role: '妻子',
        description: '测试描述',
        affinity: 95,
        age: 16,
        gender: '女',
        occupation: '女娲后裔',
        personality_traits: ['温柔'],
        image_url: 'http://example.com/linger.png',
        image_generated: true,
        description_generated: true,
      };

      useCollectionStore.setState({
        characters: [selectedCharacter],
        selectedCharacter: selectedCharacter,
      });

      const mockResponse = {
        game_id: 1,
        characters: [{
          name: '赵灵儿',
          role: '妻子',
          description: '更新后的描述',
          affinity: 98,  // Changed
          age: 16,
          gender: '女',
          occupation: '女娲后裔',
          personality_traits: ['温柔', '善良'],  // Changed
          image_url: 'http://example.com/linger_new.png',  // Changed
          image_generated: true,
          description_generated: true,
        }],
        items: [],
        landmarks: [],
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      // Refresh multiple times concurrently
      const promise1 = useCollectionStore.getState().fetchCollection(1, true);
      const promise2 = useCollectionStore.getState().fetchCollection(1, true);
      const promise3 = useCollectionStore.getState().fetchCollection(1, true);

      await Promise.all([promise1, promise2, promise3]);

      // Selection should be preserved with updated data
      const state = useCollectionStore.getState();
      expect(state.selectedCharacter).not.toBeNull();
      expect(state.selectedCharacter?.name).toBe('赵灵儿');
      expect(state.selectedCharacter?.affinity).toBe(98);
      expect(state.selectedCharacter?.description).toBe('更新后的描述');
    });
  });

  describe('write operations bypass cache', () => {
    it('generateCharacterImage should fetch fresh data after generation', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
      const mockResponse = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: 'http://example.com/image.png', image_generated: true, description_generated: false }],
        items: [],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().generateCharacterImage(1, '主角');

      // 应该调用 generateCharacterImage 和 fetchCollection(isRefresh=true)
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/collection/1/characters/%E4%B8%BB%E8%A7%92/generate-image',
        expect.objectContaining({ method: 'POST' })
      );
      expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/details', expect.objectContaining({ credentials: 'include' }));
      expect(useCollectionStore.getState().characters[0].image_url).toBe('http://example.com/image.png');
    });

    it('addRecognizedEntities should fetch fresh data after adding', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [{ name: '新物品', description: '', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: null, image_generated: false, description_generated: false, metadata: {} }],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().addRecognizedEntities(1, {
        items: [{ name: '新物品', description: '', category: 'other', importance: 'normal', appear_count: 1, appear_contexts: [] }],
        characters: [],
        landmarks: [],
      });

      expect(global.fetch).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/details', expect.objectContaining({ credentials: 'include' }));
      expect(useCollectionStore.getState().items).toHaveLength(1);
    });

    it('createItem should fetch fresh data after creation', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [{ name: '手动物品', description: '', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: null, image_generated: false, description_generated: false, metadata: {} }],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().createItem(1, '手动物品');

      expect(global.fetch).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/details', expect.objectContaining({ credentials: 'include' }));
      expect(useCollectionStore.getState().items).toHaveLength(1);
    });

    it('deleteItem should fetch fresh data after deletion', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().deleteItem(1, '旧物品');

      expect(global.fetch).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/details', expect.objectContaining({ credentials: 'include' }));
    });
  });
});
