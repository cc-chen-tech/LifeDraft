/**
 * hooks/useGameIdFromUrl.ts Tests
 * Tests for URL parameter gameId synchronization hook
 */
import { renderHook } from '@testing-library/react';
import { useGameIdFromUrl } from '@/hooks/useGameIdFromUrl';
import { useGameStore } from '@/stores/useGameStore';

// Mock next/navigation (env mock — required)
const mockSearchParams = {
  get: jest.fn(),
};

jest.mock('next/navigation', () => ({
  useSearchParams: () => mockSearchParams,
}));

function setupDefaultState() {
  useGameStore.setState({
    gameId: 295,
  });
}

describe('useGameIdFromUrl', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
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

  it('syncs URL gameId to store when different from current store gameId', () => {
    mockSearchParams.get.mockReturnValue('296');
    renderHook(() => useGameIdFromUrl());
    expect(useGameStore.getState().gameId).toBe(296);
  });

  it('does not sync when URL gameId matches current store gameId', () => {
    mockSearchParams.get.mockReturnValue('295');
    renderHook(() => useGameIdFromUrl());
    expect(useGameStore.getState().gameId).toBe(295);
  });

  it('handles invalid gameId gracefully', () => {
    mockSearchParams.get.mockReturnValue('invalid');
    renderHook(() => useGameIdFromUrl());
    expect(useGameStore.getState().gameId).toBe(295);
  });

  it('handles empty string gameId', () => {
    mockSearchParams.get.mockReturnValue('');
    renderHook(() => useGameIdFromUrl());
    expect(useGameStore.getState().gameId).toBe(295);
  });

  it('URL gameId takes priority over existing gameId', () => {
    mockSearchParams.get.mockReturnValue('296');
    renderHook(() => useGameIdFromUrl());
    expect(useGameStore.getState().gameId).toBe(296);
  });
});
