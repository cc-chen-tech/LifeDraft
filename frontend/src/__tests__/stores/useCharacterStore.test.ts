/**
 * useCharacterStore Tests
 * Tests for the character creation store
 */
import { act } from '@testing-library/react';
import { 
  useCharacterStore, 
  CREATION_STEPS, 
  MANUAL_STEPS, 
  AUTO_ADVANCE_STEPS 
} from '@/stores/useCharacterStore';
import type { PresetInfo } from '@/lib/types';

describe('useCharacterStore', () => {
  beforeEach(() => {
    act(() => {
      useCharacterStore.getState().resetCreation();
    });
  });

  describe('Initial state', () => {
    it('has correct initial values', () => {
      const state = useCharacterStore.getState();
      expect(state.creationStep).toBe(0);
      expect(state.characterSettings).toEqual({});
      expect(state.playerName).toBe('');
      expect(state.lifeVision).toBe('');
      expect(state.openingStory).toBe('');
      expect(state.isPresetLoaded).toBe(false);
    });
  });

  describe('Constants', () => {
    it('has correct creation steps', () => {
      expect(CREATION_STEPS).toEqual(['era', 'age', 'gender', 'world', 'portrait']);
    });

    it('has correct manual steps', () => {
      expect(MANUAL_STEPS).toEqual(['era', 'age', 'gender', 'world', 'portrait']);
    });

    it('has correct auto advance steps', () => {
      expect(AUTO_ADVANCE_STEPS).toEqual(['family', 'relationships', 'traits', 'wealth']);
    });
  });

  describe('Step navigation', () => {
    it('sets creation step', () => {
      act(() => {
        useCharacterStore.getState().setCreationStep(2);
      });
      expect(useCharacterStore.getState().creationStep).toBe(2);
    });

    it('moves to next step', () => {
      act(() => {
        useCharacterStore.getState().nextCreationStep();
      });
      expect(useCharacterStore.getState().creationStep).toBe(1);
    });

    it('moves to previous step', () => {
      act(() => {
        useCharacterStore.getState().setCreationStep(2);
        useCharacterStore.getState().prevCreationStep();
      });
      expect(useCharacterStore.getState().creationStep).toBe(1);
    });

    it('does not go below 0', () => {
      act(() => {
        useCharacterStore.getState().prevCreationStep();
      });
      expect(useCharacterStore.getState().creationStep).toBe(0);
    });

    it('does not exceed max steps', () => {
      act(() => {
        useCharacterStore.getState().setCreationStep(10);
        useCharacterStore.getState().nextCreationStep();
      });
      expect(useCharacterStore.getState().creationStep).toBe(CREATION_STEPS.length - 1);
    });
  });

  describe('Character settings', () => {
    it('updates character setting', () => {
      act(() => {
        useCharacterStore.getState().updateCharacterSetting('era', { era_name: 'Modern' });
      });
      expect(useCharacterStore.getState().characterSettings.era).toEqual({ era_name: 'Modern' });
    });

    it('merges character settings', () => {
      act(() => {
        useCharacterStore.getState().updateCharacterSetting('era', { era_name: 'Modern' });
        useCharacterStore.getState().updateCharacterSetting('age', { age: 25 });
      });
      const settings = useCharacterStore.getState().characterSettings;
      expect(settings.era).toEqual({ era_name: 'Modern' });
      expect(settings.age).toEqual({ age: 25 });
    });
  });

  describe('Player info', () => {
    it('sets player name', () => {
      act(() => {
        useCharacterStore.getState().setPlayerName('Test Player');
      });
      expect(useCharacterStore.getState().playerName).toBe('Test Player');
    });

    it('sets life vision', () => {
      act(() => {
        useCharacterStore.getState().setLifeVision('Live happily');
      });
      expect(useCharacterStore.getState().lifeVision).toBe('Live happily');
    });

    it('sets opening story', () => {
      act(() => {
        useCharacterStore.getState().setOpeningStory('Once upon a time...');
      });
      expect(useCharacterStore.getState().openingStory).toBe('Once upon a time...');
    });
  });

  describe('Reset', () => {
    it('resets all creation data', () => {
      act(() => {
        useCharacterStore.getState().setPlayerName('Test');
        useCharacterStore.getState().setLifeVision('Vision');
        useCharacterStore.getState().setCreationStep(3);
        useCharacterStore.getState().updateCharacterSetting('era', { era_name: 'Modern' });
        useCharacterStore.getState().resetCreation();
      });

      const state = useCharacterStore.getState();
      expect(state.creationStep).toBe(0);
      expect(state.characterSettings).toEqual({});
      expect(state.playerName).toBe('');
      expect(state.lifeVision).toBe('');
      expect(state.openingStory).toBe('');
      expect(state.isPresetLoaded).toBe(false);
    });
  });

  describe('Load preset', () => {
    it('loads preset correctly', () => {
      const preset: PresetInfo = {
        preset_id: 1,
        preset_name: 'Test Preset',
        player_name: 'Preset Character',
        life_vision: 'Preset vision',
        character_settings: {
          era: { era_name: 'Ancient' },
          age: { age: 20 },
        },
        created_at: '2024-01-01',
      };

      act(() => {
        useCharacterStore.getState().loadPreset(preset);
      });

      const state = useCharacterStore.getState();
      expect(state.playerName).toBe('Preset Character');
      expect(state.lifeVision).toBe('Preset vision');
      expect(state.characterSettings).toEqual({
        era: { era_name: 'Ancient' },
        age: { age: 20 },
      });
      expect(state.isPresetLoaded).toBe(true);
      expect(state.creationStep).toBe(MANUAL_STEPS.length);
    });

    it('loads preset without life_vision', () => {
      const preset: PresetInfo = {
        preset_id: 2,
        preset_name: 'Test Preset 2',
        player_name: 'No Vision Character',
        life_vision: '', // Empty string - falsy
        character_settings: {
          era: { era_name: 'Modern' },
        },
        created_at: '2024-01-01',
      };

      act(() => {
        useCharacterStore.getState().loadPreset(preset);
      });

      const state = useCharacterStore.getState();
      expect(state.playerName).toBe('No Vision Character');
      expect(state.lifeVision).toBe(''); // Should be empty string
    });

    it('loads preset with undefined life_vision', () => {
      const preset: PresetInfo = {
        preset_id: 3,
        preset_name: 'Test Preset 3',
        player_name: 'Undefined Vision Character',
        life_vision: undefined as unknown as string, // Undefined
        character_settings: {},
        created_at: '2024-01-01',
      };

      act(() => {
        useCharacterStore.getState().loadPreset(preset);
      });

      const state = useCharacterStore.getState();
      expect(state.lifeVision).toBe(''); // Should fallback to empty string
    });
  });
});
