/**
 * useSessionStore State Comparison Logic Tests
 *
 * Tests for the shallow comparison logic used in state synchronization
 * to catch state synchronization issues early.
 */
import { act } from '@testing-library/react';
import type { PlayerState, GameProgress, RoundInfo } from '@/lib/types';

import { useSessionStore } from '@/stores/useSessionStore';
import { useGameStore } from '@/stores/useGameStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

// Helper to create a base player state
const createBasePlayerState = (): PlayerState => ({
  player_name: 'Test',
  life_vision: 'Test Vision',
  energy: 100,
  mood: 50,
  knowledge: 0,
  wealth: 0,
  age: 18,
  week: 1,
  current_round: 1,
  rounds_per_week: 3,
  character_settings: {},
});

describe('useSessionStore State Comparison Logic', () => {
  beforeEach(() => {
    act(() => {
      useSessionStore.setState({
        gameId: null,
        sessionId: null,
        playerState: null,
        progress: null,
        roundInfo: null,
        isGameOver: false,
        enableSceneImage: true,
        constraintLevel: 'expert',
      });
    });
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  // ==================== shallowChanged Function Tests ====================
  describe('shallowChanged function behavior', () => {
    it('returns false when comparing the same object reference', async () => {
      const sameObject = createBasePlayerState();

      // First set the state with all fields to avoid extra updates
      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: sameObject,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      // Mock API to return the same object reference
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: sameObject,
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any previous calls from initial setup
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should not trigger update since it's the same reference
      expect(listener).not.toHaveBeenCalled();

      unsubscribe();
    });

    it('returns true when new value is null', async () => {
      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: createBasePlayerState(),
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: null,
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger update since player_state changed to null
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });

    it('returns true when old value is null', async () => {
      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: null,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: createBasePlayerState(),
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger update since player_state changed from null
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });

    it('returns true when both values are null', async () => {
      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: null,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: null,
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should not trigger update since both are null (no change)
      expect(listener).not.toHaveBeenCalled();

      unsubscribe();
    });

    it('only compares key fields specified in KEY_FIELDS', async () => {
      const oldState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: oldState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      // New state with only non-key field changed (player_name)
      const newState = {
        ...oldState,
        player_name: 'Changed',
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: newState,
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should NOT trigger update since KEY_FIELDS doesn't include player_name
      // KEY_FIELDS = ["energy", "mood", "knowledge", "wealth", "age", "week", "current_round"]
      expect(listener).not.toHaveBeenCalled();

      unsubscribe();
    });

    it('triggers update when key field energy changes', async () => {
      const oldState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: oldState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const newState = {
        ...oldState,
        energy: 80,
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: newState,
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger update since energy is in KEY_FIELDS
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });

    it('triggers update when key field week changes', async () => {
      const oldState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: oldState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const newState = {
        ...oldState,
        week: 2,
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: newState,
        progress: { week: 2, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 2 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger update since week is in KEY_FIELDS
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });

    it('uses shallow comparison for nested objects (reference equality)', async () => {
      const nestedObject = { some: 'value' };
      const oldState = {
        ...createBasePlayerState(),
        nested: nestedObject,
      } as PlayerState & { nested: Record<string, string> };

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: oldState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      // New state with different reference but same content for nested object
      const newState = {
        ...oldState,
        nested: { some: 'value' }, // Different reference, same content
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: newState,
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should NOT trigger update since nested is not in KEY_FIELDS
      expect(listener).not.toHaveBeenCalled();

      unsubscribe();
    });
  });

  // ==================== State Subscription Filtering Tests ====================
  describe('State Subscription Filtering', () => {
    it('does not trigger update when only non-key fields change', async () => {
      const baseState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: baseState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      // Simulate API returning state with only non-key field changes
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: {
          ...baseState,
          player_name: 'Changed',
          life_vision: 'New vision',
        },
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should not trigger subscriber since key fields haven't changed
      expect(listener).not.toHaveBeenCalled();

      unsubscribe();
    });

    it('triggers update when key fields change', async () => {
      const baseState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: baseState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      // Simulate API returning state with key field changed
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: {
          ...baseState,
          week: 2,
        },
        progress: { week: 2, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 2 },
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger subscriber since week (key field) changed
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });

    it('triggers update when multiple key fields change', async () => {
      const baseState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: baseState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      // Simulate API returning state with multiple key fields changed
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: {
          ...baseState,
          energy: 80,
          mood: 40,
          week: 2,
        },
        progress: { week: 2, current_round: 2, rounds_per_week: 3 },
        round_info: { current_round: 2, week: 2 },
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger subscriber since key fields changed
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });

    it('does not trigger update when progress key fields are unchanged', async () => {
      const basePlayerState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: basePlayerState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      // Simulate API returning same progress but player_state with only non-key fields changed
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: {
          ...basePlayerState,
          player_name: 'Changed',
        },
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Progress key fields (week, current_round, rounds_per_week) haven't changed
      // and player_state key fields haven't changed
      expect(listener).not.toHaveBeenCalled();

      unsubscribe();
    });

    it('triggers update when progress week changes', async () => {
      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: null,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: createBasePlayerState(),
        progress: { week: 2, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 2 },
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger since progress week changed
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });
  });

  // ==================== Multi-Store Sync Consistency Tests ====================
  describe('Multi-Store Sync Consistency', () => {
    beforeEach(() => {
      // Reset useGameStore as well for multi-store tests
      act(() => {
        useGameStore.setState({
          gameId: null,
          sessionId: null,
          playerState: null,
          progress: null,
          roundInfo: null,
          isGameOver: false,
          storyText: '',
          currentEvent: null,
        });
      });
    });

    it('syncs playerState updates to useGameStore', async () => {
      const playerState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: playerState,
        });
      });

      // Verify useGameStore sees the same playerState
      expect(useGameStore.getState().playerState).toEqual(playerState);
    });

    it('syncs progress updates to useGameStore', async () => {
      const progress: GameProgress = { week: 5, current_round: 3, rounds_per_week: 3 };

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          progress: progress,
        });
      });

      // Verify useGameStore sees the same progress
      expect(useGameStore.getState().progress).toEqual(progress);
    });

    it('maintains consistency between sessionStore and gameStore after syncState', async () => {
      const mockPlayerState = createBasePlayerState();
      mockPlayerState.energy = 80;
      mockPlayerState.mood = 60;
      mockPlayerState.knowledge = 10;
      mockPlayerState.wealth = 20;
      mockPlayerState.age = 20;
      mockPlayerState.week = 3;
      mockPlayerState.current_round = 2;

      const mockProgress: GameProgress = { week: 3, current_round: 2, rounds_per_week: 3 };
      const mockRoundInfo: RoundInfo = { current_round: 2, week: 3 };

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          sessionId: 'test-session',
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: mockPlayerState,
        progress: mockProgress,
        round_info: mockRoundInfo,
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Verify both stores have consistent state
      const sessionState = useSessionStore.getState();
      const gameState = useGameStore.getState();

      expect(gameState.playerState).toEqual(mockPlayerState);
      expect(gameState.progress).toEqual(mockProgress);
      expect(gameState.roundInfo).toEqual(mockRoundInfo);
      expect(sessionState.playerState).toEqual(mockPlayerState);
      expect(sessionState.progress).toEqual(mockProgress);
      expect(sessionState.roundInfo).toEqual(mockRoundInfo);
    });

    it('updates both stores when playerState key fields change', async () => {
      const initialState = createBasePlayerState();

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          sessionId: 'test-session',
          playerState: initialState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const updatedState = {
        ...initialState,
        energy: 75,
        week: 2,
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: updatedState,
        progress: { week: 2, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 2 },
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Both stores should have the updated state
      expect(useSessionStore.getState().playerState?.energy).toBe(75);
      expect(useSessionStore.getState().playerState?.week).toBe(2);
      expect(useGameStore.getState().playerState?.energy).toBe(75);
      expect(useGameStore.getState().playerState?.week).toBe(2);
    });

    it('preserves gameStore state when sessionStore non-key fields change', async () => {
      const initialState = createBasePlayerState();

      act(() => {
        useGameStore.setState({
          gameId: 1,
          playerState: initialState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      // Store the reference to check if it changes
      const originalPlayerState = useGameStore.getState().playerState;

      // Trigger sync with only non-key field changes
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: {
          ...initialState,
          player_name: 'ChangedName', // Non-key field
        },
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // State reference should remain the same (no update triggered)
      expect(useGameStore.getState().playerState).toBe(originalPlayerState);
    });
  });

  // ==================== Edge Cases ====================
  describe('Edge Cases', () => {
    it('handles undefined values in key fields comparison', async () => {
      const oldState = {
        ...createBasePlayerState(),
        energy: undefined as unknown as number,
      };

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: oldState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      const newState = createBasePlayerState();
      newState.energy = 100; // Changed from undefined

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: newState,
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger update since undefined !== 100
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });

    it('handles zero values correctly in key fields', async () => {
      const oldState = createBasePlayerState();
      oldState.energy = 0;

      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: oldState,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      // Same state with same zero values
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: { ...oldState },
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should not trigger since 0 === 0
      expect(listener).not.toHaveBeenCalled();

      unsubscribe();
    });

    it('correctly identifies changes in round_info key fields', async () => {
      act(() => {
        useSessionStore.setState({
          gameId: 1,
          playerState: null,
          progress: { week: 1, current_round: 1, rounds_per_week: 3 },
          roundInfo: { current_round: 1, week: 1 },
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: createBasePlayerState(),
        progress: { week: 2, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 2, week: 2 }, // current_round changed
        current_event: null,
      }));

      const listener = jest.fn();
      const unsubscribe = useSessionStore.subscribe(listener);

      // Clear any initial calls
      listener.mockClear();

      await act(async () => {
        await useSessionStore.getState().syncState();
      });

      // Should trigger since current_round in round_info changed
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });
  });
});
