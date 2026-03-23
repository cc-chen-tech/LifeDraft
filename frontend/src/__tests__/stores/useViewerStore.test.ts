/**
 * useViewerStore Tests
 * 
 * Tests for UI/viewing state that may be extracted from useGameStore.
 * Covers: scene images, viewing modes, UI toggles, display preferences.
 */
import { act } from '@testing-library/react';

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
    },
    images: {
      listByGame: jest.fn().mockResolvedValue({ images: [], total: 0 }),
      getRoundSceneImage: jest.fn().mockResolvedValue(null),
      getRoundSceneImageByStage: jest.fn().mockResolvedValue(null),
      getAllRoundSceneImages: jest.fn().mockResolvedValue({ scenes: [] }),
      generateRoundSceneImage: jest.fn().mockResolvedValue({
        scene_id: 1,
        round_number: 1,
        image_url: 'test.png',
        scene_description: 'Test scene',
        created_at: new Date().toISOString(),
      }),
    },
  },
}));

import { useGameStore } from '@/stores/useGameStore';
import api from '@/lib/api';

describe('useViewerStore (UI/Viewing State)', () => {
  beforeEach(() => {
    act(() => {
      useGameStore.getState().resetGame();
      useGameStore.getState().resetCreation();
      useGameStore.getState().clearImageCache();
    });
    jest.clearAllMocks();
  });

  // ==================== Scene Image Enable State ====================
  describe('Scene Image Enable State', () => {
    it('should have enableSceneImage as true by default', () => {
      expect(useGameStore.getState().enableSceneImage).toBe(true);
    });

    it('should set enableSceneImage to false', () => {
      act(() => {
        useGameStore.getState().setEnableSceneImage(false);
      });
      expect(useGameStore.getState().enableSceneImage).toBe(false);
    });

    it('should set enableSceneImage back to true', () => {
      act(() => {
        useGameStore.getState().setEnableSceneImage(false);
        useGameStore.getState().setEnableSceneImage(true);
      });
      expect(useGameStore.getState().enableSceneImage).toBe(true);
    });
  });

  // ==================== Round Scene Image State ====================
  describe('Round Scene Image State', () => {
    it('should have empty roundSceneImages initially', () => {
      expect(useGameStore.getState().roundSceneImages).toEqual([]);
    });

    it('should have null currentRoundSceneImage initially', () => {
      expect(useGameStore.getState().currentRoundSceneImage).toBeNull();
    });

    it('should have null eventSceneImage initially', () => {
      expect(useGameStore.getState().eventSceneImage).toBeNull();
    });

    it('should have null resultSceneImage initially', () => {
      expect(useGameStore.getState().resultSceneImage).toBeNull();
    });

    it('should add round scene image', () => {
      const sceneImage = {
        scene_id: 1,
        week: 1,
        round_number: 1,
        stage: 'event',
        image_url: 'test.png',
        scene_description: 'Test scene',
        referenced_images: [],
        created_at: new Date().toISOString(),
      };
      act(() => {
        useGameStore.getState().addRoundSceneImage(sceneImage);
      });
      expect(useGameStore.getState().roundSceneImages).toHaveLength(1);
      expect(useGameStore.getState().roundSceneImages[0]).toEqual(sceneImage);
    });

    it('should set currentRoundSceneImage', () => {
      const sceneImage = {
        scene_id: 1,
        week: 1,
        round_number: 1,
        stage: 'result',
        image_url: 'test.png',
        scene_description: 'Test scene',
        referenced_images: [],
        created_at: new Date().toISOString(),
      };
      act(() => {
        useGameStore.getState().setCurrentRoundSceneImage(sceneImage);
      });
      expect(useGameStore.getState().currentRoundSceneImage).toEqual(sceneImage);
    });

    it('should set eventSceneImage', () => {
      const sceneImage = {
        scene_id: 2,
        week: 1,
        round_number: 1,
        stage: 'event',
        image_url: 'event.png',
        scene_description: 'Event scene',
        referenced_images: [],
        created_at: new Date().toISOString(),
      };
      act(() => {
        useGameStore.getState().setEventSceneImage(sceneImage);
      });
      expect(useGameStore.getState().eventSceneImage).toEqual(sceneImage);
    });

    it('should set resultSceneImage', () => {
      const sceneImage = {
        scene_id: 3,
        week: 1,
        round_number: 1,
        stage: 'result',
        image_url: 'result.png',
        scene_description: 'Result scene',
        referenced_images: [],
        created_at: new Date().toISOString(),
      };
      act(() => {
        useGameStore.getState().setResultSceneImage(sceneImage);
      });
      expect(useGameStore.getState().resultSceneImage).toEqual(sceneImage);
    });
  });

  // ==================== Loading States ====================
  describe('Loading States', () => {
    it('should have isLoadingRoundSceneImage as false initially', () => {
      expect(useGameStore.getState().isLoadingRoundSceneImage).toBe(false);
    });

    it('should have isRegeneratingRoundScene as false initially', () => {
      expect(useGameStore.getState().isRegeneratingRoundScene).toBe(false);
    });

    it('should have null roundSceneRegenerateError initially', () => {
      expect(useGameStore.getState().roundSceneRegenerateError).toBeNull();
    });
  });

  // ==================== History Scene Image State ====================
  describe('History Scene Image State', () => {
    it('should have null historySceneImage initially', () => {
      expect(useGameStore.getState().historySceneImage).toBeNull();
    });

    it('should have isLoadingHistoryImage as false initially', () => {
      expect(useGameStore.getState().isLoadingHistoryImage).toBe(false);
    });

    it('should have isGeneratingHistoryImage as false initially', () => {
      expect(useGameStore.getState().isGeneratingHistoryImage).toBe(false);
    });

    it('should have isRegeneratingHistoryImage as false initially', () => {
      expect(useGameStore.getState().isRegeneratingHistoryImage).toBe(false);
    });

    it('should set historySceneImage', () => {
      const sceneImage = {
        scene_id: 5,
        week: 2,
        round_number: 3,
        stage: 'result',
        image_url: 'history.png',
        scene_description: 'History scene',
        referenced_images: [],
        created_at: new Date().toISOString(),
      };
      act(() => {
        useGameStore.getState().setHistorySceneImage(sceneImage);
      });
      expect(useGameStore.getState().historySceneImage).toEqual(sceneImage);
    });

    it('should clear historySceneImage by setting null', () => {
      act(() => {
        useGameStore.getState().setHistorySceneImage({
          scene_id: 5,
          week: 2,
          round_number: 3,
          stage: 'result',
          image_url: 'history.png',
          scene_description: 'History scene',
          referenced_images: [],
          created_at: new Date().toISOString(),
        });
        useGameStore.getState().setHistorySceneImage(null);
      });
      expect(useGameStore.getState().historySceneImage).toBeNull();
    });
  });

  // ==================== Clear Image Cache ====================
  describe('Clear Image Cache', () => {
    it('should clear all image-related state', () => {
      const sceneImage = {
        scene_id: 1,
        week: 1,
        round_number: 1,
        stage: 'event',
        image_url: 'test.png',
        scene_description: 'Test',
        referenced_images: [],
        created_at: new Date().toISOString(),
      };

      act(() => {
        useGameStore.setState({
          roundSceneImages: [sceneImage],
          currentRoundSceneImage: sceneImage,
          eventSceneImage: sceneImage,
          resultSceneImage: sceneImage,
          historySceneImage: sceneImage,
          isLoadingRoundSceneImage: true,
          isRegeneratingRoundScene: true,
          roundSceneRegenerateError: 'Error',
        });
        useGameStore.getState().clearImageCache();
      });

      const state = useGameStore.getState();
      expect(state.roundSceneImages).toEqual([]);
      expect(state.currentRoundSceneImage).toBeNull();
      expect(state.eventSceneImage).toBeNull();
      expect(state.resultSceneImage).toBeNull();
      expect(state.historySceneImage).toBeNull();
      expect(state.isLoadingRoundSceneImage).toBe(false);
      expect(state.isRegeneratingRoundScene).toBe(false);
      expect(state.roundSceneRegenerateError).toBeNull();
    });
  });

  // ==================== Fetch Scene Image ====================
  describe('Fetch Scene Image', () => {
    it('should not fetch without gameId', async () => {
      await act(async () => {
        await useGameStore.getState().fetchRoundSceneImage(1);
      });
      expect(api.images.getRoundSceneImage).not.toHaveBeenCalled();
    });

    it('should fetch scene image when gameId is set', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (api.images.getRoundSceneImage as jest.Mock).mockResolvedValue({
        scene_id: 1,
        round_number: 1,
        image_url: 'scene.png',
        scene_description: 'Scene',
        created_at: new Date().toISOString(),
      });

      await act(async () => {
        await useGameStore.getState().fetchRoundSceneImage(1);
      });

      expect(api.images.getRoundSceneImage).toHaveBeenCalled();
    });

    it('should fetch scene image by stage', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (api.images.getRoundSceneImageByStage as jest.Mock).mockResolvedValue({
        scene_id: 1,
        round_number: 1,
        stage: 'event',
        image_url: 'scene.png',
        scene_description: 'Scene',
        created_at: new Date().toISOString(),
      });

      await act(async () => {
        await useGameStore.getState().fetchRoundSceneImage(1, 'event');
      });

      expect(api.images.getRoundSceneImageByStage).toHaveBeenCalled();
    });
  });

  // ==================== Generate Round Scene Image ====================
  describe('Generate Round Scene Image', () => {
    it('should not generate without gameId', async () => {
      await act(async () => {
        await useGameStore.getState().generateRoundSceneImage(1, 'Test story');
      });
      expect(api.images.generateRoundSceneImage).not.toHaveBeenCalled();
    });

    it('should not generate without storyText', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      await act(async () => {
        await useGameStore.getState().generateRoundSceneImage(1, '');
      });

      expect(api.images.generateRoundSceneImage).not.toHaveBeenCalled();
    });

    it('should not generate when enableSceneImage is false', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.getState().setEnableSceneImage(false);
      });

      await act(async () => {
        await useGameStore.getState().generateRoundSceneImage(1, 'Test story');
      });

      expect(api.images.generateRoundSceneImage).not.toHaveBeenCalled();
    });
  });
});
