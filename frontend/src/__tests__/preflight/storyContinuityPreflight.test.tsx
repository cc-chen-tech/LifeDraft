import { act, renderHook } from '@testing-library/react';
import { handleEventComplete, handleStatusUpdate, type EventHandlers } from '@/hooks/game/eventUtils';
import { useHistoryViewer } from '@/hooks/game/useHistoryViewer';
import type { Phase } from '@/hooks/game/usePhaseManager';
import { useCollectionStore } from '@/stores/useCollectionStore';
import { useGameStore } from '@/stores/useGameStore';
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
      recognizeEntities: jest.fn(),
      addEntities: jest.fn(),
      createItem: jest.fn(),
      deleteItem: jest.fn(),
      deleteCharacter: jest.fn(),
      deleteLandmark: jest.fn(),
    },
  },
}));

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(),
  },
}));

function createHandlers(): EventHandlers {
  return {
    setStoryText: jest.fn(),
    setOptions: jest.fn(),
    setCurrentEvent: jest.fn(),
    setPhase: jest.fn(),
    setGameOver: jest.fn(),
    setRoundSummary: jest.fn(),
    setProcessing: jest.fn(),
    setConnectionStatus: jest.fn(),
    appendStoryText: jest.fn(),
    generatingRef: { current: true },
  };
}

describe('story continuity preflight', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCollectionStore.setState({
      characters: [],
      items: [],
      landmarks: [],
      isLoading: false,
      isRefreshing: false,
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      error: null,
    });
  });

  it('replaces the active story after a retry status instead of keeping stale streamed text', () => {
    const handlers = createHandlers();
    const retryStory = '苏小二按住账册，低声提醒陆明先核对暗号。';

    (useGameStore.getState as jest.Mock)
      .mockReturnValueOnce({ setStoryText: jest.fn() })
      .mockReturnValue({ storyText: '账册被人翻开，这是旧的首轮 stream 内容。', currentEvent: null });

    handleStatusUpdate({ phase: 'retry' }, handlers.setProcessing);
    handleEventComplete(
      {
        event_description: retryStory,
        options: [{ text: '跟苏小二核对暗号' }, { text: '立刻去码头截人' }],
      },
      handlers,
    );

    expect(handlers.setStoryText).toHaveBeenCalledWith(retryStory);
    expect(handlers.setCurrentEvent).toHaveBeenCalledWith({
      story: retryStory,
      options: [{ text: '跟苏小二核对暗号' }, { text: '立刻去码头截人' }],
    });
    expect(handlers.setProcessing).toHaveBeenCalledWith(true, 'retrying');
  });

  it('keeps history display pinned while current story props change', async () => {
    const phaseRef = { current: 'generating' as Phase };
    const setOptions = jest.fn();
    const setHistorySceneImage = jest.fn();
    const playerState = {
      round_history: [
        {
          week: 3,
          round: 2,
          event_description: '码头边的对峙仍停在旧案账册被交出的瞬间。',
          story_continuation: '陆明选择留下核对账册暗号。',
          scene_image: {
            scene_id: 7,
            stage: 'event',
            image_url: '/scene-7.png',
            scene_description: '码头边的对峙',
            created_at: '2026-05-16T00:00:00Z',
          },
        },
      ],
    };

    const { result, rerender } = renderHook(
      ({ storyText }) =>
        useHistoryViewer({
          playerState,
          storyText,
          currentEvent: { story: storyText, options: [{ text: '当前选择' }] },
          phaseRef,
          setPhase: jest.fn(),
          setOptions,
          generatingRef: { current: false },
          gameId: 101,
          setHistorySceneImage,
        }),
      { initialProps: { storyText: '当前故事尚未更新' } },
    );

    await act(async () => {
      await result.current.handleSelectHistoryRound(0);
    });

    expect(result.current.displayText).toContain('码头边的对峙');
    expect(setHistorySceneImage).toHaveBeenCalledWith(
      expect.objectContaining({ week: 3, round_number: 2, stage: 'event' }),
    );

    rerender({ storyText: '当前故事已经更新，但历史视图保持不变' });

    expect(result.current.displayText).toContain('码头边的对峙');
    expect(result.current.displayText).not.toContain('当前故事已经更新');
  });

  it('preserves visible collection data and selected entity during refresh', async () => {
    const existingCharacter = {
      name: '苏小二',
      role: '船行旧相识',
      description: '船行里的旧相识',
      affinity: 15,
      age: null,
      gender: null,
      occupation: null,
      personality_traits: [],
      image_url: '/old-character.png',
      image_generated: true,
      description_generated: true,
    };

    useCollectionStore.setState({
      characters: [existingCharacter],
      selectedCharacter: existingCharacter,
      items: [],
      landmarks: [],
    });

    (api.collection.get as jest.Mock).mockImplementation(async () => {
      expect(useCollectionStore.getState().isRefreshing).toBe(true);
      expect(useCollectionStore.getState().characters[0].image_url).toBe('/old-character.png');
      return {
        characters: [
          {
            name: '苏小二',
            role: '船行旧相识',
            description: '',
            affinity: 15,
            age: null,
            gender: null,
            occupation: null,
            personality_traits: [],
            image_url: '',
            image_generated: false,
            description_generated: false,
          },
        ],
        items: [],
        landmarks: [],
      };
    });

    await act(async () => {
      await useCollectionStore.getState().fetchCollection(101, true);
    });

    const state = useCollectionStore.getState();
    expect(state.isRefreshing).toBe(false);
    expect(state.characters[0]).toMatchObject({
      name: '苏小二',
      description: '船行里的旧相识',
      image_url: '/old-character.png',
      image_generated: true,
    });
    expect(state.selectedCharacter?.name).toBe('苏小二');
    expect(state.selectedCharacter?.image_url).toBe('/old-character.png');
  });
});
