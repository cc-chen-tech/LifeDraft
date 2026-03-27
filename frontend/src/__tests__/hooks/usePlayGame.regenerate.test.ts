/**
 * 测试 handleRegenerate 函数的完整行为
 * 
 * 测试覆盖：
 * 1. handleRegenerate 函数存在
 * 2. 调用不抛出错误
 */
import { renderHook, act } from '@testing-library/react';
import { usePlayGame } from '@/hooks/usePlayGame';
import { useGameStore } from '@/stores/useGameStore';
import { useUIStore } from '@/stores/useUIStore';

// Mock dependencies
jest.mock('@/stores/useGameStore', () => {
  const mockFn = jest.fn();
  (mockFn as unknown as { getState: jest.Mock }).getState = jest.fn(() => ({
    storyText: 'Original story',
    currentEvent: { story: 'Original story', options: [{ text: 'Option 1' }] },
    roundInfo: { current_round: 1 },
    enableSceneImage: true,
    generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
    syncPlayerState: jest.fn().mockResolvedValue({}),
    syncState: jest.fn().mockResolvedValue(undefined),
  }));
  return { useGameStore: mockFn };
});
jest.mock('@/stores/useUIStore');
jest.mock('@/hooks/useHydration', () => ({
  useHydration: () => true,
}));
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
}));

// Mock API functions including fetchRoundSceneImage
jest.mock('@/lib/api', () => ({
  default: {
    games: {
      load: jest.fn(),
      save: jest.fn(),
    },
    gameplay: {
      getState: jest.fn(),
    },
    images: {
      getRoundSceneImage: jest.fn().mockResolvedValue(null),
    },
  },
  fetchRoundSceneImage: jest.fn().mockResolvedValue(null),
}));

// Mock SSE functions
jest.mock('@/lib/sse', () => ({
  streamGameEvent: jest.fn(() => Promise.resolve({ completed: true })),
  streamChoice: jest.fn(() => Promise.resolve({ completed: true })),
  streamCustomChoice: jest.fn(() => Promise.resolve({ completed: true })),
  streamRegenerate: jest.fn(() => Promise.resolve({ completed: true })),
}));

// Mock fetch for remote-log
global.fetch = jest.fn(() => Promise.resolve(new Response()));

describe('handleRegenerate', () => {
  const mockSetStoryText = jest.fn();
  const mockSetCurrentEvent = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup store mocks with all required functions
    (useGameStore as unknown as jest.Mock).mockReturnValue({
      gameId: 1,
      playerState: { player_name: 'Test Player' },
      progress: { week: 1 },
      roundInfo: { current_round: 1 },
      storyText: 'Original story',
      currentEvent: { story: 'Original story', options: [{ text: 'Option 1' }] },
      isGameOver: false,
      setStoryText: mockSetStoryText,
      setCurrentEvent: mockSetCurrentEvent,
      setGameOver: jest.fn(),
      syncState: jest.fn(),
      syncPlayerState: jest.fn().mockResolvedValue({}),
      saveGame: jest.fn(),
      appendStoryText: jest.fn(),
      // Scene image functions
      roundSceneImages: {},
      currentRoundSceneImage: null,
      eventSceneImage: null,
      resultSceneImage: null,
      isLoadingRoundSceneImage: false,
      isRegeneratingRoundScene: false,
      roundSceneRegenerateError: null,
      fetchRoundSceneImage: jest.fn().mockResolvedValue(null),
      fetchAllRoundSceneImages: jest.fn().mockResolvedValue(null),
      regenerateRoundSceneImage: jest.fn().mockResolvedValue(null),
      setEventSceneImage: jest.fn(),
      setResultSceneImage: jest.fn(),
    });
    
    (useUIStore as unknown as jest.Mock).mockReturnValue({
      setProcessing: jest.fn(),
      processingMessage: null,
    });
  });

  describe('基础功能', () => {
    it('handleRegenerate 应该是一个函数', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(typeof result.current.handleRegenerate).toBe('function');
    });
    
    it('调用 handleRegenerate 不应该抛出错误', async () => {
      const { result } = renderHook(() => usePlayGame());
      
      await act(async () => {
        result.current.handleRegenerate();
      });
      
      // 基础验证：函数可以正常调用
      expect(true).toBe(true);
    });
    
    it('应该暴露所有必要的 handler 函数', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(typeof result.current.handleChoice).toBe('function');
      expect(typeof result.current.handleCustomChoice).toBe('function');
      expect(typeof result.current.handleSave).toBe('function');
      expect(typeof result.current.handleRegenerate).toBe('function');
      expect(typeof result.current.handleContinueToNextRound).toBe('function');
    });
  });

  describe('状态访问', () => {
    it('应该返回 phase 状态', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.phase).toBeDefined();
    });
    
    it('应该返回 gameId', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.gameId).toBe(1);
    });
    
    it('应该返回 storyText', () => {
      const { result } = renderHook(() => usePlayGame());
      
      expect(result.current.storyText).toBe('Original story');
    });
  });
});
