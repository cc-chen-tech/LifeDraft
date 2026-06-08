import { render, screen, waitFor } from '@testing-library/react';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

describe('CollectionPanel auto collection UI', () => {
  beforeEach(() => {
    useCollectionStore.setState({
      characters: [],
      items: [],
      landmarks: [],
      isLoading: false,
      isRefreshing: false,
      activeTab: 'items',
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: null,
      isRecognizing: false,
      recognizedEntities: null,
      isDeleting: false,
      deletingEntity: null,
    });
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  it('renders newly auto-collected story items in the item tab after mount', async () => {
    const initialCollection = {
      game_id: 515,
      characters: [
        {
          name: '陈晓雨',
          role: '核心同事',
          description: '主角的产品同事。',
          affinity: 65,
          age: null,
          gender: null,
          occupation: '产品经理',
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
    const recognizedEntities = {
      characters: [],
      items: [
        {
          name: 'SemantLink API文档U盘',
          description: '第4周推进AI协作工具时反复查阅的技术资料。',
          category: 'document',
          importance: 'critical',
          appear_count: 2,
          appear_contexts: ['第4周周一：梳理接口限制'],
        },
      ],
      landmarks: [],
    };
    const refreshedCollection = {
      ...initialCollection,
      items: [
        {
          name: 'SemantLink API文档U盘',
          description: '第4周推进AI协作工具时反复查阅的技术资料。',
          importance: 'critical',
          category: 'document',
          acquired_week: 4,
          acquired_context: '第4周周一：梳理接口限制',
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
      .mockResolvedValueOnce(jsonResponse(initialCollection))
      .mockResolvedValueOnce(jsonResponse(recognizedEntities))
      .mockResolvedValueOnce(jsonResponse({
        message: '成功添加 1 个物品, 0 个人物, 0 个地点',
        added_items: ['SemantLink API文档U盘'],
        added_characters: [],
        added_landmarks: [],
      }))
      .mockResolvedValueOnce(jsonResponse(refreshedCollection));

    render(<CollectionPanel gameId={515} />);

    expect(await screen.findByText('SemantLink API文档U盘')).toBeInTheDocument();
    expect(screen.getByText(/物品 \(1\)/)).toBeInTheDocument();
    expect(screen.queryByText('暂无物品记录')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/collection/515/add-entities'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('SemantLink API文档U盘'),
        }),
      );
    });
  });
});
