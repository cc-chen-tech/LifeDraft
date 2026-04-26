/**
 * Tests for usePlayGame hook
 * Tests session recovery, initialization, ending data, and scene images
 */
import { renderHook, act, waitFor } from '@testing-library/react';

// Mock the sub-hooks before importing usePlayGame
const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

// Mock useHydration
let isHydrated = true;
jest.mock('@/hooks/useHydration', () => ({
  useHydration: () => isHydrated,
}));

// Mock sub-hooks
type Phase = 'loading' | 'options' | 'streaming' | 'result' | 'summary' | 'ending' | 'error';

const mockPhaseManager = {
  phase: 'loading' as Phase,
  setPhase: jest.fn(),
  phaseRef: { current: 'loading' as Phase },
  connectionStatus: 'connected' as const,
  setConnectionStatus: jest.fn(),
  reconnectAttempt: 0,
  setReconnectAttempt: jest.fn(),
  elapsedSeconds: 0,
  getLoadingMessage: jest.fn(() => 'Loading...'),
  setProcessing: jest.fn(),
};

jest.mock('@/hooks/game/usePhaseManager', () => ({
  usePhaseManager: () => mockPhaseManager,
  STATUS_MESSAGES: {
    loading: 'Loading...',
    regenerating: 'Regenerating...',
  },
}));

const mockEventGenerator = {
  generateEvent: jest.fn(),
  prefetchNextEvent: jest.fn(),
};

jest.mock('@/hooks/game/useEventGenerator', () => ({
  useEventGenerator: () => mockEventGenerator,
}));

const mockChoiceHandler = {
  handleChoice: jest.fn(),
  handleCustomChoice: jest.fn(),
};

jest.mock('@/hooks/game/useChoiceHandler', () => ({
  useChoiceHandler: () => mockChoiceHandler,
}));

const mockGameState = {
  isSaving: false,
  saveToast: null,
  regenerateToast: null,
  summaryText: '',
  roundSummary: null,
  showAdjuster: false,
  endingData: null,
  setSummaryText: jest.fn(),
  setRoundSummary: jest.fn(),
  setShowAdjuster: jest.fn(),
  handleSave: jest.fn(),
  handleContinueAfterSummary: jest.fn(),
  handleContinueToNextRound: jest.fn(),
  handleAdjustStory: jest.fn(),
  handleRegenerate: jest.fn(),
};

jest.mock('@/hooks/game/useGameState', () => ({
  useGameState: () => mockGameState,
}));

const mockHistoryViewer = {
  showHistory: false,
  setShowHistory: jest.fn(),
  roundHistory: [],
  historyRoundIndex: -1,
  isViewingHistory: false,
  historyDisplayText: '',
  displayText: '',
  handleOpenHistory: jest.fn(),
  handleSelectHistoryRound: jest.fn(),
  handleBackToCurrent: jest.fn(),
};

jest.mock('@/hooks/game/useHistoryViewer', () => ({
  useHistoryViewer: () => mockHistoryViewer,
}));

// Mock games API
const mockGetActive = jest.fn();
const mockGetEnding = jest.fn();
jest.mock('@/lib/api', () => ({
  games: {
    getActive: (...args: unknown[]) => mockGetActive(...args),
  },
  gameplay: {
    getEnding: (...args: unknown[]) => mockGetEnding(...args),
  },
  default: {
    games: {
      getActive: (...args: unknown[]) => mockGetActive(...args),
    },
    gameplay: {
      getEnding: (...args: unknown[]) => mockGetEnding(...args),
    },
  },
}));

// Mock game store
const mockGameStore = {
  gameId: null as number | null,
  playerState: null as Record<string, unknown> | null,
  progress: null as Record<string, unknown> | null,
  roundInfo: null as Record<string, unknown> | null,
  storyText: '',
  currentEvent: null as { story: string; options: unknown[] } | null,
  isGameOver: false,
  appendStoryText: jest.fn(),
  setStoryText: jest.fn(),
  setCurrentEvent: jest.fn(),
  setGameOver: jest.fn(),
  syncState: jest.fn(),
  syncPlayerState: jest.fn(),
  saveGame: jest.fn(),
  roundSceneImages: [] as unknown[],
  currentRoundSceneImage: null as unknown,
  eventSceneImage: null as unknown,
  resultSceneImage: null as unknown,
  isLoadingRoundSceneImage: false,
  isRegeneratingRoundScene: false,
  roundSceneRegenerateError: null,
  fetchRoundSceneImage: jest.fn(),
  fetchAllRoundSceneImages: jest.fn(),
  regenerateRoundSceneImage: jest.fn(),
  setEventSceneImage: jest.fn(),
  setResultSceneImage: jest.fn(),
  enableSceneImage: true,
  generateRoundSceneImage: jest.fn(),
};

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: Object.assign(
    (selector?: (state: typeof mockGameStore) => unknown) => {
      if (selector) return selector(mockGameStore);
      return mockGameStore;
    },
    {
      getState: () => mockGameStore,
      setState: (fn: (state: typeof mockGameStore) => typeof mockGameStore) => {
        const newState = fn(mockGameStore);
        Object.assign(mockGameStore, newState);
      },
    }
  ),
}));

// Import after mocks
import { usePlayGame } from '@/hooks/usePlayGame';

describe('usePlayGame', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    isHydrated = true;
    
    // Reset mock store state
    Object.assign(mockGameStore, {
      gameId: null,
      playerState: null,
      progress: null,
      roundInfo: null,
      storyText: '',
      currentEvent: null,
      isGameOver: false,
      roundSceneImages: [],
      currentRoundSceneImage: null,
      eventSceneImage: null,
      resultSceneImage: null,
      isLoadingRoundSceneImage: false,
      isRegeneratingRoundScene: false,
      roundSceneRegenerateError: null,
      enableSceneImage: true,
    });
    
    // Reset phase manager
    mockPhaseManager.phase = 'loading';
    mockPhaseManager.phaseRef.current = 'loading';
    
    // Reset mocks
    mockPush.mockClear();
    mockReplace.mockClear();
    mockGetActive.mockReset();
  });

  describe('Initial state', () => {
    it('returns initial values correctly', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.phase).toBe('loading');
      expect(result.current.options).toEqual([]);
      expect(result.current.gameId).toBeNull();
      expect(result.current.hydrated).toBe(true);
    });

    it('returns loading state when not hydrated', () => {
      isHydrated = false;
      
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.hydrated).toBe(false);
    });
  });

  describe('Session Recovery', () => {
    it('redirects to home when no gameId and no active game on server', async () => {
      mockGetActive.mockRejectedValue({ status: 404 });
      
      renderHook(() => usePlayGame());
      
      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith('/');
      });
    });

    it('recovers session from server when no gameId in localStorage', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: { player_name: 'TestPlayer', age: 25 },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: {
          event_description: 'Test event',
          options: [{ text: 'Option 1' }],
        },
      };
      mockGetActive.mockResolvedValue(mockActiveGame);
      
      renderHook(() => usePlayGame());
      
      // Verify getActive was called for recovery
      await waitFor(() => {
        expect(mockGetActive).toHaveBeenCalled();
      });
    });

    it('recovers story from last_round_full_story', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          last_round_full_story: 'Last round story content',
        },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: null,
      };
      mockGetActive.mockResolvedValue(mockActiveGame);
      
      renderHook(() => usePlayGame());
      
      // Verify getActive was called for recovery
      await waitFor(() => {
        expect(mockGetActive).toHaveBeenCalled();
      });
    });

    it('recovers story from round_history when no last_round_full_story', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          round_history: [
            { event_description: 'Event 1', story_continuation: 'Story 1' },
            { event_description: 'Event 2', story_continuation: 'Story 2' },
          ],
        },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: null,
      };
      mockGetActive.mockResolvedValue(mockActiveGame);
      
      renderHook(() => usePlayGame());
      
      // Verify getActive was called for recovery
      await waitFor(() => {
        expect(mockGetActive).toHaveBeenCalled();
      });
    });

    it('handles server error during recovery', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockGetActive.mockRejectedValue({ status: 500, message: 'Server error' });

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(mockPhaseManager.setPhase).toHaveBeenCalledWith('error');
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Initial Load', () => {
    it('does not initialize when no gameId', async () => {
      renderHook(() => usePlayGame());
      
      // Should not call syncState without gameId
      expect(mockGameStore.syncState).not.toHaveBeenCalled();
    });

    it('initializes when gameId exists', async () => {
      mockGameStore.gameId = 42;
      mockGameStore.syncState.mockResolvedValue(undefined);
      mockGameStore.currentEvent = { story: 'Test', options: [{ text: 'Option 1' }] };
      
      renderHook(() => usePlayGame());
      
      await waitFor(() => {
        expect(mockGameStore.syncState).toHaveBeenCalled();
      });
    });
  });

  describe('Ending Data', () => {
    it('exposes endingData state', () => {
      const { result } = renderHook(() => usePlayGame());
      
      // endingData should be null initially
      expect(result.current.endingData).toBeNull();
    });
  });

  describe('Round Scene Images', () => {
    it('exposes roundSceneImages state', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.roundSceneImages).toEqual([]);
    });

    it('exposes scene image loading states', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.isLoadingRoundSceneImage).toBe(false);
      expect(result.current.isRegeneratingRoundScene).toBe(false);
    });

    it('exposes scene image actions', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(typeof result.current.fetchRoundSceneImage).toBe('function');
      expect(typeof result.current.fetchAllRoundSceneImages).toBe('function');
      expect(typeof result.current.regenerateRoundSceneImage).toBe('function');
    });
  });

  describe('Handler functions', () => {
    it('provides handleChoice from choiceHandler', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.handleChoice).toBe(mockChoiceHandler.handleChoice);
    });

    it('provides handleCustomChoice from choiceHandler', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.handleCustomChoice).toBe(mockChoiceHandler.handleCustomChoice);
    });

    it('provides handleSave from gameState', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.handleSave).toBe(mockGameState.handleSave);
    });

    it('provides handleRegenerate from gameState', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.handleRegenerate).toBe(mockGameState.handleRegenerate);
    });

    it('provides generateEvent from eventGenerator', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.generateEvent).toBe(mockEventGenerator.generateEvent);
    });
  });

  describe('History functions', () => {
    it('provides history state and handlers', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.showHistory).toBe(false);
      expect(result.current.handleOpenHistory).toBe(mockHistoryViewer.handleOpenHistory);
      expect(result.current.handleSelectHistoryRound).toBe(mockHistoryViewer.handleSelectHistoryRound);
      expect(result.current.handleBackToCurrent).toBe(mockHistoryViewer.handleBackToCurrent);
    });
  });

  describe('Utility functions', () => {
    it('provides getLoadingMessage', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.getLoadingMessage).toBe(mockPhaseManager.getLoadingMessage);
    });

    it('provides router instance', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.router).toBeDefined();
      expect(typeof result.current.router.push).toBe('function');
    });
  });

  describe('Store values', () => {
    it('exposes playerState from store', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.playerState).toBeNull();
    });

    it('exposes progress from store', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.progress).toBeNull();
    });

    it('exposes roundInfo from store', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.roundInfo).toBeNull();
    });

    it('exposes storyText from store', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.storyText).toBe('');
    });

    it('exposes currentEvent from store', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.currentEvent).toBeNull();
    });

    it('exposes isGameOver from store', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.isGameOver).toBe(false);
    });
  });

  describe('Actions', () => {
    it('provides setPhase action', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.setPhase).toBe(mockPhaseManager.setPhase);
    });

    it('provides setOptions action', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(typeof result.current.setOptions).toBe('function');
    });

    it('provides setShowAdjuster action', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.setShowAdjuster).toBe(mockGameState.setShowAdjuster);
    });

    it('provides setStoryText action', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.setStoryText).toBe(mockGameStore.setStoryText);
    });
  });
});
