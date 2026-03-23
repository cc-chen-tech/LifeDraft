/**
 * usePlayStateStore Tests
 * 
 * Tests for gameplay state management that may be extracted from useGameStore.
 * Covers: currentWeek, round, choices, event state, story text, game over state.
 */
import { act, renderHook } from '@testing-library/react';

// Mock the API before importing the store
jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    games: {
      list: jest.fn().mockResolvedValue([]),
      create: jest.fn().mockResolvedValue({ game_id: 1 }),
      load: jest.fn().mockResolvedValue({
        game_id: 1,
        player_state: { player_name: 'Test' },
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
      generateSummary: jest.fn().mockResolvedValue({
        summary_text: 'Test summary',
      }),
    },
    images: {
      listByGame: jest.fn().mockResolvedValue({ images: [], total: 0 }),
    },
  },
}));

import { useGameStore } from '@/stores/useGameStore';
import api from '@/lib/api';

describe('usePlayStateStore (Gameplay State)', () => {
  beforeEach(() => {
    act(() => {
      useGameStore.getState().resetGame();
      useGameStore.getState().resetCreation();
    });
    jest.clearAllMocks();
  });

  // ==================== Story Text Tests ====================
  describe('Story Text Management', () => {
    it('should have empty storyText initially', () => {
      expect(useGameStore.getState().storyText).toBe('');
    });

    it('should set storyText correctly', () => {
      act(() => {
        useGameStore.getState().setStoryText('Hello World');
      });
      expect(useGameStore.getState().storyText).toBe('Hello World');
    });

    it('should append to storyText', () => {
      act(() => {
        useGameStore.getState().setStoryText('Hello');
        useGameStore.getState().appendStoryText(' World');
      });
      expect(useGameStore.getState().storyText).toBe('Hello World');
    });

    it('should clear storyText by setting empty string', () => {
      act(() => {
        useGameStore.getState().setStoryText('Some text');
        useGameStore.getState().setStoryText('');
      });
      expect(useGameStore.getState().storyText).toBe('');
    });

    it('should append multiple times correctly', () => {
      act(() => {
        useGameStore.getState().setStoryText('A');
        useGameStore.getState().appendStoryText('B');
        useGameStore.getState().appendStoryText('C');
        useGameStore.getState().appendStoryText('D');
      });
      expect(useGameStore.getState().storyText).toBe('ABCD');
    });

    it('should handle unicode characters', () => {
      act(() => {
        useGameStore.getState().setStoryText('你好世界 🌍');
      });
      expect(useGameStore.getState().storyText).toBe('你好世界 🌍');
    });

    it('should handle very long text', () => {
      const longText = 'A'.repeat(10000);
      act(() => {
        useGameStore.getState().setStoryText(longText);
      });
      expect(useGameStore.getState().storyText.length).toBe(10000);
    });
  });

  // ==================== Current Event Tests ====================
  describe('Current Event Management', () => {
    it('should have null currentEvent initially', () => {
      expect(useGameStore.getState().currentEvent).toBeNull();
    });

    it('should set currentEvent with story and options', () => {
      const event = {
        story: 'Test story',
        options: [{ text: 'Option 1' }, { text: 'Option 2' }],
      };
      act(() => {
        useGameStore.getState().setCurrentEvent(event);
      });
      expect(useGameStore.getState().currentEvent).toEqual(event);
    });

    it('should clear currentEvent by setting null', () => {
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'Test',
          options: [],
        });
        useGameStore.getState().setCurrentEvent(null);
      });
      expect(useGameStore.getState().currentEvent).toBeNull();
    });

    it('should clear currentEvent and storyText via clearCurrentEvent', () => {
      act(() => {
        useGameStore.getState().setStoryText('Some story');
        useGameStore.getState().setCurrentEvent({
          story: 'Event story',
          options: [],
        });
        useGameStore.getState().clearCurrentEvent();
      });
      expect(useGameStore.getState().currentEvent).toBeNull();
      expect(useGameStore.getState().storyText).toBe('');
    });

    it('should preserve existing storyText when setting event', () => {
      act(() => {
        useGameStore.getState().setStoryText('Existing story');
        useGameStore.getState().setCurrentEvent({
          story: 'New event',
          options: [{ text: 'Option' }],
        });
      });
      // storyText should be preserved as existing
      expect(useGameStore.getState().storyText).toBe('Existing story');
    });

    it('should use event story when no existing storyText', () => {
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'Event story',
          options: [{ text: 'Option' }],
        });
      });
      expect(useGameStore.getState().storyText).toBe('Event story');
    });

    it('should handle event with empty options', () => {
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'Story',
          options: [],
        });
      });
      expect(useGameStore.getState().currentEvent?.options).toHaveLength(0);
    });

    it('should handle event with multiple options', () => {
      const options = [
        { text: 'Option 1', effects: { mood: 10 } },
        { text: 'Option 2', effects: { energy: -5 } },
        { text: 'Option 3', effects: { knowledge: 5 } },
      ];
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'Choose wisely',
          options,
        });
      });
      expect(useGameStore.getState().currentEvent?.options).toHaveLength(3);
    });
  });

  // ==================== Game Over State Tests ====================
  describe('Game Over State', () => {
    it('should have isGameOver as false initially', () => {
      expect(useGameStore.getState().isGameOver).toBe(false);
    });

    it('should set isGameOver to true', () => {
      act(() => {
        useGameStore.getState().setGameOver(true);
      });
      expect(useGameStore.getState().isGameOver).toBe(true);
    });

    it('should set isGameOver back to false', () => {
      act(() => {
        useGameStore.getState().setGameOver(true);
        useGameStore.getState().setGameOver(false);
      });
      expect(useGameStore.getState().isGameOver).toBe(false);
    });

    it('should not affect other state when setting game over', () => {
      act(() => {
        useGameStore.getState().setStoryText('Some story');
        useGameStore.getState().setGameOver(true);
      });
      expect(useGameStore.getState().storyText).toBe('Some story');
      expect(useGameStore.getState().isGameOver).toBe(true);
    });
  });

  // ==================== Progress State Tests ====================
  describe('Progress State', () => {
    it('should update progress via syncState', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (api.gameplay.getState as jest.Mock).mockResolvedValue({
        player_state: {},
        progress: { week: 10, current_round: 5 },
        round_info: { current_round: 5 },
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(useGameStore.getState().progress?.week).toBe(10);
    });

    it('should track week progression correctly', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      // Week 1
      (api.gameplay.getState as jest.Mock).mockResolvedValue({
        player_state: {},
        progress: { week: 1 },
        round_info: {},
        current_event: null,
      });
      await act(async () => {
        await useGameStore.getState().syncState();
      });
      expect(useGameStore.getState().progress?.week).toBe(1);

      // Week 2
      (api.gameplay.getState as jest.Mock).mockResolvedValue({
        player_state: {},
        progress: { week: 2 },
        round_info: {},
        current_event: null,
      });
      await act(async () => {
        await useGameStore.getState().syncState();
      });
      expect(useGameStore.getState().progress?.week).toBe(2);
    });
  });

  // ==================== Round Info Tests ====================
  describe('Round Info', () => {
    it('should update roundInfo via syncState', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (api.gameplay.getState as jest.Mock).mockResolvedValue({
        player_state: {},
        progress: {},
        round_info: { current_round: 7, week: 3 },
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(useGameStore.getState().roundInfo?.current_round).toBe(7);
    });
  });

  // ==================== Summary Tests ====================
  describe('Summary Management', () => {
    it('should have null lastSummary initially', () => {
      expect(useGameStore.getState().lastSummary).toBeNull();
    });

    it('should clear summary', () => {
      act(() => {
        useGameStore.setState({ lastSummary: { text: 'summary' } });
        useGameStore.getState().clearSummary();
      });
      expect(useGameStore.getState().lastSummary).toBeNull();
    });

    it('should generate summary via API', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (api.gameplay.generateSummary as jest.Mock).mockResolvedValue({
        summary_text: 'Generated summary',
        start_week: 1,
        end_week: 10,
      });

      await act(async () => {
        await useGameStore.getState().generateSummary(10);
      });

      expect(api.gameplay.generateSummary).toHaveBeenCalledWith(42, { weeks: 10 });
    });

    it('should not generate summary without gameId', async () => {
      await act(async () => {
        await useGameStore.getState().generateSummary();
      });
      expect(api.gameplay.generateSummary).not.toHaveBeenCalled();
    });
  });

  // ==================== State Flow Tests ====================
  describe('Gameplay State Flow', () => {
    it('should handle complete round flow', async () => {
      // Setup game
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      // Set event with options
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'You encounter a crossroad',
          options: [
            { text: 'Go left' },
            { text: 'Go right' },
          ],
        });
      });
      expect(useGameStore.getState().storyText).toBe('You encounter a crossroad');
      expect(useGameStore.getState().currentEvent?.options).toHaveLength(2);

      // Simulate choice selection - clear event, append result
      act(() => {
        useGameStore.getState().appendStoryText('\n\nYou chose to go left...');
        useGameStore.getState().setCurrentEvent(null);
      });

      expect(useGameStore.getState().storyText).toContain('You chose to go left');
      expect(useGameStore.getState().currentEvent).toBeNull();
    });

    it('should handle multiple rounds', () => {
      act(() => {
        // Round 1
        useGameStore.getState().setStoryText('Round 1 story');
        useGameStore.getState().setCurrentEvent({
          story: 'Round 1 story',
          options: [{ text: 'Option' }],
        });
        
        // Clear and start round 2
        useGameStore.getState().setStoryText('Round 2 story');
        useGameStore.getState().setCurrentEvent({
          story: 'Round 2 story',
          options: [{ text: 'Option' }],
        });
      });

      expect(useGameStore.getState().storyText).toBe('Round 2 story');
    });

    it('should reset all play state on resetGame', () => {
      act(() => {
        useGameStore.setState({
          storyText: 'Story',
          currentEvent: { story: 'Event', options: [] },
          progress: { week: 10 },
          roundInfo: { current_round: 5 },
          isGameOver: true,
        });
        useGameStore.getState().resetGame();
      });

      const state = useGameStore.getState();
      expect(state.storyText).toBe('');
      expect(state.currentEvent).toBeNull();
      expect(state.progress).toBeNull();
      expect(state.roundInfo).toBeNull();
      expect(state.isGameOver).toBe(false);
    });
  });

  // ==================== Edge Cases ====================
  describe('Edge Cases', () => {
    it('should handle empty event story', () => {
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: '',
          options: [{ text: 'Option' }],
        });
      });
      expect(useGameStore.getState().currentEvent?.story).toBe('');
    });

    it('should handle special characters in story', () => {
      const specialStory = '<script>alert("xss")</script>\n\n"Quotes" & ampersand';
      act(() => {
        useGameStore.getState().setStoryText(specialStory);
      });
      expect(useGameStore.getState().storyText).toBe(specialStory);
    });

    it('should handle rapid state changes', () => {
      act(() => {
        for (let i = 0; i < 100; i++) {
          useGameStore.getState().appendStoryText('a');
        }
      });
      expect(useGameStore.getState().storyText.length).toBe(100);
    });
  });
});
