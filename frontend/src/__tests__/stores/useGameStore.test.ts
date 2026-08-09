/**
 * useGameStore Tests
 * Tests for the game store state management
 */
import { act, renderHook } from '@testing-library/react';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';
import { useGameStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS } from '@/stores/useGameStore';
import { useImageStore } from '@/stores/useImageStore';
import { useGameListStore } from '@/stores/useGameListStore';
import { useEventStore } from '@/stores/useEventStore';
import { useSessionStore } from '@/stores/useSessionStore';
import { useCharacterStore } from '@/stores/useCharacterStore';
import { useSceneImageStore } from '@/stores/useSceneImageStore';

describe('useGameStore', () => {
  beforeEach(() => {
    // Reset all sub-stores before resetting the combined store
    act(() => {
      // Reset sub-stores directly
      useSessionStore.setState({
        gameId: null,
        sessionId: null,
        playerState: null,
        progress: null,
        roundInfo: null,
        isGameOver: false,
        enableSceneImage: true,
      });
      useEventStore.setState({
        currentEvent: null,
        storyText: '',
        lastSummary: null,
      });
      useCharacterStore.setState({
        creationStep: 0,
        characterSettings: {},
        playerName: '',
        lifeVision: '',
        openingStory: '',
        isPresetLoaded: false,
      });
      useGameListStore.setState({
        savedGames: [],
        presets: [],
      });
      useSceneImageStore.setState({
        roundSceneImages: [],
        currentRoundSceneImage: null,
        eventSceneImage: null,
        resultSceneImage: null,
        isLoadingRoundSceneImage: false,
        isRegeneratingRoundScene: false,
        roundSceneRegenerateError: null,
        historySceneImage: null,
        isLoadingHistoryImage: false,
        isGeneratingHistoryImage: false,
        isRegeneratingHistoryImage: false,
      });
      
      // Sync combined store
      useGameStore.getState()._syncFromSubStores();
    });
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue(jsonResponse({ images: [], total: 0 }));
  });

  describe('Initial state', () => {
    it('has correct initial values', () => {
      const state = useGameStore.getState();
      
      expect(state.gameId).toBeNull();
      expect(state.sessionId).toBeNull();
      expect(state.playerState).toBeNull();
      expect(state.progress).toBeNull();
      expect(state.roundInfo).toBeNull();
      expect(state.currentEvent).toBeNull();
      expect(state.storyText).toBe('');
      expect(state.isGameOver).toBe(false);
      expect(state.creationStep).toBe(0);
      expect(state.characterSettings).toEqual({});
      expect(state.playerName).toBe('');
      expect(state.lifeVision).toBe('');
    });
  });

  describe('Game session management', () => {
    it('sets game session', () => {
      act(() => {
        useGameStore.getState().setGameSession(123, 'session-456');
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBe(123);
      expect(state.sessionId).toBe('session-456');
    });

    it('resets game', () => {
      act(() => {
        useGameStore.getState().setGameSession(123, 'session-456');
        useGameStore.getState().setStoryText('Some story');
        useGameStore.getState().resetGame();
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBeNull();
      expect(state.sessionId).toBeNull();
      expect(state.storyText).toBe('');
    });
  });

  describe('Story text management', () => {
    it('sets story text', () => {
      act(() => {
        useGameStore.getState().setStoryText('Test story');
      });

      expect(useGameStore.getState().storyText).toBe('Test story');
    });

    it('appends story text', () => {
      act(() => {
        useGameStore.getState().setStoryText('Hello');
        useGameStore.getState().appendStoryText(' World');
      });

      expect(useGameStore.getState().storyText).toBe('Hello World');
    });

    it('clears story text', () => {
      act(() => {
        useGameStore.getState().setStoryText('Test');
        useGameStore.getState().setStoryText('');
      });

      expect(useGameStore.getState().storyText).toBe('');
    });
  });

  describe('Current event management', () => {
    it('sets current event', () => {
      const event = {
        story: 'Test story',
        options: [{ text: 'Option 1' }, { text: 'Option 2' }],
      };

      act(() => {
        useGameStore.getState().setCurrentEvent(event);
      });

      const state = useGameStore.getState();
      expect(state.currentEvent).toEqual(event);
    });

    it('clears current event', () => {
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'Test',
          options: [],
        });
        useGameStore.getState().clearCurrentEvent();
      });

      const state = useGameStore.getState();
      expect(state.currentEvent).toBeNull();
      expect(state.storyText).toBe('');
    });

    it('sets null event', () => {
      act(() => {
        useGameStore.getState().setCurrentEvent({
          story: 'Test',
          options: [],
        });
        useGameStore.getState().setCurrentEvent(null);
      });

      expect(useGameStore.getState().currentEvent).toBeNull();
    });
  });

  describe('Game over state', () => {
    it('sets game over to true', () => {
      act(() => {
        useGameStore.getState().setGameOver(true);
      });

      expect(useGameStore.getState().isGameOver).toBe(true);
    });

    it('sets game over to false', () => {
      act(() => {
        useGameStore.getState().setGameOver(true);
        useGameStore.getState().setGameOver(false);
      });

      expect(useGameStore.getState().isGameOver).toBe(false);
    });
  });

  describe('Character creation', () => {
    it('has correct creation steps', () => {
      // CREATION_STEPS only contains user-interactive steps
      expect(CREATION_STEPS).toEqual(['era', 'age', 'gender', 'world', 'portrait']);
    });

    it('has correct manual steps', () => {
      expect(MANUAL_STEPS).toEqual(['era', 'age', 'gender', 'world', 'portrait']);
    });

    it('has correct auto advance steps', () => {
      expect(AUTO_ADVANCE_STEPS).toEqual(['family', 'relationships', 'traits', 'wealth']);
    });

    it('sets player name', () => {
      act(() => {
        useGameStore.getState().setPlayerName('TestPlayer');
      });

      expect(useGameStore.getState().playerName).toBe('TestPlayer');
    });

    it('sets life vision', () => {
      act(() => {
        useGameStore.getState().setLifeVision('Test Vision');
      });

      expect(useGameStore.getState().lifeVision).toBe('Test Vision');
    });

    it('updates character setting', () => {
      act(() => {
        useGameStore.getState().updateCharacterSetting('era', { era: 'modern' });
      });

      expect(useGameStore.getState().characterSettings.era).toEqual({ era: 'modern' });
    });

    it('increments creation step', () => {
      act(() => {
        useGameStore.getState().nextCreationStep();
      });

      expect(useGameStore.getState().creationStep).toBe(1);
    });

    it('decrements creation step', () => {
      act(() => {
        useGameStore.getState().setCreationStep(3);
        useGameStore.getState().prevCreationStep();
      });

      expect(useGameStore.getState().creationStep).toBe(2);
    });

    it('does not decrement below 0', () => {
      act(() => {
        useGameStore.getState().prevCreationStep();
      });

      expect(useGameStore.getState().creationStep).toBe(0);
    });

    it('does not increment beyond max steps', () => {
      act(() => {
        useGameStore.getState().setCreationStep(CREATION_STEPS.length - 1);
        useGameStore.getState().nextCreationStep();
      });

      expect(useGameStore.getState().creationStep).toBe(CREATION_STEPS.length - 1);
    });

    it('resets creation', () => {
      act(() => {
        useGameStore.getState().setPlayerName('Test');
        useGameStore.getState().setLifeVision('Vision');
        useGameStore.getState().setCreationStep(5);
        useGameStore.getState().updateCharacterSetting('era', { era: 'modern' });
        useGameStore.getState().resetCreation();
      });

      const state = useGameStore.getState();
      expect(state.playerName).toBe('');
      expect(state.lifeVision).toBe('');
      expect(state.creationStep).toBe(0);
      expect(state.characterSettings).toEqual({});
    });
  });

  describe('Preset management', () => {
    it('loads preset', () => {
      const preset = {
        preset_id: 1,
        preset_name: 'Test Preset',
        player_name: 'Preset Player',
        life_vision: 'Preset Vision',
        character_settings: { era: { era: 'future' } },
        created_at: '2024-01-15T10:00:00Z',
      };

      act(() => {
        useGameStore.getState().loadPreset(preset);
      });

      const state = useGameStore.getState();
      expect(state.playerName).toBe('Preset Player');
      expect(state.lifeVision).toBe('Preset Vision');
      expect(state.characterSettings).toEqual({ era: { era: 'future' } });
      expect(state.isPresetLoaded).toBe(true);
    });
  });

  describe('Summary management', () => {
    it('clears summary', () => {
      act(() => {
        // Manually set a summary first
        useGameStore.setState({ lastSummary: { summary: 'test' } });
        useGameStore.getState().clearSummary();
      });

      expect(useGameStore.getState().lastSummary).toBeNull();
    });
  });

  describe('generateRoundSceneImage', () => {
    it('does nothing when gameId is null', async () => {
      await act(async () => {
        await useGameStore.getState().generateRoundSceneImage(1, 'test story');
      });

      // Should not throw
      expect(useGameStore.getState().currentRoundSceneImage).toBeNull();
    });

    it('does nothing when storyText is empty', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      await act(async () => {
        await useGameStore.getState().generateRoundSceneImage(1, '');
      });

      // Should not throw
      expect(useGameStore.getState().currentRoundSceneImage).toBeNull();
    });

    it('does nothing when enableSceneImage is false', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.getState().setEnableSceneImage(false);
      });

      await act(async () => {
        await useGameStore.getState().generateRoundSceneImage(1, 'test story');
      });

      // Should not generate
      expect(useGameStore.getState().currentRoundSceneImage).toBeNull();
    });
  });

  describe('loadGameState', () => {
    it('loads game state successfully', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 42,
        player_state: { player_name: 'TestPlayer', age: 25 },
        progress: { week: 10 },
        round_info: { current_round: 5 },
        current_event: null,
      }));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/games/42', expect.objectContaining({ credentials: 'include' }));
      expect(useGameStore.getState().playerState).toEqual({ player_name: 'TestPlayer', age: 25 });
    });

    it('loads game state with current event', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 42,
        player_state: { player_name: 'TestPlayer' },
        progress: { week: 10 },
        round_info: { current_round: 5 },
        current_event: {
          event_description: 'Test event',
          options: [{ text: 'Option 1' }, { text: 'Option 2' }],
        },
      }));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      expect(useGameStore.getState().currentEvent).toEqual({
        story: 'Test event',
        options: [{ text: 'Option 1' }, { text: 'Option 2' }],
      });
    });

    it('restores story from last_round_full_story when no current event', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          last_round_full_story: 'Last round story content here',
        },
        progress: { week: 10 },
        round_info: { current_round: 5 },
        current_event: null,
      }));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      expect(useGameStore.getState().storyText).toBe('Last round story content here');
    });

    it('restores story from round_history when no last_round_full_story', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          round_history: [
            { event_description: 'Event 1', story_continuation: 'Continuation 1' },
          ],
        },
        progress: { week: 10 },
        round_info: { current_round: 5 },
        current_event: null,
      }));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      expect(useGameStore.getState().storyText).toContain('Event 1');
    });

    it('does not restore story from stale progression data when current round does not align', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          current_event_data: { event_description: 'current round in progress' },
          last_round_full_story: 'Old stale story',
          round_history: [{ week: 1, round: 0, event_description: 'Old story', story_continuation: 'Old continuation' }],
        },
        progress: { week: 5, current_round: 3, rounds_per_week: 3 },
        round_info: { current_round: 3, week: 5 },
        current_event: null,
      }));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      expect(useGameStore.getState().storyText).toBe('');
    });
  });

  describe('syncState', () => {
    it('syncs state successfully', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: { player_name: 'SyncedPlayer' },
        progress: { week: 20 },
        round_info: { current_round: 10 },
        current_event: null,
      }));

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(useGameStore.getState().playerState).toEqual({ player_name: 'SyncedPlayer' });
    });

    it('recovers backend-completed event over stale local generating story', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.getState().setStoryText('AI 正在分析你的选择...');
        useGameStore.getState().setCurrentEvent({
          story: 'AI 正在分析你的选择...',
          options: [{ text: '旧选项，不应继续显示' }],
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: {
          player_name: 'RecoveredPlayer',
          life_vision: '',
          energy: 100,
          mood: 100,
          knowledge: 0,
          wealth: 0,
          age: 18,
          week: 2,
          current_round: 1,
          rounds_per_week: 3,
          character_settings: {},
        },
        progress: { week: 2, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 2 },
        current_event: {
          event_description: '后端已经完成的新故事正文。',
          options: [{ text: '查看账册' }, { text: '去码头追问' }],
        },
      }));

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(useGameStore.getState().storyText).toBe('后端已经完成的新故事正文。');
      expect(useGameStore.getState().currentEvent).toEqual({
        story: '后端已经完成的新故事正文。',
        options: [{ text: '查看账册' }, { text: '去码头追问' }],
      });
    });
  });

  describe('syncPlayerState', () => {
    it('syncs player state without returning response', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      const mockResponse = {
        player_state: { player_name: 'Player' },
        progress: { week: 5 },
        round_info: { current_round: 2 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      await act(async () => {
        await useGameStore.getState().syncPlayerState();
      });

      // syncPlayerState now returns void, state is updated directly in store
      expect(global.fetch).toHaveBeenCalledWith('/api/games/42', expect.objectContaining({ credentials: 'include' }));
    });
  });

  describe('shallowChanged helper', () => {
    it('detects changes in key fields', () => {
      // Test through syncState behavior
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.setState({
          playerState: { player_name: 'Test', life_vision: '', energy: 50, mood: 80, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} },
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        player_state: { energy: 60, mood: 80 }, // energy changed
        progress: { week: 5 },
        round_info: { current_round: 2 },
        current_event: null,
      }));

      // Should update because energy changed
      expect(useGameStore.getState().playerState).toEqual({ player_name: 'Test', life_vision: '', energy: 50, mood: 80, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} });
    });
  });

  describe('API integration', () => {
    it('fetches saved games', async () => {
      const mockGames = [
        { game_id: 1, player_name: 'Test', age: 25, week: 10, updated_at: '' },
      ];
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockGames));

      await act(async () => {
        await useGameStore.getState().fetchSavedGames();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/games', expect.objectContaining({ credentials: 'include' }));
      expect(useGameStore.getState().savedGames).toEqual(mockGames);
    });

    it('fetches presets', async () => {
      const mockPresets = [
        { preset_id: 1, preset_name: 'Test', player_name: 'Player', character_settings: {} },
      ];
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockPresets));

      await act(async () => {
        await useGameStore.getState().fetchPresets();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/presets', expect.objectContaining({ credentials: 'include' }));
      expect(useGameStore.getState().presets).toEqual(mockPresets);
    });

    it('deletes game', async () => {
      // Set savedGames in sub-store first
      act(() => {
        useGameListStore.setState({
          savedGames: [
            { game_id: 1, player_name: 'Test1', age: 20, week: 5, updated_at: '', created_at: '' },
            { game_id: 2, player_name: 'Test2', age: 25, week: 10, updated_at: '', created_at: '' },
          ],
        });
        useGameStore.getState()._syncFromSubStores();
      });

      await act(async () => {
        await useGameStore.getState().deleteGame(1);
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/games/1', expect.objectContaining({ method: 'DELETE' }));
      expect(useGameStore.getState().savedGames).toHaveLength(1);
      expect(useGameStore.getState().savedGames[0].game_id).toBe(2);
    });

    it('deletes preset', async () => {
      // Set presets in sub-store first
      act(() => {
        useGameListStore.setState({
          presets: [
            { preset_id: 1, preset_name: 'Test1', player_name: 'P1', character_settings: {}, life_vision: '', created_at: '' },
            { preset_id: 2, preset_name: 'Test2', player_name: 'P2', character_settings: {}, life_vision: '', created_at: '' },
          ],
        });
        useGameStore.getState()._syncFromSubStores();
      });

      await act(async () => {
        await useGameStore.getState().deletePreset(1);
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/presets/1', expect.objectContaining({ method: 'DELETE' }));
      expect(useGameStore.getState().presets).toHaveLength(1);
      expect(useGameStore.getState().presets[0].preset_id).toBe(2);
    });

    it('saves game', async () => {
      act(() => {
        useGameStore.getState().setGameSession(123, 'session-123');
      });

      await act(async () => {
        await useGameStore.getState().saveGame();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/games/123/save', expect.objectContaining({ method: 'POST' }));
    });

    it('does not save game without gameId', async () => {
      await act(async () => {
        await useGameStore.getState().saveGame();
      });

      expect(global.fetch).not.toHaveBeenCalledWith('/api/games/123/save', expect.anything());
    });
  });

  describe('Opening story', () => {
    it('sets opening story', () => {
      act(() => {
        useGameStore.getState().setOpeningStory('Once upon a time...');
      });

      expect(useGameStore.getState().openingStory).toBe('Once upon a time...');
    });
  });

  // ==================== 新增测试：核心方法覆盖 ====================

  describe('loadGameState', () => {
    it('loads game state normally', async () => {
      const mockState = {
        game_id: 42,
        player_state: { player_name: 'TestPlayer', age: 25 },
        progress: { week: 5, current_round: 10 },
        round_info: { current_round: 10, week: 5 },
        current_event: {
          event_description: 'Test event story',
          options: [{ text: 'Option 1' }, { text: 'Option 2' }],
        },
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBe(42);
      expect(state.playerState).toEqual(mockState.player_state);
      expect(state.progress).toEqual(mockState.progress);
      expect(state.currentEvent?.story).toBe('Test event story');
      expect(state.storyText).toBe('Test event story');
    });

    it('restores story from last_round_full_story when no current_event', async () => {
      const mockState = {
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          last_round_full_story: 'Last round story from backend',
        },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      expect(useGameStore.getState().storyText).toBe('Last round story from backend');
    });

    it('restores story from round_history when no last_round_full_story', async () => {
      const mockState = {
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          round_history: [
            { event_description: 'Event 1', story_continuation: 'Continuation 1' },
            { event_description: 'Event 2', story_continuation: 'Continuation 2' },
          ],
        },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      expect(useGameStore.getState().storyText).toBe('Event 2\n\nContinuation 2');
    });
  });

  describe('syncState', () => {
    it('syncs state normally', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      const mockState = {
        player_state: { player_name: 'Test', age: 26, energy: 80 },
        progress: { week: 6, current_round: 11 },
        round_info: { current_round: 11, week: 6 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/games/42', expect.objectContaining({ credentials: 'include' }));
    });

    it('recovers from session 404 by reloading game', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'expired-session');
      });

      const error404 = { status: 404, message: 'Session not found' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(404));

      const mockReloadedState = {
        game_id: 42,
        player_state: { player_name: 'Reloaded' },
        progress: { week: 1 },
        round_info: { current_round: 1 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockReloadedState));

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/games/42', expect.objectContaining({ credentials: 'include' }));
    });

    it('clears state when game no longer exists', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.getState().setCurrentEvent({
          story: 'Some story',
          options: [{ text: 'Continue' }],
        });
      });

      const error404 = { status: 404, message: 'Session not found' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(404));

      const error404Reload = { status: 404, message: 'Game not found' };
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(404));

      await act(async () => {
        try {
          await useGameStore.getState().syncState();
        } catch (e) {
          // Expected to throw
        }
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBeNull();
      expect(state.playerState).toBeNull();
      expect(state.currentEvent).toBeNull();
      expect(state.storyText).toBe('');
    });

    it('does not clear a newer facade event when a legacy sync rejects after session reset', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.getState().setCurrentEvent({
          story: 'Old game story',
          options: [{ text: 'Old choice' }],
        });
      });

      const originalSyncState = useSessionStore.getState().syncState;
      let rejectLegacySync!: (reason: unknown) => void;
      useSessionStore.setState({
        syncState: jest.fn(() => new Promise((_resolve, reject) => {
          rejectLegacySync = reject;
        })),
      } as never);

      try {
        const legacySync = useGameStore.getState().syncState();
        const newerEvent = {
          story: 'New game story',
          options: [{ text: 'New choice' }],
        };

        act(() => {
          useSessionStore.setState({ gameId: null });
          useGameStore.setState({
            gameId: 99,
            currentEvent: newerEvent,
            storyText: newerEvent.story,
          });
        });

        rejectLegacySync(Object.assign(new Error('Game not found'), { status: 404 }));
        await expect(legacySync).resolves.toBeUndefined();
        expect(useGameStore.getState()).toEqual(expect.objectContaining({
          gameId: 99,
          currentEvent: newerEvent,
          storyText: newerEvent.story,
        }));
      } finally {
        useSessionStore.setState({ syncState: originalSyncState } as never);
      }
    });

    it('does nothing when gameId is null', async () => {
      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(global.fetch).not.toHaveBeenCalledWith('/api/games/42', expect.anything());
    });
  });

  describe('syncPlayerState', () => {
    it('syncs player state normally', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      const mockState = {
        player_state: { player_name: 'Test', energy: 90 },
        progress: { week: 7 },
        round_info: { current_round: 12 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

      await act(async () => {
        await useGameStore.getState().syncPlayerState();
      });

      // Verify the API was called - syncPlayerState now returns void
      expect(global.fetch).toHaveBeenCalledWith('/api/games/42', expect.objectContaining({ credentials: 'include' }));
    });

    it('reloads game on session 404', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'expired-session');
        useGameStore.getState().setCurrentEvent({ story: 'Test', options: [] });
      });

      const error404 = { status: 404, message: 'Session expired' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(404));

      const mockReloadedState = {
        game_id: 42,
        player_state: { player_name: 'Reloaded' },
        progress: { week: 1 },
        round_info: { current_round: 1 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockReloadedState));

      await act(async () => {
        await useGameStore.getState().syncPlayerState();
      });

      const state = useGameStore.getState();
      expect(state.currentEvent).toBeNull();
      expect(state.storyText).toBe('');
    });

    it('does nothing when gameId is null', async () => {
      let result;
      await act(async () => {
        result = await useGameStore.getState().syncPlayerState();
      });

      expect(result).toBeUndefined();
      expect(global.fetch).not.toHaveBeenCalledWith('/api/games/42', expect.anything());
    });
  });

  // ★ 玩家形象和开场插画测试已移至 useImageStore.test.ts

  describe('fetchRoundSceneImage branches', () => {
    it('adds new scene when not existing', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.setState({ roundSceneImages: [] });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
          scene_id: 1,
          round_number: 5,
          image_url: 'url',
          scene_description: 'Scene',
          created_at: '2024-01-01T00:00:00Z',
        }));

      await act(async () => {
        await useGameStore.getState().fetchRoundSceneImage(5);
      });

      expect(useGameStore.getState().roundSceneImages).toHaveLength(1);
    });

    it('fetchAllRoundSceneImages sets currentScene based on roundInfo', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        // Set roundInfo in sub-store
        useSessionStore.setState({
          roundInfo: { current_round: 5, week: 2 },
          progress: { week: 2, current_round: 5, rounds_per_week: 3 },
        });
        useGameStore.getState()._syncFromSubStores();
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
          scenes: [
            { scene_id: 1, week: 2, round_number: 4, stage: 'result', image_url: 'url1' },
            { scene_id: 2, week: 2, round_number: 5, stage: 'result', image_url: 'url2' },
          ],
        }));

      await act(async () => {
        await useGameStore.getState().fetchAllRoundSceneImages();
      });

      expect(useGameStore.getState().currentRoundSceneImage?.round_number).toBe(5);
    });

    it('regenerateRoundSceneImage updates scene', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        // ★ 使用 useImageStore 设置玩家形象
        useImageStore.getState().setPlayerImages([{
          image_id: 1,
          image_url: 'url',
          image_type: 'player'
        }]);
        useImageStore.getState().setSelectedImageIndex(0);
        
        // ★ useGameStore 只设置自己管理的状态
        useGameStore.setState({
          storyText: 'Test story',
          characterSettings: { era: { era: 'modern' } },
          playerName: 'Test',
          currentRoundSceneImage: {
            scene_id: 1,
            week: 1,
            round_number: 5,
            stage: 'event',
            image_url: 'old-url',
            scene_description: 'Old',
            referenced_images: [],
            created_at: '2024-01-01T00:00:00Z',
          },
          roundSceneImages: [{
            scene_id: 1,
            week: 1,
            round_number: 5,
            stage: 'event',
            image_url: 'old-url',
            scene_description: 'Old',
            referenced_images: [],
            created_at: '2024-01-01T00:00:00Z',
          }],
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
          image_id: 2,
          image_url: 'new-url',
          scene_description: 'New scene',
          created_at: '2024-01-02T00:00:00Z',
        }));

      await act(async () => {
        await useGameStore.getState().regenerateRoundSceneImage(5, 'make it darker');
      });

      expect(useGameStore.getState().isRegeneratingRoundScene).toBe(false);
    });

    it('regenerateRoundSceneImage handles error', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        // Set scene image in sub-store
        useSceneImageStore.setState({
          currentRoundSceneImage: {
            scene_id: 1,
            week: 1,
            round_number: 5,
            stage: 'event',
            image_url: 'url',
            scene_description: 'Scene',
            referenced_images: [],
            created_at: '2024-01-01T00:00:00Z',
          },
        });
        useGameStore.getState()._syncFromSubStores();
      });

      (global.fetch as jest.Mock).mockRejectedValue(new Error('Regen failed'));

      await act(async () => {
        await useGameStore.getState().regenerateRoundSceneImage(5, 'prompt');
      });

      expect(useGameStore.getState().roundSceneRegenerateError).toBe('Regen failed');
    });
  });

  describe('Additional session recovery tests', () => {
    describe('syncState edge cases', () => {
      it('handles non-404 errors without reload', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const error500 = { status: 500, message: 'Server error' };
        (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(400));

        await expect(
          useGameStore.getState().syncState()
        ).rejects.toBeDefined();
      });

      it('handles 404 in message but not status', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const errorWith404Message = { message: 'Error 404: Not found' };
        (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(404));

        const mockReloadedState = {
          game_id: 42,
          player_state: { player_name: 'Reloaded' },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: null,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockReloadedState));

        await act(async () => {
          await useGameStore.getState().syncState();
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/games/42', expect.objectContaining({ credentials: 'include' }));
      });

      it('updates state when shallowChanged returns true', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
          useGameStore.setState({ playerState: { player_name: 'Test', life_vision: '', energy: 50, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} } });
        });

        const mockState = {
          player_state: { energy: 100, mood: 'happy' },
          progress: { week: 5 },
          round_info: { current_round: 10 },
          current_event: null,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

        await act(async () => {
          await useGameStore.getState().syncState();
        });

        const state = useGameStore.getState();
        expect(state.playerState?.energy).toBe(100);
      });

      it('updates currentEvent when new options arrive', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
          useGameStore.getState().setCurrentEvent({ story: 'Old story', options: [] });
        });

        const mockState = {
          player_state: { player_name: 'Test' },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: {
            event_description: 'New event',
            options: [{ text: 'Option 1' }, { text: 'Option 2' }],
          },
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

        await act(async () => {
          await useGameStore.getState().syncState();
        });

        const state = useGameStore.getState();
        expect(state.currentEvent?.options).toHaveLength(2);
      });

      it('does not update when no changes detected', async () => {
        const existingState = {
          player_state: { energy: 50 },
          progress: { week: 5, current_round: 10 },
          round_info: { current_round: 10, week: 5 },
        };
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
          useGameStore.setState({
            playerState: { player_name: '', life_vision: '', energy: 50, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 5, current_round: 10, rounds_per_week: 3, character_settings: {} },
            progress: { week: 5, current_round: 10, rounds_per_week: 3 },
            roundInfo: { current_round: 10, week: 5 },
          });
        });

        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(existingState));

        await act(async () => {
          await useGameStore.getState().syncState();
        });

        // State should remain the same
        const state = useGameStore.getState();
        expect(state.playerState?.energy).toBe(50);
      });
    });

    describe('syncPlayerState edge cases', () => {
      it('handles non-404 errors', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const error500 = { status: 500, message: 'Server error' };
        (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(400));

        await expect(
          useGameStore.getState().syncPlayerState()
        ).rejects.toBeDefined();
      });

      it('handles 404 with message string', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const errorWith404Message = { message: 'Request failed with 404' };
        (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(404));

        const mockReloadedState = {
          game_id: 42,
          player_state: { player_name: 'Reloaded' },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: null,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockReloadedState));

        await act(async () => {
          await useGameStore.getState().syncPlayerState();
        });

        expect(useGameStore.getState().currentEvent).toBeNull();
        expect(useGameStore.getState().storyText).toBe('');
      });

      it('throws error when reload fails with non-404', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const error404 = { status: 404 };
        (global.fetch as jest.Mock).mockResolvedValueOnce(errorResponse(404));
        const error500 = { status: 500 };
        (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400));

        await expect(
          useGameStore.getState().syncPlayerState()
        ).rejects.toBeDefined();
      });

      it('returns state when sync succeeds', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const mockState = {
          player_state: { energy: 100 },
          progress: { week: 5 },
          round_info: { current_round: 10 },
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockState));

        await act(async () => {
          await useGameStore.getState().syncPlayerState();
        });

        // Verify API was called - syncPlayerState now returns void
        expect(global.fetch).toHaveBeenCalledWith('/api/games/42', expect.objectContaining({ credentials: 'include' }));
      });
    });

    describe('loadGameState edge cases', () => {
      it('handles load without existing event', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const mockLoadedGame = {
          game_id: 42,
          player_state: { player_name: 'Test' },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: null,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockLoadedGame));

        await act(async () => {
          await useGameStore.getState().loadGameState(42);
        });

        const state = useGameStore.getState();
        expect(state.playerState?.player_name).toBe('Test');
        expect(state.currentEvent).toBeNull();
      });

      it('handles load with event having options', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const mockLoadedGame = {
          game_id: 42,
          player_state: { player_name: 'Test' },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: {
            event_description: 'Test event',
            options: [{ text: 'Option 1' }],
          },
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockLoadedGame));

        await act(async () => {
          await useGameStore.getState().loadGameState(42);
        });

        const state = useGameStore.getState();
        expect(state.currentEvent?.story).toBe('Test event');
        expect(state.currentEvent?.options).toHaveLength(1);
      });

      it('handles load with last_round_full_story', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const mockLoadedGame = {
          game_id: 42,
          player_state: { player_name: 'Test', last_round_full_story: 'Previous round story...' },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: null,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockLoadedGame));

        await act(async () => {
          await useGameStore.getState().loadGameState(42);
        });

        const state = useGameStore.getState();
        expect(state.storyText).toBe('Previous round story...');
      });

      it('handles load with round_history but no last_round_full_story', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const mockLoadedGame = {
          game_id: 42,
          player_state: {
            player_name: 'Test',
            round_history: [{ event_description: 'Round 1 story...', story_continuation: '' }]
          },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: null,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockLoadedGame));

        await act(async () => {
          await useGameStore.getState().loadGameState(42);
        });

        const state = useGameStore.getState();
        expect(state.storyText).toBe('Round 1 story...');
      });

      it('handles load with round_history and story_continuation', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        const mockLoadedGame = {
          game_id: 42,
          player_state: {
            player_name: 'Test',
            round_history: [{ event_description: 'Event happened', story_continuation: 'Story continued' }]
          },
          progress: { week: 1 },
          round_info: { current_round: 1 },
          current_event: null,
        };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockLoadedGame));

        await act(async () => {
          await useGameStore.getState().loadGameState(42);
        });

        const state = useGameStore.getState();
        expect(state.storyText).toContain('Event happened');
        expect(state.storyText).toContain('Story continued');
      });

      it('restores current event story when backend returns options with empty event text', async () => {
        act(() => {
          useGameStore.getState().setGameSession(42, 'session-42');
        });

        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
          game_id: 42,
          player_state: {
            player_name: 'Test',
            last_round_full_story: 'Recovered visible story body.',
          },
          progress: { week: 2 },
          round_info: { current_round: 1 },
          current_event: {
            event_description: '',
            story_text: '',
            options: [{ text: 'Continue from recovered story', effects: {} }],
          },
        }));

        await act(async () => {
          await useGameStore.getState().loadGameState(42);
        });

        const state = useGameStore.getState();
        expect(state.storyText).toBe('Recovered visible story body.');
        expect(state.currentEvent).toEqual({
          story: 'Recovered visible story body.',
          options: [{ text: 'Continue from recovered story', effects: {} }],
        });
      });
    });
  });
});
