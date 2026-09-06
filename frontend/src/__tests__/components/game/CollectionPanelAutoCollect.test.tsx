import { render, screen, waitFor } from '@testing-library/react';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

describe('CollectionPanel collection hydration UI', () => {
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

  it('does not auto-add recognition results during initial mount', async () => {
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
    (global.fetch as jest.Mock).mockResolvedValueOnce(jsonResponse(initialCollection));

    render(<CollectionPanel gameId={515} />);

    expect(await screen.findByText('暂无物品记录')).toBeInTheDocument();
    expect(screen.getByText(/物品 \(0\)/)).toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });
  });

  it('does not auto-add story characters when other collections already contain entries', async () => {
    useCollectionStore.setState({ activeTab: 'characters' });

    const initialCollection = {
      game_id: 516,
      characters: [
        {
          name: '林见微',
          role: '主角',
          description: '当前游戏主角。',
          affinity: 100,
          age: null,
          gender: null,
          occupation: '产品经理',
          personality_traits: [],
          image_url: null,
          image_generated: false,
          description_generated: true,
        },
      ],
      items: [
        {
          name: '旧账本',
          description: '已经收集过的线索。',
          importance: 'important',
          category: 'document',
          acquired_week: 1,
          acquired_context: '开场故事',
          is_key_item: true,
          image_url: null,
          image_generated: false,
          description_generated: true,
          metadata: {},
        },
      ],
      landmarks: [
        {
          name: '苏州贸易公司',
          description: '已经收集过的地点。',
          importance: 'important',
          first_visited_week: 1,
          visit_count: 1,
          related_events: [],
          image_url: null,
          image_generated: false,
          description_generated: true,
          metadata: {},
        },
      ],
      total_characters: 1,
      total_items: 1,
      total_landmarks: 1,
    };
    (global.fetch as jest.Mock).mockResolvedValueOnce(jsonResponse(initialCollection));

    render(<CollectionPanel gameId={516} />);

    expect(await screen.findByText('林见微')).toBeInTheDocument();
    expect(screen.getByText(/人物 \(1\)/)).toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });
  });
});
