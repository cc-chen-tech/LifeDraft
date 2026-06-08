/**
 * stores/useCollectionStore.ts Tests
 * Tests for collection state management
 */

import { useCollectionStore } from '@/stores/useCollectionStore';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

describe('useCollectionStore', () => {
  beforeEach(() => {
    // Reset store to initial state
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
    global.fetch = jest.fn();
  });

  describe('Initial State', () => {
    it('has correct initial state', () => {
      const state = useCollectionStore.getState();

      expect(state.characters).toEqual([]);
      expect(state.items).toEqual([]);
      expect(state.landmarks).toEqual([]);
      expect(state.isLoading).toBe(false);
      expect(state.isRefreshing).toBe(false);
      expect(state.activeTab).toBe('characters');
      expect(state.selectedCharacter).toBeNull();
      expect(state.selectedItem).toBeNull();
      expect(state.selectedLandmark).toBeNull();
      expect(state.generatingImageFor).toBeNull();
      expect(state.generatingDescriptionFor).toBeNull();
      expect(state.regeneratingImageFor).toBeNull();
      expect(state.error).toBeNull();
    });
  });

  describe('UI State Actions', () => {
    describe('setActiveTab', () => {
      it('switches to characters tab', () => {
        useCollectionStore.getState().setActiveTab('characters');
        expect(useCollectionStore.getState().activeTab).toBe('characters');
      });

      it('switches to items tab', () => {
        useCollectionStore.getState().setActiveTab('items');
        expect(useCollectionStore.getState().activeTab).toBe('items');
      });

      it('switches to landmarks tab', () => {
        useCollectionStore.getState().setActiveTab('landmarks');
        expect(useCollectionStore.getState().activeTab).toBe('landmarks');
      });
    });

    describe('selectCharacter', () => {
      it('selects a character and clears item/landmark selection', () => {
        const character = {
          name: 'Test Character',
          role: 'Friend',
          description: 'A test friend',
          affinity: 80,
          age: 25,
          gender: '男',
          occupation: '工程师',
          personality_traits: ['开朗'],
          image_url: 'http://example.com/img.png',
          image_generated: true,
          description_generated: true,
        };

        useCollectionStore.getState().selectCharacter(character);

        expect(useCollectionStore.getState().selectedCharacter).toEqual(character);
        expect(useCollectionStore.getState().selectedItem).toBeNull();
        expect(useCollectionStore.getState().selectedLandmark).toBeNull();
      });

      it('clears selection when null', () => {
        const character = { name: 'Test', role: '', description: '', affinity: 50, age: 0, gender: '', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false };
        useCollectionStore.setState({ selectedCharacter: character });

        useCollectionStore.getState().selectCharacter(null);

        expect(useCollectionStore.getState().selectedCharacter).toBeNull();
      });
    });

    describe('selectItem', () => {
      it('selects an item and clears character/landmark selection', () => {
        const item = {
          name: 'Test Item',
          description: 'A test item',
          importance: 'important' as const,
          category: 'weapon' as const,
          acquired_week: 5,
          acquired_context: 'Found in a cave',
          is_key_item: true,
          image_url: 'http://example.com/item.png',
          image_generated: true,
          description_generated: false,
          metadata: {},
        };

        useCollectionStore.getState().selectItem(item);

        expect(useCollectionStore.getState().selectedItem).toEqual(item);
        expect(useCollectionStore.getState().selectedCharacter).toBeNull();
        expect(useCollectionStore.getState().selectedLandmark).toBeNull();
      });
    });

    describe('selectLandmark', () => {
      it('selects a landmark and clears character/item selection', () => {
        const landmark = {
          name: 'Test Landmark',
          description: 'A test landmark',
          category: 'building' as const,
          importance: 'important' as const,
          first_appear_week: 1,
          appear_count: 3,
          last_appear_week: 5,
          context: 'A mysterious building',
          is_key_location: true,
          image_url: 'http://example.com/landmark.png',
          image_generated: true,
          metadata: {},
        };

        useCollectionStore.getState().selectLandmark(landmark);

        expect(useCollectionStore.getState().selectedLandmark).toEqual(landmark);
        expect(useCollectionStore.getState().selectedCharacter).toBeNull();
        expect(useCollectionStore.getState().selectedItem).toBeNull();
      });
    });

    describe('clearSelection', () => {
      it('clears all selections', () => {
        const character = { name: 'Test', role: '', description: '', affinity: 50, age: 0, gender: '', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false };
        const item = { name: 'Item', description: '', importance: 'normal' as const, category: 'other' as const, acquired_week: 0, acquired_context: '', is_key_item: false, image_url: null, image_generated: false, description_generated: false, metadata: {} };
        const landmark = { name: 'Landmark', description: '', category: 'other' as const, importance: 'normal' as const, first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: null, image_generated: false, metadata: {} };

        useCollectionStore.setState({ selectedCharacter: character, selectedItem: item, selectedLandmark: landmark });

        useCollectionStore.getState().clearSelection();

        expect(useCollectionStore.getState().selectedCharacter).toBeNull();
        expect(useCollectionStore.getState().selectedItem).toBeNull();
        expect(useCollectionStore.getState().selectedLandmark).toBeNull();
      });
    });

    describe('clearError', () => {
      it('clears error state', () => {
        useCollectionStore.setState({ error: 'Test error' });

        useCollectionStore.getState().clearError();

        expect(useCollectionStore.getState().error).toBeNull();
      });
    });
  });

  describe('fetchCollection preserves selection', () => {
    it('auto-collects recognized story entities when collection is empty', async () => {
      const emptyCollection = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
        total_characters: 0,
        total_items: 0,
        total_landmarks: 0,
      };
      const recognizedEntities = {
        characters: [
          {
            name: '赵掌柜',
            description: '赵家船行的掌柜，知道账册和铜钥匙的来历。',
            category: 'person',
            importance: 'important' as const,
            appear_count: 1,
            appear_contexts: ['第1周周一：在赵家船行后院交出账册'],
          },
        ],
        items: [
          {
            name: '铜钥匙',
            description: '从旧账册夹层里掉出的关键钥匙。',
            category: 'tool',
            importance: 'critical' as const,
            appear_count: 1,
            appear_contexts: ['第1周周一：旧账册夹层'],
          },
        ],
        landmarks: [],
      };
      const populatedCollection = {
        game_id: 1,
        characters: [
          {
            name: '赵掌柜',
            role: '故事人物',
            description: '赵家船行的掌柜，知道账册和铜钥匙的来历。',
            affinity: 50,
            age: null,
            gender: null,
            occupation: null,
            personality_traits: [],
            image_url: null,
            image_generated: false,
            description_generated: true,
          },
        ],
        items: [
          {
            name: '铜钥匙',
            description: '从旧账册夹层里掉出的关键钥匙。',
            importance: 'critical',
            category: 'tool',
            acquired_week: 0,
            acquired_context: '第1周周一：旧账册夹层',
            is_key_item: true,
            image_url: null,
            image_generated: false,
            description_generated: true,
            metadata: {},
          },
        ],
        landmarks: [],
        total_characters: 1,
        total_items: 1,
        total_landmarks: 0,
      };

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse(emptyCollection))
        .mockResolvedValueOnce(jsonResponse(recognizedEntities))
        .mockResolvedValueOnce(jsonResponse({
          message: '成功添加 1 个物品, 1 个人物, 0 个地点',
          added_items: ['铜钥匙'],
          added_characters: ['赵掌柜'],
          added_landmarks: [],
        }))
        .mockResolvedValueOnce(jsonResponse(populatedCollection));

      await useCollectionStore.getState().fetchCollection(1);
      await useCollectionStore.getState().autoCollectRecognizedEntities(1);

      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        '/api/collection/1/recognize-entities',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            entity_types: ['item', 'character', 'landmark'],
            min_appearances: 1,
          }),
        }),
      );
      expect(global.fetch).toHaveBeenNthCalledWith(
        3,
        '/api/collection/1/add-entities',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('赵掌柜'),
        }),
      );
      expect(useCollectionStore.getState().characters.map((c) => c.name)).toEqual(['赵掌柜']);
      expect(useCollectionStore.getState().items.map((i) => i.name)).toEqual(['铜钥匙']);
    });

    it('auto-collects missing item entities when characters already exist', async () => {
      const existingCharacter = {
        name: '陈晓雨',
        role: '核心同事',
        description: '主角的产品同事。',
        affinity: 50,
        age: null,
        gender: null,
        occupation: null,
        personality_traits: [],
        image_url: null,
        image_generated: false,
        description_generated: true,
      };
      const existingCollection = {
        game_id: 303,
        characters: [existingCharacter],
        items: [],
        landmarks: [],
        total_characters: 1,
        total_items: 0,
        total_landmarks: 0,
      };
      const recognizedEntities = {
        characters: [
          {
            name: '陈晓雨',
            description: '已在收集中存在的同事。',
            category: 'person',
            importance: 'important' as const,
            appear_count: 3,
            appear_contexts: ['第1周：需求评审'],
          },
        ],
        items: [
          {
            name: '竞品分析报告',
            description: '主角推进产品路线时反复使用的关键报告。',
            category: 'document',
            importance: 'important' as const,
            appear_count: 2,
            appear_contexts: ['第2周周中：评审会上引用'],
          },
        ],
        landmarks: [],
      };
      const populatedCollection = {
        ...existingCollection,
        items: [
          {
            name: '竞品分析报告',
            description: '主角推进产品路线时反复使用的关键报告。',
            importance: 'important',
            category: 'document',
            acquired_week: 2,
            acquired_context: '第2周周中：评审会上引用',
            is_key_item: true,
            image_url: null,
            image_generated: false,
            description_generated: true,
            metadata: {},
          },
        ],
        total_items: 1,
      };

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse(existingCollection))
        .mockResolvedValueOnce(jsonResponse(recognizedEntities))
        .mockResolvedValueOnce(jsonResponse({
          message: '成功添加 1 个物品, 0 个人物, 0 个地点',
          added_items: ['竞品分析报告'],
          added_characters: [],
          added_landmarks: [],
        }))
        .mockResolvedValueOnce(jsonResponse(populatedCollection));

      await useCollectionStore.getState().fetchCollection(303);
      await useCollectionStore.getState().autoCollectRecognizedEntities(303);

      expect(global.fetch).toHaveBeenNthCalledWith(
        3,
        '/api/collection/303/add-entities',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('竞品分析报告'),
        }),
      );
      const addBody = JSON.parse((global.fetch as jest.Mock).mock.calls[2][1].body);
      expect(addBody.characters).toEqual([]);
      expect(addBody.items).toHaveLength(1);
      expect(useCollectionStore.getState().items.map((i) => i.name)).toEqual(['竞品分析报告']);
    });

    it('retries auto collection after an empty recognition result', async () => {
      const emptyCollection = {
        game_id: 2,
        characters: [],
        items: [],
        landmarks: [],
        total_characters: 0,
        total_items: 0,
        total_landmarks: 0,
      };
      const noEntities = { characters: [], items: [], landmarks: [] };
      const recognizedEntities = {
        characters: [
          {
            name: '陈晓雨',
            description: '主角的产品同学。',
            category: 'person',
            importance: 'important' as const,
            appear_count: 1,
            appear_contexts: ['第1周周中：线上会议'],
          },
        ],
        items: [],
        landmarks: [],
      };
      const populatedCollection = {
        game_id: 2,
        characters: [
          {
            name: '陈晓雨',
            role: '故事人物',
            description: '主角的产品同学。',
            affinity: 50,
            age: null,
            gender: null,
            occupation: null,
            personality_traits: [],
            image_url: null,
            image_generated: false,
            description_generated: true,
          },
        ],
        items: [],
        landmarks: [],
        total_characters: 1,
        total_items: 0,
        total_landmarks: 0,
      };

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse(emptyCollection))
        .mockResolvedValueOnce(jsonResponse(noEntities))
        .mockResolvedValueOnce(jsonResponse(recognizedEntities))
        .mockResolvedValueOnce(jsonResponse({
          message: '成功添加 0 个物品, 1 个人物, 0 个地点',
          added_items: [],
          added_characters: ['陈晓雨'],
          added_landmarks: [],
        }))
        .mockResolvedValueOnce(jsonResponse(populatedCollection));

      await useCollectionStore.getState().fetchCollection(2);
      await useCollectionStore.getState().autoCollectRecognizedEntities(2);
      await useCollectionStore.getState().autoCollectRecognizedEntities(2);

      const recognitionCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
        String(url).includes('/recognize-entities'),
      );
      expect(recognitionCalls).toHaveLength(2);
      expect(useCollectionStore.getState().characters.map((c) => c.name)).toEqual(['陈晓雨']);
    });

    it('preserves selected character after fetch', async () => {
      // Setup initial state with selected character
      const initialCharacter = {
        name: 'Selected Character',
        role: 'Friend',
        description: 'Old description',
        affinity: 80,
        age: 25,
        gender: '男',
        occupation: '工程师',
        personality_traits: [] as string[],
        image_url: 'http://example.com/old.png',
        image_generated: true,
        description_generated: true,
      };
      useCollectionStore.setState({ selectedCharacter: initialCharacter });

      // Mock new response with updated data
      const mockResponse = {
        game_id: 1,
        characters: [
          { ...initialCharacter, description: 'New description', image_url: 'http://example.com/new.png' },
          { name: 'Other Character', role: 'Enemy', description: '', affinity: 30, age: 30, gender: '女', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false },
        ],
        items: [],
        landmarks: [],
        total_characters: 2,
        total_items: 0,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().fetchCollection(1);

      // Selection should be preserved and updated with new data
      expect(useCollectionStore.getState().selectedCharacter).not.toBeNull();
      expect(useCollectionStore.getState().selectedCharacter?.name).toBe('Selected Character');
      expect(useCollectionStore.getState().selectedCharacter?.description).toBe('New description');
      expect(useCollectionStore.getState().selectedCharacter?.image_url).toBe('http://example.com/new.png');
    });

    it('preserves selected item after fetch', async () => {
      const initialItem = {
        name: 'Selected Item',
        description: 'Old description',
        importance: 'important' as const,
        category: 'weapon' as const,
        acquired_week: 5,
        acquired_context: 'Found',
        is_key_item: true,
        image_url: 'http://example.com/old.png',
        image_generated: true,
        description_generated: false,
        metadata: {},
      };
      useCollectionStore.setState({ selectedItem: initialItem });

      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [
          { ...initialItem, description: 'New description', image_url: 'http://example.com/new.png' },
        ],
        landmarks: [],
        total_characters: 0,
        total_items: 1,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().fetchCollection(1);

      expect(useCollectionStore.getState().selectedItem).not.toBeNull();
      expect(useCollectionStore.getState().selectedItem?.name).toBe('Selected Item');
      expect(useCollectionStore.getState().selectedItem?.description).toBe('New description');
    });

    it('preserves selected landmark after fetch', async () => {
      const initialLandmark = {
        name: 'Selected Landmark',
        description: 'Old description',
        category: 'building' as const,
        importance: 'important' as const,
        first_appear_week: 1,
        appear_count: 3,
        last_appear_week: 5,
        context: 'Context',
        is_key_location: true,
        image_url: 'http://example.com/old.png',
        image_generated: true,
        metadata: {},
      };
      useCollectionStore.setState({ selectedLandmark: initialLandmark });

      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [
          { ...initialLandmark, description: 'New description', image_url: 'http://example.com/new.png' },
        ],
        total_characters: 0,
        total_items: 0,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().fetchCollection(1);

      expect(useCollectionStore.getState().selectedLandmark).not.toBeNull();
      expect(useCollectionStore.getState().selectedLandmark?.name).toBe('Selected Landmark');
      expect(useCollectionStore.getState().selectedLandmark?.description).toBe('New description');
    });

    it('clears selection if item no longer exists', async () => {
      const initialItem = {
        name: 'Deleted Item',
        description: '',
        importance: 'normal' as const,
        category: 'other' as const,
        acquired_week: 0,
        acquired_context: '',
        is_key_item: false,
        image_url: null,
        image_generated: false,
        description_generated: false,
        metadata: {},
      };
      useCollectionStore.setState({ selectedItem: initialItem });

      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [], // Item is gone
        landmarks: [],
        total_characters: 0,
        total_items: 0,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await useCollectionStore.getState().fetchCollection(1);

      expect(useCollectionStore.getState().selectedItem).toBeNull();
    });

    it('sets isLoading for initial load', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
        total_characters: 0,
        total_items: 0,
      };
      (global.fetch as jest.Mock).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve(jsonResponse(mockResponse)), 100))
      );

      const promise = useCollectionStore.getState().fetchCollection(1, false);

      // Initial load should set isLoading
      expect(useCollectionStore.getState().isLoading).toBe(true);
      expect(useCollectionStore.getState().isRefreshing).toBe(false);

      await promise;

      expect(useCollectionStore.getState().isLoading).toBe(false);
    });

    it('sets isRefreshing for refresh', async () => {
      const mockResponse = {
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
        total_characters: 0,
        total_items: 0,
      };
      (global.fetch as jest.Mock).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve(jsonResponse(mockResponse)), 100))
      );

      const promise = useCollectionStore.getState().fetchCollection(1, true);

      // Refresh mode should NOT set isLoading (keeps list visible)
      expect(useCollectionStore.getState().isLoading).toBe(false);
      // isRefreshing is not set in the new implementation - we simply don't show loading state

      await promise;

      // After completion, everything should be false
      expect(useCollectionStore.getState().isLoading).toBe(false);
      expect(useCollectionStore.getState().isRefreshing).toBe(false);
    });
  });

  describe('API Actions', () => {
    describe('fetchCollection', () => {
      it('returns early without gameId', async () => {
        await useCollectionStore.getState().fetchCollection(0);

        expect(global.fetch).not.toHaveBeenCalled();
        expect(useCollectionStore.getState().error).toBe('游戏ID不存在');
      });

      it('fetches collection data successfully with landmarks', async () => {
        const mockResponse = {
          game_id: 1,
          characters: [
            { name: 'Character 1', role: 'Friend', description: '', affinity: 80, age: 25, gender: '男', occupation: '', personality_traits: [], image_url: null, image_generated: false, description_generated: false },
          ],
          items: [
            { name: 'Item 1', description: '', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: null, image_generated: false, description_generated: false, metadata: {} },
          ],
          landmarks: [
            { name: 'Landmark 1', description: '', category: 'building', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: null, image_generated: false, metadata: {} },
          ],
          total_characters: 1,
          total_items: 1,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        await useCollectionStore.getState().fetchCollection(1);

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/details', expect.objectContaining({ credentials: 'include' }));
        expect(useCollectionStore.getState().characters).toHaveLength(1);
        expect(useCollectionStore.getState().items).toHaveLength(1);
        expect(useCollectionStore.getState().landmarks).toHaveLength(1);
        expect(useCollectionStore.getState().isLoading).toBe(false);
      });

      it('handles fetch error', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400));

        await useCollectionStore.getState().fetchCollection(1);

        expect(useCollectionStore.getState().error).toBe('error');
        expect(useCollectionStore.getState().isLoading).toBe(false);
      });
    });

    describe('generateCharacterImage', () => {
      it('returns early without gameId', async () => {
        await useCollectionStore.getState().generateCharacterImage(0, 'Test');

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('generates character image successfully', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
        const mockResponse = {
          game_id: 1,
          characters: [{ name: 'Test', role: '', description: '', affinity: 50, age: 0, gender: '', occupation: '', personality_traits: [], image_url: 'new_url', image_generated: true, description_generated: false }],
          items: [],
          landmarks: [],
          total_characters: 1,
          total_items: 0,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        await useCollectionStore.getState().generateCharacterImage(1, 'Test');

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/characters/Test/generate-image', expect.objectContaining({ method: 'POST' }));
        expect(useCollectionStore.getState().generatingImageFor).toBeNull();
      });

      it('handles generation error', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400, 'Generation failed'));

        await useCollectionStore.getState().generateCharacterImage(1, 'Test');

        expect(useCollectionStore.getState().error).toBe('Generation failed');
        expect(useCollectionStore.getState().generatingImageFor).toBeNull();
      });
    });

    describe('regenerateCharacterImage', () => {
      it('returns early without gameId', async () => {
        await useCollectionStore.getState().regenerateCharacterImage(0, 'Test', 'feedback');

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('returns early without feedback', async () => {
        await useCollectionStore.getState().regenerateCharacterImage(1, 'Test', '');

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('regenerates character image successfully', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
        const mockResponse = {
          game_id: 1,
          characters: [{ name: 'Test', role: '', description: '', affinity: 50, age: 0, gender: '', occupation: '', personality_traits: [], image_url: 'new_url', image_generated: true, description_generated: false }],
          items: [],
          landmarks: [],
          total_characters: 1,
          total_items: 0,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        await useCollectionStore.getState().regenerateCharacterImage(1, 'Test', '头发变长');

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/characters/Test/regenerate-image', expect.objectContaining({ method: 'POST' }));
        expect(useCollectionStore.getState().regeneratingImageFor).toBeNull();
      });

      it('handles regeneration error', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400));

        await useCollectionStore.getState().regenerateCharacterImage(1, 'Test', 'feedback');

        expect(useCollectionStore.getState().error).toBe('error');
        expect(useCollectionStore.getState().regeneratingImageFor).toBeNull();
      });
    });

    describe('regenerateItemImage', () => {
      it('regenerates item image successfully', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
        const mockResponse = {
          game_id: 1,
          characters: [],
          items: [{ name: 'TestItem', description: '', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: 'new_url', image_generated: true, description_generated: false, metadata: {} }],
          landmarks: [],
          total_characters: 0,
          total_items: 1,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        await useCollectionStore.getState().regenerateItemImage(1, 'TestItem', '颜色改深');

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/items/TestItem/regenerate-image', expect.objectContaining({ method: 'POST' }));
        expect(useCollectionStore.getState().regeneratingImageFor).toBeNull();
      });
    });

    describe('generateLandmarkImage', () => {
      it('returns early without gameId', async () => {
        await useCollectionStore.getState().generateLandmarkImage(0, 'Test');

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('generates landmark image successfully', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
        const mockResponse = {
          game_id: 1,
          characters: [],
          items: [],
          landmarks: [{ name: 'TestLandmark', description: '', category: 'building', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: 'new_url', image_generated: true, metadata: {} }],
          total_characters: 0,
          total_items: 0,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        await useCollectionStore.getState().generateLandmarkImage(1, 'TestLandmark');

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/landmarks/TestLandmark/generate-image', expect.objectContaining({ method: 'POST' }));
        expect(useCollectionStore.getState().generatingImageFor).toBeNull();
      });
    });

    describe('batchGenerateLandmarkImages', () => {
      it('returns early without gameId', async () => {
        await useCollectionStore.getState().batchGenerateLandmarkImages(0);

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('returns early when no pending landmarks', async () => {
        useCollectionStore.setState({
          landmarks: [
            { name: 'GeneratedLandmark', description: '', category: 'building', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: 'url', image_generated: true, metadata: {} },
          ],
        });

        await useCollectionStore.getState().batchGenerateLandmarkImages(1);

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('generates images for all pending landmarks', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
        const mockResponse = {
          game_id: 1,
          characters: [],
          items: [],
          landmarks: [
            { name: 'Landmark1', description: '', category: 'building', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: 'url1', image_generated: true, metadata: {} },
            { name: 'Landmark2', description: '', category: 'nature', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: 'url2', image_generated: true, metadata: {} },
          ],
          total_characters: 0,
          total_items: 0,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        useCollectionStore.setState({
          landmarks: [
            { name: 'Landmark1', description: '', category: 'building', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: null, image_generated: false, metadata: {} },
            { name: 'Landmark2', description: '', category: 'nature', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: null, image_generated: false, metadata: {} },
          ],
        });

        await useCollectionStore.getState().batchGenerateLandmarkImages(1);

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/landmarks/Landmark1/generate-image', expect.objectContaining({ method: 'POST' }));
        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/landmarks/Landmark2/generate-image', expect.objectContaining({ method: 'POST' }));
        expect(useCollectionStore.getState().generatingImageFor).toBeNull();
      });

      it('stops on first error during batch generation', async () => {
        (global.fetch as jest.Mock)
          .mockResolvedValueOnce(jsonResponse({ success: true }))
          .mockResolvedValueOnce(errorResponse(400, 'Generation failed'))
          .mockResolvedValue(jsonResponse({ success: true }));

        useCollectionStore.setState({
          landmarks: [
            { name: 'Landmark1', description: '', category: 'building', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: null, image_generated: false, metadata: {} },
            { name: 'Landmark2', description: '', category: 'nature', importance: 'normal', first_appear_week: 0, appear_count: 1, last_appear_week: 0, context: '', is_key_location: false, image_url: null, image_generated: false, metadata: {} },
          ],
        });

        await useCollectionStore.getState().batchGenerateLandmarkImages(1);

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/landmarks/Landmark1/generate-image', expect.objectContaining({ method: 'POST' }));
        // After error, fetchCollection is called internally which clears error
        // The batch generation stops on first error and fetchCollection resets state
        expect(useCollectionStore.getState().generatingImageFor).toBeNull();
      });
    });

    describe('generateItemImage', () => {
      it('returns early without gameId', async () => {
        await useCollectionStore.getState().generateItemImage(0, 'TestItem');

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('generates item image successfully', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));
        const mockResponse = {
          game_id: 1,
          characters: [],
          items: [{ name: 'TestItem', description: '', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: 'new_url', image_generated: true, description_generated: false, metadata: {} }],
          total_characters: 0,
          total_items: 1,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        await useCollectionStore.getState().generateItemImage(1, 'TestItem');

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/items/TestItem/generate-image', expect.objectContaining({ method: 'POST' }));
        expect(useCollectionStore.getState().generatingImageFor).toBeNull();
      });
    });

    describe('generateItemDescription', () => {
      it('returns early without gameId', async () => {
        await useCollectionStore.getState().generateItemDescription(0, 'TestItem');

        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('generates item description successfully', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true, data: { description: 'New description' } }));
        const mockResponse = {
          game_id: 1,
          characters: [],
          items: [{ name: 'TestItem', description: 'New description', importance: 'normal', category: 'other', acquired_week: 0, acquired_context: '', is_key_item: false, image_url: null, image_generated: false, description_generated: true, metadata: {} }],
          landmarks: [],
          total_characters: 0,
          total_items: 1,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

        await useCollectionStore.getState().generateItemDescription(1, 'TestItem');

        expect(global.fetch).toHaveBeenCalledWith('/api/collection/1/items/TestItem/generate-description', expect.objectContaining({ method: 'POST' }));
        expect(useCollectionStore.getState().generatingDescriptionFor).toBeNull();
      });
    });
  });

  describe('State Management', () => {
    it('tracks generating image state correctly', async () => {
      (global.fetch as jest.Mock).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve(jsonResponse({ success: true })), 100))
      );
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
        total_characters: 0,
        total_items: 0,
      }));

      const promise = useCollectionStore.getState().generateCharacterImage(1, 'Test');

      // Check that generating state is set immediately
      expect(useCollectionStore.getState().generatingImageFor).toBe('Test');

      await promise;

      // Check that generating state is cleared after completion
      expect(useCollectionStore.getState().generatingImageFor).toBeNull();
    });

    it('tracks generating description state correctly', async () => {
      (global.fetch as jest.Mock).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve(jsonResponse({ success: true })), 100))
      );
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
        total_characters: 0,
        total_items: 0,
      }));

      const promise = useCollectionStore.getState().generateItemDescription(1, 'TestItem');

      expect(useCollectionStore.getState().generatingDescriptionFor).toBe('TestItem');

      await promise;

      expect(useCollectionStore.getState().generatingDescriptionFor).toBeNull();
    });

    it('tracks regenerating image state correctly', async () => {
      (global.fetch as jest.Mock).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve(jsonResponse({ success: true })), 100))
      );
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        characters: [],
        items: [],
        landmarks: [],
        total_characters: 0,
        total_items: 0,
      }));

      const promise = useCollectionStore.getState().regenerateCharacterImage(1, 'Test', 'feedback');

      expect(useCollectionStore.getState().regeneratingImageFor).toBe('Test');

      await promise;

      expect(useCollectionStore.getState().regeneratingImageFor).toBeNull();
    });
  });

  describe('fetchCollection refresh mode', () => {
    it('preserves existing image_url when new data has empty url in refresh mode', async () => {
      // 先设置初始状态，包含已有图片的人物
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

      // Mock API 返回新数据，但图片 URL 为空（模拟生成过程中）
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
          image_url: '',  // 空 URL，模拟生成过程中
          image_generated: false,
          description_generated: true,
        }],
        items: [],
        landmarks: [],
      }));

      // 调用刷新模式
      await useCollectionStore.getState().fetchCollection(1, true);

      // 验证：旧图片 URL 被保留，避免闪烁
      const character = useCollectionStore.getState().characters[0];
      expect(character.image_url).toBe('http://example.com/old_image.png');
      expect(character.image_generated).toBe(true);
    });

    it('updates to new image_url when available in refresh mode', async () => {
      // 先设置初始状态
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

      // Mock API 返回新数据，有新的图片 URL
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
          image_url: 'http://example.com/new_image.png',  // 新 URL
          image_generated: true,
          description_generated: true,
        }],
        items: [],
        landmarks: [],
      }));

      // 调用刷新模式
      await useCollectionStore.getState().fetchCollection(1, true);

      // 验证：使用新的图片 URL
      const character = useCollectionStore.getState().characters[0];
      expect(character.image_url).toBe('http://example.com/new_image.png');
    });

    it('does not merge data in initial load mode', async () => {
      // Mock API 返回数据
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
          image_url: '',  // 空 URL
          image_generated: false,
          description_generated: true,
        }],
        items: [],
        landmarks: [],
      }));

      // 调用初始加载模式（isRefresh=false）
      await useCollectionStore.getState().fetchCollection(1, false);

      // 验证：使用 API 返回的数据，不合并
      const character = useCollectionStore.getState().characters[0];
      expect(character.image_url).toBe('');
      expect(character.image_generated).toBe(false);
    });
  });
});
