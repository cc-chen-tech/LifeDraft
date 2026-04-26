/**
 * Tests for useCharacterCreation hook
 * Tests initial state, form field management, generation flow,
 * loading states, error handling, and edge cases.
 */
import { renderHook, act, waitFor } from '@testing-library/react';

// -- Mock next/navigation --
const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

// -- Mock stores --
const mockGameStoreState = {
  creationStep: 0,
  characterSettings: {} as Record<string, unknown>,
  playerName: '',
  lifeVision: '',
  isPresetLoaded: false,
  gameId: null as number | null,
  sessionId: null as string | null,
};

const mockGameStoreFunctions = {
  setCreationStep: jest.fn(),
  nextCreationStep: jest.fn(),
  prevCreationStep: jest.fn(),
  updateCharacterSetting: jest.fn(),
  setPlayerName: jest.fn(),
  setLifeVision: jest.fn(),
  resetCreation: jest.fn(),
  setGameSession: jest.fn(),
};

jest.mock('@/stores/useGameStore', () => {
  const CREATION_STEPS = ['era', 'age', 'gender', 'world', 'portrait'];
  const MANUAL_STEPS = ['era', 'age', 'gender', 'world', 'portrait'];
  const AUTO_ADVANCE_STEPS = ['family', 'relationships', 'traits', 'wealth'];

  return {
    useGameStore: Object.assign(
      (selector?: (state: typeof mockGameStoreState & typeof mockGameStoreFunctions) => unknown) => {
        const fullState = { ...mockGameStoreState, ...mockGameStoreFunctions };
        if (selector) return selector(fullState);
        return fullState;
      },
      {
        getState: () => ({ ...mockGameStoreState, ...mockGameStoreFunctions }),
      }
    ),
    CREATION_STEPS,
    MANUAL_STEPS,
    AUTO_ADVANCE_STEPS,
  };
});

const mockImageStoreState = {
  playerImages: [] as Array<{ image_id: number; image_url: string }>,
  selectedImageIndex: 0,
  isGeneratingImage: false,
  imageFeedback: '',
  playerImage: null as { image_id: number; image_url: string } | null,
};

const mockImageStoreFunctions = {
  setSelectedImageIndex: jest.fn(),
  setImageFeedback: jest.fn(),
  generatePlayerImage: jest.fn(),
  regeneratePlayerImage: jest.fn(),
  regenerateFreshPlayerImage: jest.fn(),
};

jest.mock('@/stores/useImageStore', () => ({
  useImageStore: Object.assign(
    (selector?: (state: typeof mockImageStoreState & typeof mockImageStoreFunctions) => unknown) => {
      const fullState = { ...mockImageStoreState, ...mockImageStoreFunctions };
      if (selector) return selector(fullState);
      return fullState;
    },
    {
      getState: () => ({ ...mockImageStoreState, ...mockImageStoreFunctions }),
    }
  ),
}));

const mockUIStoreState = {
  language: 'zh' as string,
};

jest.mock('@/stores/useUIStore', () => ({
  useUIStore: Object.assign(
    (selector?: (state: typeof mockUIStoreState) => unknown) => {
      if (selector) return selector(mockUIStoreState);
      return mockUIStoreState;
    },
    {
      getState: () => ({ ...mockUIStoreState }),
    }
  ),
}));

// -- Mock API --
const mockGenerateSetting = jest.fn();
const mockGenerateRelationship = jest.fn();
const mockGenerateRelationshipsSummary = jest.fn();
const mockGameCreate = jest.fn();
const mockPresetCreate = jest.fn();

jest.mock('@/lib/api', () => ({
  character: {
    generateSetting: (...args: unknown[]) => mockGenerateSetting(...args),
    generateRelationship: (...args: unknown[]) => mockGenerateRelationship(...args),
    generateRelationshipsSummary: (...args: unknown[]) => mockGenerateRelationshipsSummary(...args),
  },
  games: {
    create: (...args: unknown[]) => mockGameCreate(...args),
  },
  presets: {
    create: (...args: unknown[]) => mockPresetCreate(...args),
  },
  default: {
    character: {
      generateSetting: (...args: unknown[]) => mockGenerateSetting(...args),
      generateRelationship: (...args: unknown[]) => mockGenerateRelationship(...args),
      generateRelationshipsSummary: (...args: unknown[]) => mockGenerateRelationshipsSummary(...args),
    },
    games: {
      create: (...args: unknown[]) => mockGameCreate(...args),
    },
    presets: {
      create: (...args: unknown[]) => mockPresetCreate(...args),
    },
  },
}));

// Import after mocks
import { useCharacterCreation } from '@/hooks/useCharacterCreation';

describe('useCharacterCreation', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Reset mock store state
    Object.assign(mockGameStoreState, {
      creationStep: 0,
      characterSettings: {},
      playerName: '',
      lifeVision: '',
      isPresetLoaded: false,
      gameId: null,
      sessionId: null,
    });

    Object.assign(mockImageStoreState, {
      playerImages: [],
      selectedImageIndex: 0,
      isGeneratingImage: false,
      imageFeedback: '',
      playerImage: null,
    });

    Object.assign(mockUIStoreState, {
      language: 'zh',
    });

    mockPush.mockClear();
    mockReplace.mockClear();
  });

  // ===================== Initial State =====================

  describe('Initial state', () => {
    it('returns default creationStep as 0', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.creationStep).toBe(0);
    });

    it('returns default characterSettings as empty object', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.characterSettings).toEqual({});
    });

    it('returns empty playerName by default', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerName).toBe('');
    });

    it('returns empty lifeVision by default', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.lifeVision).toBe('');
    });

    it('returns isPresetLoaded as false', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isPresetLoaded).toBe(false);
    });

    it('returns null gameId by default', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.gameId).toBeNull();
    });

    it('returns empty playerImages array', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImages).toEqual([]);
    });

    it('returns selectedImageIndex as 0', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.selectedImageIndex).toBe(0);
    });

    it('returns isGeneratingImage as false', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isGeneratingImage).toBe(false);
    });

    it('returns isGenerating as false', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isGenerating).toBe(false);
    });

    it('returns empty feedback', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.feedback).toBe('');
    });

    it('returns showPresetSheet as false', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.showPresetSheet).toBe(false);
    });

    it('returns empty presetName', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.presetName).toBe('');
    });

    it('returns isSavingPreset as false', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isSavingPreset).toBe(false);
    });

    it('returns null generatedContent', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.generatedContent).toBeNull();
    });

    it('returns null toast', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.toast).toBeNull();
    });

    it('returns autoGenPhase as idle', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.autoGenPhase).toBe('idle');
    });

    it('returns isBackgroundGenerating as false', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isBackgroundGenerating).toBe(false);
    });
  });

  // ===================== Computed Values =====================

  describe('Computed values', () => {
    it('computes currentStepKey from creationStep', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.currentStepKey).toBe('era');
    });

    it('computes currentStepKey when creationStep is 2', () => {
      mockGameStoreState.creationStep = 2;
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.currentStepKey).toBe('gender');
    });

    it('computes isFirstStep as true when creationStep is 0', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isFirstStep).toBe(true);
      expect(result.current.isLastStep).toBe(false);
    });

    it('computes isLastStep as true when on last step', () => {
      mockGameStoreState.creationStep = 4;
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isLastStep).toBe(true);
      expect(result.current.isFirstStep).toBe(false);
    });

    it('computes isPortraitStep as true on portrait step', () => {
      mockGameStoreState.creationStep = 4;
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isPortraitStep).toBe(true);
    });

    it('computes isPortraitStep as false on non-portrait step', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isPortraitStep).toBe(false);
    });

    it('computes hasBasicInfo as false when playerName is empty', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.hasBasicInfo).toBe(false);
    });

    it('computes hasBasicInfo as true when playerName is filled', () => {
      mockGameStoreState.playerName = 'TestPlayer';
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.hasBasicInfo).toBe(true);
    });

    it('computes isManualStep as true for all steps', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isManualStep).toBe(true);
    });
  });

  // ===================== Form Field State Management =====================

  describe('Form field state management', () => {
    it('provides setPlayerName from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setPlayerName('NewName');
      });
      expect(mockGameStoreFunctions.setPlayerName).toHaveBeenCalledWith('NewName');
    });

    it('provides setLifeVision from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setLifeVision('A great vision');
      });
      expect(mockGameStoreFunctions.setLifeVision).toHaveBeenCalledWith('A great vision');
    });

    it('provides updateCharacterSetting from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.updateCharacterSetting('era', { era_name: '古代' });
      });
      expect(mockGameStoreFunctions.updateCharacterSetting).toHaveBeenCalledWith(
        'era',
        { era_name: '古代' }
      );
    });

    it('provides setCreationStep from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setCreationStep(1);
      });
      expect(mockGameStoreFunctions.setCreationStep).toHaveBeenCalledWith(1);
    });

    it('provides setFeedback for local feedback state', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setFeedback('Need more details');
      });
      expect(result.current.feedback).toBe('Need more details');
    });

    it('provides setPresetName for local preset name', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setPresetName('My Preset');
      });
      expect(result.current.presetName).toBe('My Preset');
    });

    it('provides setShowPresetSheet toggle', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setShowPresetSheet(true);
      });
      expect(result.current.showPresetSheet).toBe(true);
    });

    it('provides resetCreation from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.resetCreation();
      });
      expect(mockGameStoreFunctions.resetCreation).toHaveBeenCalled();
    });

    it('provides nextCreationStep from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.nextCreationStep();
      });
      expect(mockGameStoreFunctions.nextCreationStep).toHaveBeenCalled();
    });
  });

  // ===================== Character Generation Flow =====================

  describe('handleGenerate', () => {
    it('does nothing when hasBasicInfo is false (empty playerName)', async () => {
      const { result } = renderHook(() => useCharacterCreation());
      await act(async () => {
        await result.current.handleGenerate();
      });
      expect(mockGenerateSetting).not.toHaveBeenCalled();
    });

    it('calls api.character.generateSetting with correct params', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.lifeVision = 'Become a hero';
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockGenerateSetting.mockResolvedValue({ era_name: '古代', era_description: 'Ancient times' });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(mockGenerateSetting).toHaveBeenCalledWith({
        setting_type: 'era',
        player_name: 'TestPlayer',
        life_vision: 'Become a hero',
        previous_settings: { era: { era_name: '古代' } },
        feedback: null,
        language: 'zh',
      });
    });

    it('sets isGenerating to true during generation', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      let resolvePromise: (value: unknown) => void;
      const promise = new Promise((resolve) => { resolvePromise = resolve; });
      mockGenerateSetting.mockReturnValue(promise);

      const { result } = renderHook(() => useCharacterCreation());

      let generationPromise: Promise<void>;
      await act(async () => {
        generationPromise = result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(true);
      expect(result.current.generatedContent).toBeNull();

      await act(async () => {
        resolvePromise!({ era_name: '古代', era_description: 'Ancient times' });
        await generationPromise!;
      });

      expect(result.current.isGenerating).toBe(false);
    });

    it('sets generatedContent after successful generation', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      const expectedContent = { era_name: '古代', era_description: 'Ancient times' };
      mockGenerateSetting.mockResolvedValue(expectedContent);

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(result.current.generatedContent).toEqual(expectedContent);
    });

    it('handles generation with feedback string', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGenerateSetting.mockResolvedValue({ era_name: '现代' });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate('More specific');
      });

      expect(mockGenerateSetting).toHaveBeenCalledWith(
        expect.objectContaining({ feedback: 'More specific' })
      );
    });
  });

  // ===================== Loading States =====================

  describe('Loading states', () => {
    it('sets isGenerating to false after generation completes', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGenerateSetting.mockResolvedValue({ era_name: '古代' });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(false);
    });

    it('sets isGenerating to false after generation fails', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGenerateSetting.mockRejectedValue(new Error('Network error'));
      jest.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(false);
    });

    it('sets isSavingPreset to true during preset save', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      let resolvePromise: (value: unknown) => void;
      const promise = new Promise((resolve) => { resolvePromise = resolve; });
      mockPresetCreate.mockReturnValue(promise);

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setPresetName('My Preset');
      });

      let savePromise: Promise<void>;
      await act(async () => {
        savePromise = result.current.handleSavePreset();
      });

      expect(result.current.isSavingPreset).toBe(true);

      await act(async () => {
        resolvePromise!({ preset_id: 1 });
        await savePromise!;
      });

      expect(result.current.isSavingPreset).toBe(false);
    });
  });

  // ===================== Error Handling =====================

  describe('Error handling', () => {
    it('shows error toast when generation fails after retries', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGenerateSetting.mockRejectedValue(new Error('API failure'));
      jest.spyOn(console, 'error').mockImplementation(() => {});
      jest.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      await waitFor(() => {
        expect(result.current.toast).toEqual({
          type: 'error',
          message: '生成失败，请重试',
        });
      });
    });

    it('shows error toast when saving preset fails', async () => {
      mockPresetCreate.mockRejectedValue(new Error('Save error'));
      jest.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setPresetName('My Preset');
      });

      await act(async () => {
        await result.current.handleSavePreset();
      });

      await waitFor(() => {
        expect(result.current.toast).toEqual({
          type: 'error',
          message: '保存失败，请重试',
        });
      });
    });

    it('does not save preset when presetName is empty', async () => {
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleSavePreset();
      });

      expect(mockPresetCreate).not.toHaveBeenCalled();
    });
  });

  // ===================== handleRegenerate =====================

  describe('handleRegenerate', () => {
    it('calls handleGenerate with current feedback and clears feedback', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGenerateSetting.mockResolvedValue({ era_name: '古代' });

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setFeedback('Please change era');
      });

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(result.current.feedback).toBe('');
      expect(mockGenerateSetting).toHaveBeenCalledWith(
        expect.objectContaining({ feedback: 'Please change era' })
      );
    });
  });

  // ===================== Constants =====================

  describe('Constants', () => {
    it('exposes STEP_LABELS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.STEP_LABELS).toBeDefined();
      expect(result.current.STEP_LABELS.era).toBe('时代背景');
    });

    it('exposes STEP_DESCRIPTIONS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.STEP_DESCRIPTIONS).toBeDefined();
      expect(result.current.STEP_DESCRIPTIONS.era).toBe('选择你的人生将发生在哪个时代');
    });

    it('exposes CREATION_STEPS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.CREATION_STEPS).toEqual(['era', 'age', 'gender', 'world', 'portrait']);
    });

    it('exposes AUTO_ADVANCE_STEPS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.AUTO_ADVANCE_STEPS).toEqual(['family', 'relationships', 'traits', 'wealth']);
    });
  });

  // ===================== Player Images =====================

  describe('Player images', () => {
    it('returns playerImage as null when no images', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toBeNull();
    });

    it('returns playerImage from selected image', () => {
      mockImageStoreState.playerImages = [
        { image_id: 1, image_url: '/img/1.png' },
        { image_id: 2, image_url: '/img/2.png' },
      ];
      mockImageStoreState.selectedImageIndex = 1;
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toEqual({ image_id: 2, image_url: '/img/2.png' });
    });

    it('falls back to first image when selectedIndex is out of bounds', () => {
      mockImageStoreState.playerImages = [
        { image_id: 1, image_url: '/img/1.png' },
      ];
      mockImageStoreState.selectedImageIndex = 5;
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toEqual({ image_id: 1, image_url: '/img/1.png' });
    });

    it('provides setSelectedImageIndex from image store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setSelectedImageIndex(2);
      });
      expect(mockImageStoreFunctions.setSelectedImageIndex).toHaveBeenCalledWith(2);
    });

    it('provides setImageFeedback from image store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setImageFeedback('Change style');
      });
      expect(mockImageStoreFunctions.setImageFeedback).toHaveBeenCalledWith('Change style');
    });
  });

  // ===================== Router =====================

  describe('Router', () => {
    it('exposes router instance', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.router).toBeDefined();
      expect(typeof result.current.router.push).toBe('function');
    });
  });

  // ===================== Toast =====================

  describe('Toast', () => {
    it('showToast sets toast and clears after timeout', async () => {
      jest.useFakeTimers();
      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.showToast('success', 'Operation complete');
      });

      expect(result.current.toast).toEqual({
        type: 'success',
        message: 'Operation complete',
      });

      act(() => {
        jest.advanceTimersByTime(3000);
      });

      expect(result.current.toast).toBeNull();

      jest.useRealTimers();
    });
  });

  // ===================== Auto-gen State =====================

  describe('Auto-gen state', () => {
    it('provides setAutoGenPhase', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setAutoGenPhase('generating');
      });
      expect(result.current.autoGenPhase).toBe('generating');
    });

    it('provides setShowDetails', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setShowDetails(true);
      });
      expect(result.current.showDetails).toBe(true);
    });

    it('starts with autoGenPhase as done when all auto settings present', () => {
      mockGameStoreState.characterSettings = {
        family: { family_name: 'Test' },
        relationships: { relationships_description: 'Test' },
        traits: { personality: 'brave' },
        wealth: { wealth_level: 'middle' },
      };
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.autoGenPhase).toBe('done');
    });
  });

  // ===================== prevCreationStep =====================

  describe('prevCreationStep (wrapper)', () => {
    it('calls prevCreationStep on the store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.prevCreationStep();
      });
      expect(mockGameStoreFunctions.prevCreationStep).toHaveBeenCalled();
    });

    it('clears generatedContent when going back', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.prevCreationStep();
      });
      expect(result.current.generatedContent).toBeNull();
    });

    it('clears feedback when going back', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setFeedback('Some feedback');
      });
      act(() => {
        result.current.prevCreationStep();
      });
      expect(result.current.feedback).toBe('');
    });
  });

  // ===================== handleSavePreset =====================

  describe('handleSavePreset', () => {
    it('calls api.presets.create with correct params', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.lifeVision = 'My Vision';
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockPresetCreate.mockResolvedValue({ preset_id: 1 });

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setPresetName('My Cool Preset');
      });

      await act(async () => {
        await result.current.handleSavePreset();
      });

      expect(mockPresetCreate).toHaveBeenCalledWith({
        preset_name: 'My Cool Preset',
        player_name: 'TestPlayer',
        life_vision: 'My Vision',
        character_settings: { era: { era_name: '古代' } },
      });
    });

    it('shows success toast and closes sheet after save', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockPresetCreate.mockResolvedValue({ preset_id: 1 });

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setPresetName('My Preset');
        result.current.setShowPresetSheet(true);
      });

      await act(async () => {
        await result.current.handleSavePreset();
      });

      expect(result.current.showPresetSheet).toBe(false);
      expect(result.current.presetName).toBe('');
      expect(result.current.toast).toEqual({
        type: 'success',
        message: '预设保存成功',
      });
    });
  });

  // ===================== handleStartGame =====================

  describe('handleStartGame', () => {
    it('shows error toast when playerName is empty', async () => {
      const { result } = renderHook(() => useCharacterCreation());
      jest.spyOn(console, 'warn').mockImplementation(() => {});

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(result.current.toast).toEqual({
        type: 'error',
        message: '请先输入角色姓名',
      });
      expect(mockGameCreate).not.toHaveBeenCalled();
    });

    it('does not start game when isGenerating is true', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      // Prevent auto-generation from firing by setting current step key
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      jest.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      // Call handleGenerate first to set isGenerating = true
      let genPromise: Promise<void>;
      mockGenerateSetting.mockImplementation(() => new Promise(() => {})); // never resolves
      await act(async () => {
        genPromise = result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(true);

      // Now try to start game while generating
      await act(async () => {
        await result.current.handleStartGame();
      });

      // Should have warned and not called game create
      expect(mockGameCreate).not.toHaveBeenCalled();
    });

    it('navigates to /story/opening when gameId already exists', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.gameId = 42;
      // Prevent auto-generation from interfering
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockPresetCreate.mockResolvedValue({ preset_id: 1 });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(mockPush).toHaveBeenCalledWith('/story/opening');
    });

    it('creates a new game and navigates when no gameId', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockPresetCreate.mockResolvedValue({ preset_id: 1 });
      mockGameCreate.mockResolvedValue({ game_id: 99 });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(mockGameCreate).toHaveBeenCalledWith({
        character_settings: { era: { era_name: '古代' } },
        player_name: 'TestPlayer',
        life_vision: '',
        language: 'zh',
      });

      expect(mockGameStoreFunctions.setGameSession).toHaveBeenCalledWith(99, '99');

      // Navigation fires asynchronously (setTimeout 100ms)
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/story/opening');
      });
    });

    it('saves auto-preset before creating game', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockPresetCreate.mockResolvedValue({ preset_id: 1 });
      mockGameCreate.mockResolvedValue({ game_id: 100 });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      // Verify preset was saved (auto-preset)
      expect(mockPresetCreate).toHaveBeenCalled();
      const presetCall = mockPresetCreate.mock.calls[0][0];
      expect(presetCall.preset_name).toContain('TestPlayer');
      expect(presetCall.player_name).toBe('TestPlayer');
    });

    it('handles preset save failure gracefully (non-blocking)', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      // Prevent auto-generation from interfering
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockPresetCreate.mockRejectedValue(new Error('Preset save error'));
      mockGameCreate.mockResolvedValue({ game_id: 200 });

      jest.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      // Should still create the game
      expect(mockGameCreate).toHaveBeenCalled();

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/story/opening');
      });
    });

    it('shows error toast when game creation fails', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      // Prevent auto-generation from interfering
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockPresetCreate.mockRejectedValue(new Error('Preset save error'));
      mockGameCreate.mockRejectedValue(new Error('Game creation error'));

      jest.spyOn(console, 'error').mockImplementation(() => {});
      jest.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      await waitFor(() => {
        expect(result.current.toast).toEqual({
          type: 'error',
          message: '创建游戏失败，请重试',
        });
      });
    });
  });

  // ===================== handleAcceptAndNext =====================

  describe('handleAcceptAndNext', () => {
    it('updates characterSetting with generatedContent for non-portrait steps', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.creationStep = 0;
      const content = { era_name: '古代', era_description: 'Ancient era' };
      mockGenerateSetting.mockResolvedValue(content);

      const { result } = renderHook(() => useCharacterCreation());

      // First generate content
      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(result.current.generatedContent).toEqual(content);

      // Then accept and next
      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      expect(mockGameStoreFunctions.updateCharacterSetting).toHaveBeenCalledWith('era', content);
      expect(result.current.generatedContent).toBeNull();
    });

    it('creates game on world step when no gameId exists', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.creationStep = 3; // world step
      mockGameStoreState.characterSettings = {
        era: { era_name: '古代' },
        age: { age: 25 },
        gender: { gender: '男' },
      };
      mockGameCreate.mockResolvedValue({ game_id: 50 });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      expect(mockGameCreate).toHaveBeenCalledWith({
        character_settings: {
          era: { era_name: '古代' },
          age: { age: 25 },
          gender: { gender: '男' },
        },
        player_name: 'TestPlayer',
        life_vision: '',
        language: 'zh',
      });

      expect(mockGameStoreFunctions.setGameSession).toHaveBeenCalledWith(50, '50');
      expect(mockGameStoreFunctions.nextCreationStep).toHaveBeenCalled();
    });

    it('advances to next step on normal non-portrait step', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.creationStep = 0;
      mockGameStoreState.gameId = 10; // Game already exists
      mockGenerateSetting.mockResolvedValue({ era_name: '古代' });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });
      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      // On non-world, existing game: just update setting and advance
      expect(mockGameStoreFunctions.updateCharacterSetting).toHaveBeenCalled();
      expect(mockGameStoreFunctions.nextCreationStep).toHaveBeenCalled();
    });

    it('shows error toast when game creation fails on world step', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.creationStep = 3; // world step
      mockGameCreate.mockRejectedValue(new Error('Creation failed'));

      jest.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      await waitFor(() => {
        expect(result.current.toast).toEqual({
          type: 'error',
          message: '创建游戏失败，请重试',
        });
      });
    });
  });

  // ===================== regenerateSetting =====================

  describe('regenerateSetting', () => {
    it('throws error when no gameId', async () => {
      jest.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await expect(
        act(async () => {
          await result.current.regenerateSetting('era', 'Change it');
        })
      ).rejects.toThrow('游戏未创建');
    });

    it('calls api.character.generateSetting and updates store', async () => {
      mockGameStoreState.gameId = 10;
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      const newContent = { era_name: '现代', era_description: 'Modern era' };
      mockGenerateSetting.mockResolvedValue(newContent);

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.regenerateSetting('era', 'Change era to modern');
      });

      expect(mockGenerateSetting).toHaveBeenCalledWith({
        setting_type: 'era',
        player_name: 'TestPlayer',
        life_vision: '',
        previous_settings: { era: { era_name: '古代' } },
        language: 'zh',
        feedback: 'Change era to modern',
      });

      expect(mockGameStoreFunctions.updateCharacterSetting).toHaveBeenCalledWith('era', newContent);
    });
  });

  // ===================== Image Store Actions =====================

  describe('Image store actions', () => {
    it('provides regeneratePlayerImage', async () => {
      mockImageStoreFunctions.regeneratePlayerImage.mockResolvedValue(undefined);
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.regeneratePlayerImage('Fix face');
      });

      expect(mockImageStoreFunctions.regeneratePlayerImage).toHaveBeenCalledWith('Fix face');
    });

    it('provides regenerateFreshPlayerImage', async () => {
      mockImageStoreFunctions.regenerateFreshPlayerImage.mockResolvedValue(undefined);
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.regenerateFreshPlayerImage();
      });

      expect(mockImageStoreFunctions.regenerateFreshPlayerImage).toHaveBeenCalled();
    });
  });

  // ===================== Language =====================

  describe('Language', () => {
    it('returns language from UI store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.language).toBe('zh');
    });

    it('reflects language change in UI store', () => {
      mockUIStoreState.language = 'en';
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.language).toBe('en');
    });
  });

  // ===================== Edge Cases =====================

  describe('Edge cases', () => {
    it('handleGenerate does nothing when playerName is whitespace only', async () => {
      mockGameStoreState.playerName = '   ';
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(mockGenerateSetting).not.toHaveBeenCalled();
      // hasBasicInfo checks trimmed length > 0
      expect(result.current.hasBasicInfo).toBe(false);
    });

    it('handleAcceptAndNext without generatedContent skips update', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.gameId = 10;
      mockGameStoreState.creationStep = 0;

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      // Should advance step without updating character setting
      expect(mockGameStoreFunctions.nextCreationStep).toHaveBeenCalled();
    });

    it('handles rapid successive handleGenerate calls', async () => {
      mockGameStoreState.playerName = 'TestPlayer';
      mockGameStoreState.creationStep = 0;
      // Prevent auto-generation by pre-populating the current step
      mockGameStoreState.characterSettings = { era: { era_name: '古代' } };
      mockGenerateSetting.mockResolvedValue({ era_name: '古代' });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
        await result.current.handleGenerate('Second call');
      });

      // Both calls should have been made (auto-generation is suppressed by pre-populated setting)
      expect(mockGenerateSetting).toHaveBeenCalledTimes(2);
    });

    it('playerImage uses first image as fallback when index is 0 and images exist', () => {
      mockImageStoreState.playerImages = [{ image_id: 10, image_url: '/img/10.png' }];
      mockImageStoreState.selectedImageIndex = 0;
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toEqual({ image_id: 10, image_url: '/img/10.png' });
    });
  });
});
