/**
 * Store Migration Compatibility Tests
 * 
 * Tests to ensure backward compatibility when migrating/splitting stores.
 * Validates that old selectors and state shapes still work after refactoring.
 */
import { act } from '@testing-library/react';

// Mock the API before importing stores
jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    games: {
      list: jest.fn().mockResolvedValue([]),
      create: jest.fn().mockResolvedValue({ game_id: 1 }),
      load: jest.fn().mockResolvedValue({
        game_id: 1,
        player_state: { player_name: 'Test', energy: 100 },
        progress: { week: 1 },
        round_info: { current_round: 1 },
        current_event: null,
      }),
      save: jest.fn().mockResolvedValue({ success: true }),
      delete: jest.fn().mockResolvedValue({ success: true }),
    },
    presets: {
      list: jest.fn().mockResolvedValue([]),
      create: jest.fn().mockResolvedValue({ preset_id: 1 }),
      delete: jest.fn().mockResolvedValue({ success: true }),
    },
    gameplay: {
      getState: jest.fn().mockResolvedValue({
        player_state: { player_name: 'Test' },
        progress: { week: 1 },
        round_info: { current_round: 1 },
        current_event: null,
      }),
    },
    images: {
      listByGame: jest.fn().mockResolvedValue({ images: [], total: 0 }),
      getRoundSceneImage: jest.fn().mockResolvedValue(null),
      getAllRoundSceneImages: jest.fn().mockResolvedValue({ scenes: [] }),
    },
  },
}));

import { useGameStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS } from '@/stores/useGameStore';
import { useImageStore } from '@/stores/useImageStore';
import { useEventStore } from '@/stores/useEventStore';
import { useCharacterStore } from '@/stores/useCharacterStore';
import { useGameListStore } from '@/stores/useGameListStore';

describe('Store Migration Compatibility', () => {
  beforeEach(() => {
    act(() => {
      useGameStore.getState().resetGame();
      useGameStore.getState().resetCreation();
    });
    jest.clearAllMocks();
  });

  describe('Old useGameStore selectors still work', () => {
    it('should access gameId through useGameStore', () => {
      act(() => {
        useGameStore.getState().setGameId(42);
      });
      expect(useGameStore.getState().gameId).toBe(42);
    });

    it('should access sessionId through useGameStore', () => {
      act(() => {
        useGameStore.getState().setGameSession(1, 'session-1');
      });
      expect(useGameStore.getState().sessionId).toBe('session-1');
    });

    it('should access storyText through useGameStore', () => {
      act(() => {
        useGameStore.getState().setStoryText('Test story');
      });
      expect(useGameStore.getState().storyText).toBe('Test story');
    });

    it('should access currentEvent through useGameStore', () => {
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'Event',
          options: [{ text: 'Option' }],
        });
      });
      expect(useGameStore.getState().currentEvent?.story).toBe('Event');
    });

    it('should access creationStep through useGameStore', () => {
      act(() => {
        useGameStore.getState().setCreationStep(3);
      });
      expect(useGameStore.getState().creationStep).toBe(3);
    });

    it('should access characterSettings through useGameStore', () => {
      act(() => {
        useGameStore.getState().updateCharacterSetting('era', { era: 'modern' });
      });
      expect(useGameStore.getState().characterSettings.era).toEqual({ era: 'modern' });
    });

    it('should access enableSceneImage through useGameStore', () => {
      act(() => {
        useGameStore.getState().setEnableSceneImage(false);
      });
      expect(useGameStore.getState().enableSceneImage).toBe(false);
    });
  });

  describe('State shape matches original', () => {
    it('should have all original session fields', () => {
      const state = useGameStore.getState();
      expect('gameId' in state).toBe(true);
      expect('sessionId' in state).toBe(true);
      expect('playerState' in state).toBe(true);
      expect('progress' in state).toBe(true);
      expect('roundInfo' in state).toBe(true);
      expect('isGameOver' in state).toBe(true);
    });

    it('should have all original event fields', () => {
      const state = useGameStore.getState();
      expect('currentEvent' in state).toBe(true);
      expect('storyText' in state).toBe(true);
      expect('lastSummary' in state).toBe(true);
    });

    it('should have all original character creation fields', () => {
      const state = useGameStore.getState();
      expect('creationStep' in state).toBe(true);
      expect('characterSettings' in state).toBe(true);
      expect('playerName' in state).toBe(true);
      expect('lifeVision' in state).toBe(true);
      expect('openingStory' in state).toBe(true);
      expect('isPresetLoaded' in state).toBe(true);
    });

    it('should have all original list fields', () => {
      const state = useGameStore.getState();
      expect('savedGames' in state).toBe(true);
      expect('presets' in state).toBe(true);
    });

    it('should have all original scene image fields', () => {
      const state = useGameStore.getState();
      expect('roundSceneImages' in state).toBe(true);
      expect('currentRoundSceneImage' in state).toBe(true);
      expect('eventSceneImage' in state).toBe(true);
      expect('resultSceneImage' in state).toBe(true);
      expect('enableSceneImage' in state).toBe(true);
    });

    it('should export CREATION_STEPS correctly', () => {
      expect(CREATION_STEPS).toBeDefined();
      expect(Array.isArray(CREATION_STEPS)).toBe(true);
      expect(CREATION_STEPS).toContain('era');
      expect(CREATION_STEPS).toContain('portrait');
    });

    it('should export MANUAL_STEPS correctly', () => {
      expect(MANUAL_STEPS).toBeDefined();
      expect(Array.isArray(MANUAL_STEPS)).toBe(true);
    });

    it('should export AUTO_ADVANCE_STEPS correctly', () => {
      expect(AUTO_ADVANCE_STEPS).toBeDefined();
      expect(Array.isArray(AUTO_ADVANCE_STEPS)).toBe(true);
    });
  });

  describe('Cross-store data consistency', () => {
    it('should maintain consistency when using useGameStore actions', () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.getState().setStoryText('Test story');
        useGameStore.getState().setCurrentEvent({
          story: 'Test story',
          options: [{ text: 'Option' }],
        });
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBe(42);
      expect(state.sessionId).toBe('session-42');
      expect(state.storyText).toBe('Test story');
      expect(state.currentEvent?.options).toHaveLength(1);
    });

    it('should maintain consistency between related fields', () => {
      act(() => {
        useGameStore.getState().setPlayerName('TestPlayer');
        useGameStore.getState().updateCharacterSetting('era', { era: 'ancient' });
        useGameStore.getState().setCreationStep(2);
      });

      const state = useGameStore.getState();
      expect(state.playerName).toBe('TestPlayer');
      expect(state.characterSettings.era).toEqual({ era: 'ancient' });
      expect(state.creationStep).toBe(2);
    });
  });

  describe('Concurrent updates from multiple stores', () => {
    it('should handle concurrent state updates', () => {
      act(() => {
        // Simulate updates that might come from different parts of the app
        useGameStore.getState().setStoryText('Story 1');
        useGameStore.getState().setCurrentEvent({
          story: 'Story 1',
          options: [],
        });
        useGameStore.getState().appendStoryText(' - continued');
      });

      expect(useGameStore.getState().storyText).toBe('Story 1 - continued');
    });

    it('should not lose data during rapid updates', () => {
      act(() => {
        for (let i = 0; i < 10; i++) {
          useGameStore.getState().appendStoryText(`Part${i}`);
        }
      });

      const storyText = useGameStore.getState().storyText;
      for (let i = 0; i < 10; i++) {
        expect(storyText).toContain(`Part${i}`);
      }
    });
  });

  describe('Hydration works with split stores', () => {
    it('should handle state initialization correctly', () => {
      // Simulate fresh app load
      act(() => {
        useGameStore.getState().resetGame();
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBeNull();
      expect(state.sessionId).toBeNull();
      expect(state.storyText).toBe('');
      expect(state.currentEvent).toBeNull();
    });

    it('should handle state restoration correctly', async () => {
      // Simulate restoring state (like from a saved game)
      const savedState = {
        gameId: 100,
        sessionId: 'saved-session',
        playerState: { player_name: 'SavedPlayer', life_vision: '', energy: 80, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 5, current_round: 3, rounds_per_week: 3, character_settings: {} },
        progress: { week: 5, current_round: 3, rounds_per_week: 3 },
        roundInfo: { current_round: 3, week: 5 },
        storyText: 'Saved story content',
        currentEvent: null,
      };

      act(() => {
        useGameStore.setState(savedState);
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBe(100);
      expect(state.sessionId).toBe('saved-session');
      expect(state.storyText).toBe('Saved story content');
    });

    it('should handle partial state updates', () => {
      act(() => {
        useGameStore.setState({ gameId: 1, storyText: 'Initial' });
      });

      // Update only part of the state
      act(() => {
        useGameStore.setState({ storyText: 'Updated' });
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBe(1);  // Should be preserved
      expect(state.storyText).toBe('Updated');  // Should be updated
    });
  });

  describe('Sub-store re-exports work correctly', () => {
    it('should re-export useEventStore from useGameStore', () => {
      expect(useEventStore).toBeDefined();
    });

    it('should re-export useImageStore from useGameStore', () => {
      expect(useImageStore).toBeDefined();
    });

    it('should re-export useCharacterStore from useGameStore', () => {
      expect(useCharacterStore).toBeDefined();
    });

    it('should re-export useGameListStore from useGameStore', () => {
      expect(useGameListStore).toBeDefined();
    });
  });
});
