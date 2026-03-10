/**
 * hooks/useGameIdFromUrl.ts Tests
 * Tests for URL parameter gameId synchronization hook
 */
import { renderHook, act } from '@testing-library/react';
import { useGameIdFromUrl } from '@/hooks/useGameIdFromUrl';
import { useGameStore } from '@/stores/useGameStore';

// Mock next/navigation
const mockSearchParams = {
  get: jest.fn(),
};

jest.mock('next/navigation', () => ({
  useSearchParams: () => mockSearchParams,
}));

// Mock useGameStore
const mockSetGameId = jest.fn();

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: jest.fn((selector) => {
    const state = {
      setGameId: mockSetGameId,
      gameId: 295, // localStorage 中的旧值
    };
    return selector(state);
  }),
}));

describe('useGameIdFromUrl', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // 默认 localStorage 中的 gameId 是 295
    (useGameStore as unknown as jest.Mock).mockImplementation((selector) => {
      return selector({
        setGameId: mockSetGameId,
        gameId: 295,
      });
    });
  });

  it('returns urlGameId from URL parameters', () => {
    mockSearchParams.get.mockReturnValue('296');

    const { result } = renderHook(() => useGameIdFromUrl());

    expect(result.current.urlGameId).toBe(296);
  });

  it('returns null when no gameId in URL', () => {
    mockSearchParams.get.mockReturnValue(null);

    const { result } = renderHook(() => useGameIdFromUrl());

    expect(result.current.urlGameId).toBeNull();
  });

  it('syncs URL gameId to store when different from localStorage', () => {
    mockSearchParams.get.mockReturnValue('296');

    renderHook(() => useGameIdFromUrl());

    // URL gameId=296 优先于 localStorage gameId=295
    expect(mockSetGameId).toHaveBeenCalledWith(296);
  });

  it('does not sync when URL gameId matches localStorage', () => {
    mockSearchParams.get.mockReturnValue('295');

    renderHook(() => useGameIdFromUrl());

    // URL gameId=295 与 localStorage 相同，不需要更新
    expect(mockSetGameId).not.toHaveBeenCalled();
  });

  it('handles invalid gameId gracefully', () => {
    mockSearchParams.get.mockReturnValue('invalid');

    renderHook(() => useGameIdFromUrl());

    expect(mockSetGameId).not.toHaveBeenCalled();
  });

  it('handles empty string gameId', () => {
    mockSearchParams.get.mockReturnValue('');

    renderHook(() => useGameIdFromUrl());

    expect(mockSetGameId).not.toHaveBeenCalled();
  });

  it('URL gameId takes priority over localStorage', () => {
    // 模拟 URL 有 gameId=296，localStorage 有 gameId=295
    mockSearchParams.get.mockReturnValue('296');

    renderHook(() => useGameIdFromUrl());

    // 验证 URL 参数优先
    expect(mockSetGameId).toHaveBeenCalledTimes(1);
    expect(mockSetGameId).toHaveBeenCalledWith(296);
  });
});
