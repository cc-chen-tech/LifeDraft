/**
 * useCollectionStore 缓存机制测试
 *
 * 验证 fetchCollection 的短时缓存行为：
 * 1. 30 秒内重复调用只发 1 次请求
 * 2. isRefresh=true 时绕过缓存
 * 3. 写操作后的强制刷新能正常获取新数据
 */

import { useCollectionStore } from '@/stores/useCollectionStore';
import api from '@/lib/api';

jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    collection: {
      get: jest.fn(),
      generateCharacterImage: jest.fn(),
      generateItemImage: jest.fn(),
      generateLandmarkImage: jest.fn(),
      generateCharacterDescription: jest.fn(),
      generateItemDescription: jest.fn(),
      generateLandmarkDescription: jest.fn(),
      regenerateCharacterImage: jest.fn(),
      regenerateItemImage: jest.fn(),
      addEntities: jest.fn(),
      createItem: jest.fn(),
      deleteItem: jest.fn(),
      deleteCharacter: jest.fn(),
      deleteLandmark: jest.fn(),
    },
  },
}));

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
  });

  describe('fetchCollection cache behavior', () => {
    it('should call api.collection.get on first fetch', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };
      (api.collection.get as jest.Mock).mockResolvedValue(mockResponse);

      await useCollectionStore.getState().fetchCollection(1);

      expect(api.collection.get).toHaveBeenCalledTimes(1);
      expect(api.collection.get).toHaveBeenCalledWith(1);
    });

    it('should use cache for repeated fetch within 30 seconds', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false }],
        items: [],
        landmarks: [],
      };
      (api.collection.get as jest.Mock).mockResolvedValue(mockResponse);

      // 第一次请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(api.collection.get).toHaveBeenCalledTimes(1);

      // 第二次请求（在缓存有效期内）
      await useCollectionStore.getState().fetchCollection(1);
      // 仍然只调用 1 次
      expect(api.collection.get).toHaveBeenCalledTimes(1);

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
      (api.collection.get as jest.Mock)
        .mockResolvedValueOnce(mockResponse1)
        .mockResolvedValueOnce(mockResponse2);

      // 第一次普通请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(api.collection.get).toHaveBeenCalledTimes(1);
      expect(useCollectionStore.getState().characters).toHaveLength(1);

      // 强制刷新
      await useCollectionStore.getState().fetchCollection(1, true);
      expect(api.collection.get).toHaveBeenCalledTimes(2);
      expect(useCollectionStore.getState().characters).toHaveLength(2);
    });

    it('should call api again after cache expires', async () => {
      jest.useFakeTimers();
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };
      (api.collection.get as jest.Mock).mockResolvedValue(mockResponse);

      // 第一次请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(api.collection.get).toHaveBeenCalledTimes(1);

      // 快进 31 秒，超过缓存有效期
      jest.advanceTimersByTime(31000);

      // 再次请求
      await useCollectionStore.getState().fetchCollection(1);
      expect(api.collection.get).toHaveBeenCalledTimes(2);

      jest.useRealTimers();
    });
  });

  describe('write operations bypass cache', () => {
    it('generateCharacterImage should fetch fresh data after generation', async () => {
      (api.collection.generateCharacterImage as jest.Mock).mockResolvedValue({ success: true });
      const mockResponse = {
        game_id: 1,
        characters: [{ name: '主角', role: '主角', description: '', affinity: 100, age: 20, gender: '男', occupation: '', personality_traits: [], image_url: 'http://example.com/image.png', image_generated: true, description_generated: false }],
        items: [],
        landmarks: [],
      };
      (api.collection.get as jest.Mock).mockResolvedValue(mockResponse);

      await useCollectionStore.getState().generateCharacterImage(1, '主角');

      // 应该调用 generateCharacterImage 和 fetchCollection(isRefresh=true)
      expect(api.collection.generateCharacterImage).toHaveBeenCalledWith(1, '主角');
      expect(api.collection.get).toHaveBeenCalledWith(1);
      expect(useCollectionStore.getState().characters[0].image_url).toBe('http://example.com/image.png');
    });

    it('addRecognizedEntities should fetch fresh data after adding', async () => {
      (api.collection.addEntities as jest.Mock).mockResolvedValue({ success: true });
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [{ name: '新物品', description: '', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: null, image_generated: false, description_generated: false, metadata: {} }],
        landmarks: [],
      };
      (api.collection.get as jest.Mock).mockResolvedValue(mockResponse);

      await useCollectionStore.getState().addRecognizedEntities(1, {
        items: [{ name: '新物品', description: '', category: 'other', importance: 'normal', appear_count: 1, appear_contexts: [] }],
        characters: [],
        landmarks: [],
      });

      expect(api.collection.addEntities).toHaveBeenCalled();
      expect(api.collection.get).toHaveBeenCalledWith(1);
      expect(useCollectionStore.getState().items).toHaveLength(1);
    });

    it('createItem should fetch fresh data after creation', async () => {
      (api.collection.createItem as jest.Mock).mockResolvedValue({ success: true });
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [{ name: '手动物品', description: '', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: null, image_generated: false, description_generated: false, metadata: {} }],
        landmarks: [],
      };
      (api.collection.get as jest.Mock).mockResolvedValue(mockResponse);

      await useCollectionStore.getState().createItem(1, '手动物品');

      expect(api.collection.createItem).toHaveBeenCalled();
      expect(api.collection.get).toHaveBeenCalledWith(1);
      expect(useCollectionStore.getState().items).toHaveLength(1);
    });

    it('deleteItem should fetch fresh data after deletion', async () => {
      (api.collection.deleteItem as jest.Mock).mockResolvedValue({ success: true });
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
      };
      (api.collection.get as jest.Mock).mockResolvedValue(mockResponse);

      await useCollectionStore.getState().deleteItem(1, '旧物品');

      expect(api.collection.deleteItem).toHaveBeenCalled();
      expect(api.collection.get).toHaveBeenCalledWith(1);
    });
  });
});
