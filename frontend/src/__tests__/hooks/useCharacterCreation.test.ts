/**
 * Tests for useCharacterCreation hook
 * Tests initial state, form field management, generation flow,
 * loading states, error handling, and edge cases.
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useCharacterCreation } from '@/hooks/useCharacterCreation';
import { useCharacterStore, useGameStore } from '@/stores/useGameStore';
import { useImageStore } from '@/stores/useImageStore';
import { useUIStore } from '@/stores/useUIStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import { INPUT_LIMITS } from '@/types/input-limits.generated';

const testOrigin = {
  revision: 1,
  start_date: '2026-08-13',
  starting_age: 28,
  era_description: '2020年代中期的现代都市',
  life_stage_description: '职业稳定探索期',
  world_context: 'AI工具快速变化',
};

// -- Mock next/navigation --
const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

/** Extract parsed body from a fetch call to the given URL */
function fetchBody(url: string): Record<string, unknown> | null {
  const calls = (global.fetch as jest.Mock).mock.calls.filter((c: unknown[]) => c[0] === url);
  const call = calls[calls.length - 1];
  if (!call) return null;
  return JSON.parse((call[1] as Record<string, string>).body);
}

/** Check if fetch was called for a given URL */
function fetchCalled(url: string): boolean {
  return (global.fetch as jest.Mock).mock.calls.some((c: unknown[]) => c[0] === url);
}

// -- Store method spying --
const GAME_METHODS = ['nextCreationStep', 'prevCreationStep', 'updateCharacterSetting', 'resetCreation', 'setGameSession'] as const;
const IMAGE_METHODS = ['generatePlayerImage', 'regeneratePlayerImage', 'regenerateFreshPlayerImage'] as const;

type GameStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof GAME_METHODS)[number]>>;
type ImageStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useImageStore, (typeof IMAGE_METHODS)[number]>>;

function setupDefaultState() {
  useCharacterStore.setState({
    creationStep: 0,
    characterSettings: {},
    playerName: '',
    lifeVision: '',
    openingStory: '',
    isPresetLoaded: false,
  } as never);
  useGameStore.setState({
    creationStep: 0,
    characterSettings: {},
    playerName: '',
    lifeVision: '',
    isPresetLoaded: false,
    gameId: null,
    sessionId: null,
  } as never);
  useImageStore.setState({
    playerImages: [],
    selectedImageIndex: 0,
    isGeneratingImage: false,
    imageFeedback: '',
    playerImage: null,
  } as never);
  useUIStore.setState({ language: 'zh' } as never);
}

describe('useCharacterCreation', () => {
  let gameSpy: GameStoreSpy;
  let imageSpy: ImageStoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    setupDefaultState();
    gameSpy = spyOnStoreMethods(useGameStore, GAME_METHODS);
    imageSpy = spyOnStoreMethods(useImageStore, IMAGE_METHODS);
    mockPush.mockClear();
    mockReplace.mockClear();
  });

  afterEach(() => {
    gameSpy.restore();
    imageSpy.restore();
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
      expect(result.current.currentStepKey).toBe('story_origin');
    });

    it('computes currentStepKey when creationStep is 2', () => {
      useGameStore.setState({ creationStep: 2 } as never);
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.currentStepKey).toBe('world');
    });

    it('computes isFirstStep as true when creationStep is 0', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isFirstStep).toBe(true);
      expect(result.current.isLastStep).toBe(false);
    });

    it('computes isLastStep as true when on last step', () => {
      useGameStore.setState({ creationStep: 3 } as never);
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.isLastStep).toBe(true);
      expect(result.current.isFirstStep).toBe(false);
    });

    it('computes isPortraitStep as true on portrait step', () => {
      useGameStore.setState({ creationStep: 3 } as never);
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
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
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
    it('setPlayerName updates playerName in store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setPlayerName('NewName');
      });
      expect(useGameStore.getState().playerName).toBe('NewName');
    });

    it('setLifeVision updates lifeVision in store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setLifeVision('A great vision');
      });
      expect(useGameStore.getState().lifeVision).toBe('A great vision');
    });

    it('provides updateCharacterSetting from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.updateCharacterSetting('era', { era_name: '古代' });
      });
      expect(gameSpy.spies.updateCharacterSetting).toHaveBeenCalledWith(
        'era',
        { era_name: '古代' }
      );
    });

    it('setCreationStep updates creationStep in store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setCreationStep(1);
      });
      expect(useGameStore.getState().creationStep).toBe(1);
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
      expect(gameSpy.spies.resetCreation).toHaveBeenCalled();
    });

    it('provides nextCreationStep from store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.nextCreationStep();
      });
      expect(gameSpy.spies.nextCreationStep).toHaveBeenCalled();
    });
  });

  // ===================== Character Generation Flow =====================

  describe('handleGenerate', () => {
    it('does nothing when hasBasicInfo is false (empty playerName)', async () => {
      const { result } = renderHook(() => useCharacterCreation());
      await act(async () => {
        await result.current.handleGenerate();
      });
      expect(fetchCalled('/api/character/story-origin')).toBe(false);
    });

    it('calls api.character.generateStoryOrigin with correct params', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        lifeVision: 'Become a hero',
        characterSettings: { era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(testOrigin));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(fetchBody('/api/character/story-origin')).toMatchObject({
        player_name: 'TestPlayer',
        life_vision: 'Become a hero',
        previous_settings: { era: { era_name: '古代' } },
        feedback: null,
        language: 'zh',
      });
    });

    it('does not submit an overlimit persisted UI value', async () => {
      useGameStore.setState({
        playerName: '😀'.repeat(INPUT_LIMITS.name + 1),
      } as never);
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(fetchCalled('/api/character/setting')).toBe(false);
    });

    it('does not retry deterministic 422 responses', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockImplementation((_url: string, options?: RequestInit) => {
        const body = typeof options?.body === 'string' ? options.body : '';
        return Promise.resolve(
          body.includes('deterministic-422')
            ? errorResponse(422, 'too long')
            : jsonResponse({}),
        );
      });
      jest.spyOn(console, 'warn').mockImplementation(() => {});
      jest.spyOn(console, 'error').mockImplementation(() => {});
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate('deterministic-422');
      });

      const calls = (global.fetch as jest.Mock).mock.calls.filter(
        (call: unknown[]) =>
          call[0] === '/api/character/story-origin' &&
          typeof (call[1] as RequestInit | undefined)?.body === 'string' &&
          ((call[1] as RequestInit).body as string).includes('deterministic-422'),
      );
      expect(calls).toHaveLength(1);
    });

    it('sets isGenerating to true during generation', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      let resolvePromise: (value: Response) => void;
      const promise = new Promise<Response>((resolve) => { resolvePromise = resolve; });
      (global.fetch as jest.Mock).mockReturnValue(promise);

      const { result } = renderHook(() => useCharacterCreation());

      let generationPromise: Promise<void>;
      await act(async () => {
        generationPromise = result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(true);
      expect(result.current.generatedContent).toBeNull();

      await act(async () => {
        resolvePromise!(jsonResponse({ era_name: '古代', era_description: 'Ancient times' }));
        await generationPromise!;
      });

      expect(result.current.isGenerating).toBe(false);
    });

    it('sets generatedContent after successful generation', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      const expectedContent = { era_name: '古代', era_description: 'Ancient times' };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(expectedContent));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(result.current.generatedContent).toEqual(expectedContent);
    });

    it('discards era generated from stale life vision when user edits vision before response returns', async () => {
      useGameStore.setState({
        playerName: '许知夏',
        lifeVision: '',
        creationStep: 0,
        characterSettings: { era: { era_name: 'placeholder' } },
      } as never);

      let resolveGeneration!: (value: Response) => void;
      (global.fetch as jest.Mock).mockReturnValue(
        new Promise<Response>((resolve) => {
          resolveGeneration = resolve;
        })
      );

      const { result } = renderHook(() => useCharacterCreation());

      let generationPromise!: Promise<void>;
      await act(async () => {
        generationPromise = result.current.handleGenerate();
      });

      act(() => {
        result.current.setLifeVision('现代上海，独立游戏开发者，不要古代、不要穿越。');
      });

      await act(async () => {
        resolveGeneration(
          jsonResponse({
            year: 1100,
            era_description: '1100年北宋中后期，科举制度完善。',
            world_context: '北宋王朝文人地位崇高。',
          })
        );
        await generationPromise;
      });

      expect(result.current.generatedContent).toBeNull();
    });

    it('discards feedback regeneration when life vision changes before response returns', async () => {
      useGameStore.setState({
        playerName: '许知夏',
        lifeVision: '现代上海，独立游戏开发者。',
        creationStep: 0,
        characterSettings: {},
      } as never);

      let resolveGeneration!: (value: Response) => void;
      (global.fetch as jest.Mock).mockReturnValue(
        new Promise<Response>((resolve) => {
          resolveGeneration = resolve;
        })
      );

      const { result } = renderHook(() => useCharacterCreation());

      let generationPromise!: Promise<void>;
      await act(async () => {
        generationPromise = result.current.handleGenerate('请保持现代都市背景。');
      });

      act(() => {
        result.current.setLifeVision('现代上海，独立游戏音乐制作人，不要古代。');
      });

      await act(async () => {
        resolveGeneration(
          jsonResponse({
            year: 1100,
            era_description: '1100年北宋中后期，科举制度完善。',
          })
        );
        await generationPromise;
      });

      expect(result.current.generatedContent).toBeNull();
    });

    it('handles generation with feedback string', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ era_name: '现代' }));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate('More specific');
      });

      expect(fetchBody('/api/character/story-origin')).toMatchObject({ feedback: 'More specific' });
    });
  });

  // ===================== Loading States =====================

  describe('Loading states', () => {
    it('sets isGenerating to false after generation completes', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ era_name: '古代' }));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(false);
    });

    it('sets isGenerating to false after generation fails', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400, 'Network error'));
      jest.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(false);
    });

    it('sets isSavingPreset to true during preset save', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      let resolvePromise: (value: Response) => void;
      const promise = new Promise<Response>((resolve) => { resolvePromise = resolve; });
      (global.fetch as jest.Mock).mockReturnValue(promise);

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
        resolvePromise!(jsonResponse({ preset_id: 1 }));
        await savePromise!;
      });

      expect(result.current.isSavingPreset).toBe(false);
    });
  });

  // ===================== Error Handling =====================

  describe('Error handling', () => {
    it('shows error toast when generation fails after retries', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400, 'API failure'));
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
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400, 'Save error'));
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

    it('exposes inline preset save progress and error states for the modal', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      let resolveSave: (response: Response) => void = () => undefined;
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/presets') {
          return new Promise<Response>((resolve) => {
            resolveSave = resolve;
          });
        }
        return Promise.resolve(jsonResponse({}));
      });
      jest.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setPresetName('My Preset');
      });

      let savePromise!: Promise<void>;
      act(() => {
        savePromise = result.current.handleSavePreset();
      });

      await waitFor(() => {
        expect(result.current.isSavingPreset).toBe(true);
      });
      expect((result.current as unknown as { presetSaveStatus?: string }).presetSaveStatus).toBe('saving');
      expect((result.current as unknown as { presetSaveMessage?: string }).presetSaveMessage).toBe('正在保存角色预设...');

      await act(async () => {
        resolveSave(errorResponse(400, 'Save error'));
        await savePromise;
      });

      expect(result.current.isSavingPreset).toBe(false);
      expect((result.current as unknown as { presetSaveStatus?: string }).presetSaveStatus).toBe('error');
      expect((result.current as unknown as { presetSaveMessage?: string }).presetSaveMessage).toBe('保存失败，预设未保存，请重试。');
    });

    it('does not save preset when presetName is empty', async () => {
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleSavePreset();
      });

      expect(fetchCalled('/api/presets')).toBe(false);
    });
  });

  // ===================== handleRegenerate =====================

  describe('handleRegenerate', () => {
    it('calls handleGenerate with current feedback and clears feedback', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ era_name: '古代' }));

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setFeedback('Please change era');
      });

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(result.current.feedback).toBe('');
      expect(fetchBody('/api/character/story-origin')).toMatchObject({ feedback: 'Please change era' });
    });

    it('keeps overlimit feedback visible and does not submit it', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      const { result } = renderHook(() => useCharacterCreation());
      const feedback = '😀'.repeat(INPUT_LIMITS.feedback + 1);
      act(() => result.current.setFeedback(feedback));

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(result.current.feedback).toBe(feedback);
      const calls = (global.fetch as jest.Mock).mock.calls.filter(
        (call: unknown[]) =>
          call[0] === '/api/character/setting' &&
          typeof (call[1] as RequestInit | undefined)?.body === 'string' &&
          ((call[1] as RequestInit).body as string).includes(feedback),
      );
      expect(calls).toHaveLength(0);
    });
  });

  // ===================== Constants =====================

  describe('Constants', () => {
    it('exposes STEP_LABELS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.STEP_LABELS).toBeDefined();
      expect(result.current.STEP_LABELS.story_origin).toBe('故事起点');
    });

    it('exposes STEP_DESCRIPTIONS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.STEP_DESCRIPTIONS).toBeDefined();
      expect(result.current.STEP_DESCRIPTIONS.story_origin).toContain('完整起点');
    });

    it('exposes CREATION_STEPS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.CREATION_STEPS).toEqual(['story_origin', 'gender', 'world', 'portrait']);
    });

    it('exposes AUTO_ADVANCE_STEPS', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.AUTO_ADVANCE_STEPS).toEqual(['family', 'relationships', 'traits']);
    });
  });

  // ===================== Player Images =====================

  describe('Player images', () => {
    it('returns playerImage as null when no images', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toBeNull();
    });

    it('returns playerImage from selected image', () => {
      useImageStore.setState({
        playerImages: [
          { image_id: 1, image_url: '/img/1.png' },
          { image_id: 2, image_url: '/img/2.png' },
        ],
        selectedImageIndex: 1,
      } as never);
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toEqual({ image_id: 2, image_url: '/img/2.png' });
    });

    it('falls back to first image when selectedIndex is out of bounds', () => {
      useImageStore.setState({
        playerImages: [
          { image_id: 1, image_url: '/img/1.png' },
        ],
        selectedImageIndex: 5,
      } as never);
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toEqual({ image_id: 1, image_url: '/img/1.png' });
    });

    it('setSelectedImageIndex updates selectedImageIndex in image store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setSelectedImageIndex(2);
      });
      expect(useImageStore.getState().selectedImageIndex).toBe(2);
    });

    it('setImageFeedback updates imageFeedback in image store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.setImageFeedback('Change style');
      });
      expect(useImageStore.getState().imageFeedback).toBe('Change style');
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
      useGameStore.setState({
        characterSettings: {
          family: { family_name: 'Test' },
          relationships: { relationships_description: 'Test' },
          traits: { personality: 'brave' },
          wealth: { wealth_level: 'middle' },
        },
      } as never);
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.autoGenPhase).toBe('done');
    });

    it('keeps the portrait phase visible when background generation finishes', async () => {
      useGameStore.setState({
        creationStep: 2,
        gameId: null,
        playerName: '阿衡',
        lifeVision: '建立长久事业',
        characterSettings: {
          story_origin: testOrigin,
          family: { family_background: '普通家庭' },
          relationships: { relationships_description: '旧友仍在' },
        },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(
        jsonResponse({ personality: ['谨慎'] }),
      );

      const { result } = renderHook(() => useCharacterCreation());
      await act(async () => {
        await result.current.runAutoGeneration(false);
      });

      expect(result.current.autoGenPhase).toBe('idle');
      expect(gameSpy.spies.updateCharacterSetting).toHaveBeenCalledWith(
        'traits',
        { personality: ['谨慎'] },
      );
    });

    it('exposes each actual automatic background step while the generation loop advances', async () => {
      useGameStore.setState({
        creationStep: 3,
        playerName: '陆明',
        lifeVision: '认真生活',
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: '城市' },
        },
      } as never);

      let resolveFamily: ((response: Response) => void) | undefined;
      let resolveRelationship: ((response: Response) => void) | undefined;
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/character/setting') {
          return new Promise<Response>((resolve) => {
            resolveFamily = resolve;
          });
        }
        if (url === '/api/character/relationship') {
          return new Promise<Response>((resolve) => {
            resolveRelationship = resolve;
          });
        }
        return Promise.resolve(jsonResponse({}));
      });

      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        void result.current.runAutoGeneration();
      });

      await waitFor(() => expect(result.current.autoGenLabel).toBe('家庭背景'));
      act(() => {
        resolveFamily?.(jsonResponse({ family_background: '普通家庭' }));
      });
      await waitFor(() => expect(result.current.autoGenLabel).toBe('生成关键人物'));
      expect(resolveRelationship).toBeDefined();

    });
  });

  // ===================== prevCreationStep =====================

  describe('prevCreationStep (wrapper)', () => {
    it('calls prevCreationStep on the store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      act(() => {
        result.current.prevCreationStep();
      });
      expect(gameSpy.spies.prevCreationStep).toHaveBeenCalled();
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
      useGameStore.setState({
        playerName: 'TestPlayer',
        lifeVision: 'My Vision',
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ preset_id: 1 }));

      const { result } = renderHook(() => useCharacterCreation());

      act(() => {
        result.current.setPresetName('My Cool Preset');
      });

      await act(async () => {
        await result.current.handleSavePreset();
      });

      expect(fetchBody('/api/presets')).toMatchObject({
        preset_name: 'My Cool Preset',
        player_name: 'TestPlayer',
        life_vision: 'My Vision',
        character_settings: { era: { era_name: '古代' } },
      });
    });

    it('shows success toast and closes sheet after save', async () => {
      useGameStore.setState({ playerName: 'TestPlayer' } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ preset_id: 1 }));

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
      expect(fetchCalled('/api/games')).toBe(false);
    });

    it('does not start game when isGenerating is true', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        characterSettings: { era: { era_name: '古代' } },
      } as never);
      jest.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      // Call handleGenerate first to set isGenerating = true
      let resolveGeneration!: (value: Response) => void;
      (global.fetch as jest.Mock).mockImplementation(
        () => new Promise<Response>((resolve) => {
          resolveGeneration = resolve;
        })
      );
      let generationPromise!: Promise<void>;
      await act(async () => {
        generationPromise = result.current.handleGenerate();
      });

      expect(result.current.isGenerating).toBe(true);

      // Now try to start game while generating
      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(fetchCalled('/api/games')).toBe(false);

      await act(async () => {
        resolveGeneration(jsonResponse({ era_name: '古代', era_description: 'Ancient times' }));
        await generationPromise;
      });
    });

    it('does not start a game with an overlimit name', async () => {
      useGameStore.setState({
        playerName: '😀'.repeat(INPUT_LIMITS.name + 1),
      } as never);
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(fetchCalled('/api/games')).toBe(false);
      expect(result.current.toast?.type).toBe('error');
    });

    it('navigates to /play when gameId already exists', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        gameId: 42,
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ preset_id: 1 }));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(mockPush).toHaveBeenCalledWith('/play');
    });

    it('patches existing game identity when gameId already exists', async () => {
      useGameStore.setState({
        playerName: '沈若澜',
        lifeVision: '2026年的深圳，女性AI教育产品创始人',
        gameId: 109,
        characterSettings: { story_origin: testOrigin, era: { era_description: '2026年的深圳' } },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(fetchBody('/api/games/109/character-settings')).toMatchObject({
        character_settings: { story_origin: testOrigin, era: { era_description: '2026年的深圳' } },
        player_name: '沈若澜',
        life_vision: '2026年的深圳，女性AI教育产品创始人',
      });
      expect(mockPush).toHaveBeenCalledWith('/play');
    });

    it('creates a new game and navigates when no gameId', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ preset_id: 1 }));
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ game_id: 99 }));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(fetchBody('/api/games')).toMatchObject({
        character_settings: { story_origin: testOrigin, era: { era_name: '古代' } },
        player_name: 'TestPlayer',
        life_vision: '',
        language: 'zh',
      });

      expect(gameSpy.spies.setGameSession).toHaveBeenCalledWith(99, '99');

      // Navigation fires asynchronously (setTimeout 100ms)
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/play');
      });
    });

    it('saves auto-preset before creating game', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ preset_id: 1 }));
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ game_id: 100 }));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(fetchCalled('/api/presets')).toBe(true);
      const presetCall = fetchBody('/api/presets');
      expect(presetCall.preset_name).toContain('TestPlayer');
      expect(presetCall.player_name).toBe('TestPlayer');
    });

    it('handles preset save failure gracefully (non-blocking)', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/presets') return Promise.resolve(errorResponse(400, 'Preset save error'));
        return Promise.resolve(jsonResponse({ game_id: 200 }));
      });

      jest.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleStartGame();
      });

      expect(fetchCalled('/api/games')).toBe(true);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/play');
      });
    });

    it('shows error toast when game creation fails', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/presets') return Promise.resolve(errorResponse(400, 'Preset save error'));
        if (url === '/api/games') return Promise.resolve(errorResponse(400, 'Game creation error'));
        return Promise.resolve(jsonResponse({}));
      });

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
    it('does not advance or write with an overlimit name', async () => {
      useGameStore.setState({
        playerName: '😀'.repeat(INPUT_LIMITS.name + 1),
        creationStep: 3,
      } as never);
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      expect(fetchCalled('/api/games')).toBe(false);
      expect(gameSpy.spies.nextCreationStep).not.toHaveBeenCalled();
    });

    it('updates characterSetting with generatedContent for non-portrait steps', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        creationStep: 0,
      } as never);
      const content = testOrigin;
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(content));

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

      expect(gameSpy.spies.nextCreationStep).toHaveBeenCalled();
      expect(result.current.generatedContent).toBeNull();
    });

    it('creates game on world step when no gameId exists', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        creationStep: 2,
        characterSettings: {
          era: { era_name: '古代' },
          age: { age: 25 },
          gender: { gender: '男' },
        },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ game_id: 50 }));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      expect(fetchBody('/api/games')).toMatchObject({
        character_settings: {
          era: { era_name: '古代' },
          age: { age: 25 },
          gender: { gender: '男' },
        },
        player_name: 'TestPlayer',
        life_vision: '',
        language: 'zh',
      });

      expect(gameSpy.spies.setGameSession).toHaveBeenCalledWith(50, '50');
      expect(gameSpy.spies.nextCreationStep).toHaveBeenCalled();
    });

    it('includes the accepted world setting in the initial game creation request', async () => {
      useGameStore.setState({
        playerName: '顾晚晴',
        lifeVision: '现代都市悬疑，女性调查记者，追查科技公司数据黑幕，不要跳到古代模板。',
        creationStep: 2,
        characterSettings: {
          era: { year: 960, era_description: '960年北宋初年' },
          age: { age: 20 },
          gender: { gender: '女' },
        },
      } as never);
      const generatedWorld = {
        world_description: '2020年代现代化大都市，科技公司掌控海量用户数据，调查记者追查数据黑幕。',
        technology_level: '5G、人工智能、大数据、云计算',
        social_system: '现代法治社会',
      };
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url.endsWith('/character/setting')) {
          return Promise.resolve(jsonResponse(generatedWorld));
        }
        if (url.endsWith('/games')) {
          return Promise.resolve(jsonResponse({ game_id: 51 }));
        }
        return Promise.resolve(jsonResponse({}));
      });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });
      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      expect(fetchBody('/api/games')).toMatchObject({
        character_settings: {
          era: { year: 960, era_description: '960年北宋初年' },
          age: { age: 20 },
          gender: { gender: '女' },
          world: generatedWorld,
        },
        player_name: '顾晚晴',
        life_vision: '现代都市悬疑，女性调查记者，追查科技公司数据黑幕，不要跳到古代模板。',
        language: 'zh',
      });
    });

    it('advances to next step on normal non-portrait step', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        creationStep: 0,
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(testOrigin));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });
      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      expect(gameSpy.spies.nextCreationStep).toHaveBeenCalled();
      expect(useGameStore.getState().characterSettings.story_origin).toEqual(testOrigin);
    });

    it('shows error toast when game creation fails on world step', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        creationStep: 2,
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400, 'Creation failed'));

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
        result.current.regenerateSetting('era', 'Change it')
      ).rejects.toThrow('游戏未创建');
    });

    it('calls api.character.generateSetting and updates store', async () => {
      useGameStore.setState({
        gameId: 10,
        playerName: 'TestPlayer',
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      const newContent = { era_name: '现代', era_description: 'Modern era' };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(newContent));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.regenerateSetting('era', 'Change era to modern');
      });

      expect(fetchBody('/api/character/setting')).toMatchObject({
        setting_type: 'era',
        player_name: 'TestPlayer',
        life_vision: '',
        previous_settings: { era: { era_name: '古代' } },
        language: 'zh',
        feedback: 'Change era to modern',
      });

      expect(gameSpy.spies.updateCharacterSetting).toHaveBeenCalledWith('era', newContent);
    });

    it('builds and persists a complete relationship candidate before one store update', async () => {
      const oldRelationships = {
        relationships_description: '旧关系摘要',
        key_people: [
          { name: '陈晓峰', role: '前同事', relationship: '仍在原公司任职' },
          { name: '周丽', role: '律师', relationship: '提供法律咨询' },
        ],
      };
      useGameStore.setState({
        gameId: 10,
        playerName: '林见微',
        lifeVision: '现实主义创业故事',
        characterSettings: { relationships: oldRelationships },
      } as never);
      const people = [
        { name: '陈晓峰', role: '前同事', relationship: '仍在原公司任职' },
        { name: '周丽', role: '律师', relationship: '持续提供法律咨询' },
      ];
      let personIndex = 0;
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/character/relationship') {
          return Promise.resolve(jsonResponse(people[personIndex++]));
        }
        if (url === '/api/character/relationships-summary') {
          return Promise.resolve(jsonResponse({ relationships_description: '新的完整关系摘要' }));
        }
        if (url === '/api/games/10/character-settings') {
          return Promise.resolve(jsonResponse({ success: true, message: 'saved' }));
        }
        return Promise.resolve(jsonResponse({}));
      });

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.regenerateSetting(
          'relationships',
          '陈晓峰仍是前同事，不要改变职业',
        );
      });

      const genericSettingBodies = (global.fetch as jest.Mock).mock.calls
        .filter((call: unknown[]) => call[0] === '/api/character/setting')
        .map((call: unknown[]) => JSON.parse((call[1] as RequestInit).body as string));
      expect(genericSettingBodies).not.toContainEqual(
        expect.objectContaining({ setting_type: 'relationships' }),
      );
      const relationshipCalls = (global.fetch as jest.Mock).mock.calls.filter(
        (call: unknown[]) => call[0] === '/api/character/relationship',
      );
      expect(relationshipCalls).toHaveLength(2);
      expect(JSON.parse(relationshipCalls[0][1].body)).toMatchObject({
        feedback: '陈晓峰仍是前同事，不要改变职业',
        existing_people: [],
        person_index: 0,
        total_needed: 2,
      });
      expect(JSON.parse(relationshipCalls[1][1].body)).toMatchObject({
        existing_people: [people[0]],
        person_index: 1,
        total_needed: 2,
      });
      const candidate = {
        relationships_description: '新的完整关系摘要',
        key_people: people,
      };
      expect(fetchBody('/api/games/10/character-settings')).toEqual({
        character_settings: { relationships: candidate },
      });
      expect(gameSpy.spies.updateCharacterSetting).toHaveBeenCalledTimes(1);
      expect(gameSpy.spies.updateCharacterSetting).toHaveBeenCalledWith(
        'relationships',
        candidate,
      );
      const patchCallIndex = (global.fetch as jest.Mock).mock.calls.findIndex(
        (call: unknown[]) => call[0] === '/api/games/10/character-settings',
      );
      expect(gameSpy.spies.updateCharacterSetting.mock.invocationCallOrder[0]).toBeGreaterThan(
        (global.fetch as jest.Mock).mock.invocationCallOrder[patchCallIndex],
      );
    });

    it('rejects an incomplete relationship person without replacing old data', async () => {
      const oldRelationships = {
        relationships_description: '旧关系摘要',
        key_people: [{ name: '陈晓峰', role: '前同事', relationship: '仍在职' }],
      };
      useGameStore.setState({
        gameId: 10,
        playerName: '林见微',
        characterSettings: { relationships: oldRelationships },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(
        jsonResponse({ name: '', role: '', relationship: '' }),
      );

      const { result } = renderHook(() => useCharacterCreation());

      await expect(
        result.current.regenerateSetting('relationships', '保留原职业'),
      ).rejects.toThrow('人际关系生成结果不完整');

      expect(fetchCalled('/api/character/relationships-summary')).toBe(false);
      expect(fetchCalled('/api/games/10/character-settings')).toBe(false);
      expect(gameSpy.spies.updateCharacterSetting).not.toHaveBeenCalled();
      expect(useGameStore.getState().characterSettings.relationships).toEqual(
        oldRelationships,
      );
    });

    it('rejects an empty relationship summary without committing the candidate', async () => {
      const oldRelationships = {
        relationships_description: '旧关系摘要',
        key_people: [{ name: '陈晓峰', role: '前同事', relationship: '仍在职' }],
      };
      useGameStore.setState({
        gameId: 10,
        playerName: '林见微',
        characterSettings: { relationships: oldRelationships },
      } as never);
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/character/relationship') {
          return Promise.resolve(jsonResponse({ name: '陈晓峰', role: '前同事', relationship: '仍在职' }));
        }
        return Promise.resolve(jsonResponse({ relationships_description: '  ' }));
      });

      const { result } = renderHook(() => useCharacterCreation());

      await expect(
        result.current.regenerateSetting('relationships', '保留原职业'),
      ).rejects.toThrow('人际关系生成结果不完整');

      expect(fetchCalled('/api/games/10/character-settings')).toBe(false);
      expect(gameSpy.spies.updateCharacterSetting).not.toHaveBeenCalled();
    });

    it('rejects duplicate relationship names without persisting partial data', async () => {
      const oldRelationships = {
        relationships_description: '旧关系摘要',
        key_people: [
          { name: '陈晓峰', role: '前同事', relationship: '仍在职' },
          { name: '周丽', role: '律师', relationship: '提供咨询' },
        ],
      };
      useGameStore.setState({
        gameId: 10,
        playerName: '林见微',
        characterSettings: { relationships: oldRelationships },
      } as never);
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/character/relationship') {
          return Promise.resolve(jsonResponse({ name: '陈晓峰', role: '前同事', relationship: '仍在职' }));
        }
        return Promise.resolve(jsonResponse({ relationships_description: '重复人物摘要' }));
      });

      const { result } = renderHook(() => useCharacterCreation());

      await expect(
        result.current.regenerateSetting('relationships', '保留原职业'),
      ).rejects.toThrow('人际关系生成结果不完整');

      expect(fetchCalled('/api/games/10/character-settings')).toBe(false);
      expect(gameSpy.spies.updateCharacterSetting).not.toHaveBeenCalled();
    });

    it('keeps old relationship data when server persistence fails', async () => {
      const oldRelationships = {
        relationships_description: '旧关系摘要',
        key_people: [{ name: '陈晓峰', role: '前同事', relationship: '仍在职' }],
      };
      useGameStore.setState({
        gameId: 10,
        playerName: '林见微',
        characterSettings: { relationships: oldRelationships },
      } as never);
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/character/relationship') {
          return Promise.resolve(jsonResponse({ name: '陈晓峰', role: '前同事', relationship: '仍在职' }));
        }
        if (url === '/api/character/relationships-summary') {
          return Promise.resolve(jsonResponse({ relationships_description: '新摘要' }));
        }
        return Promise.resolve(errorResponse(422, 'save failed'));
      });

      const { result } = renderHook(() => useCharacterCreation());

      await expect(
        result.current.regenerateSetting('relationships', '保留原职业'),
      ).rejects.toThrow('人际关系重新生成失败，已保留原设定，请重试');

      expect(gameSpy.spies.updateCharacterSetting).not.toHaveBeenCalled();
      expect(useGameStore.getState().characterSettings.relationships).toEqual(
        oldRelationships,
      );
    });
  });

  // ===================== Image Store Actions =====================

  describe('Image store actions', () => {
    it('provides regeneratePlayerImage', async () => {
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.regeneratePlayerImage('Fix face');
      });

      expect(imageSpy.spies.regeneratePlayerImage).toHaveBeenCalledWith('Fix face');
    });

    it('provides regenerateFreshPlayerImage', async () => {
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.regenerateFreshPlayerImage();
      });

      expect(imageSpy.spies.regenerateFreshPlayerImage).toHaveBeenCalled();
    });
  });

  // ===================== Language =====================

  describe('Language', () => {
    it('returns language from UI store', () => {
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.language).toBe('zh');
    });

    it('reflects language change in UI store', () => {
      useUIStore.setState({ language: 'en' } as never);
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.language).toBe('en');
    });
  });

  // ===================== Edge Cases =====================

  describe('Edge cases', () => {
    it('handleGenerate does nothing when playerName is whitespace only', async () => {
      useGameStore.setState({ playerName: '   ' } as never);
      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
      });

      expect(fetchCalled('/api/character/setting')).toBe(false);
      expect(result.current.hasBasicInfo).toBe(false);
    });

    it('handleAcceptAndNext without generatedContent skips update', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        gameId: 10,
        creationStep: 0,
      } as never);

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleAcceptAndNext();
      });

      expect(gameSpy.spies.nextCreationStep).toHaveBeenCalled();
    });

    it('handles rapid successive handleGenerate calls', async () => {
      useGameStore.setState({
        playerName: 'TestPlayer',
        creationStep: 0,
        characterSettings: { story_origin: testOrigin, era: { era_name: '古代' } },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(testOrigin));

      const { result } = renderHook(() => useCharacterCreation());

      await act(async () => {
        await result.current.handleGenerate();
        await result.current.handleGenerate('Second call');
      });

      expect((global.fetch as jest.Mock).mock.calls.filter((c: unknown[]) => c[0] === '/api/character/story-origin').length).toBe(2);
    });

    it('playerImage uses first image as fallback when index is 0 and images exist', () => {
      useImageStore.setState({
        playerImages: [{ image_id: 10, image_url: '/img/10.png' }],
        selectedImageIndex: 0,
      } as never);
      const { result } = renderHook(() => useCharacterCreation());
      expect(result.current.playerImage).toEqual({ image_id: 10, image_url: '/img/10.png' });
    });
  });
});
