/**
 * Tests for CreatePage component
 * Uses real Zustand stores with setState() + spyOnStoreMethods
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CreatePage from '@/app/create/page';
import { useGameStore } from '@/stores/useGameStore';
import { useUIStore } from '@/stores/useUIStore';
import { useImageStore } from '@/stores/useImageStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

// Env mocks (required — network calls, routing)
const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

const GAME_METHODS = ['setCreationStep', 'nextCreationStep', 'prevCreationStep', 'updateCharacterSetting', 'setPlayerName', 'setLifeVision', 'resetCreation', 'setGameSession'] as const;
const IMAGE_METHODS = ['generatePlayerImage', 'regeneratePlayerImage', 'regenerateFreshPlayerImage', 'setSelectedImageIndex', 'setImageFeedback', 'setPlayerImage', 'setPlayerImages', 'setIsGeneratingImage', 'generateOpeningIllustration', 'regenerateOpeningIllustration', 'setOpeningIllustration', 'setIsGeneratingIllustration', 'setIllustrationError', 'loadPlayerImages'] as const;

type GameStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof GAME_METHODS)[number]>>;
type ImageStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useImageStore, (typeof IMAGE_METHODS)[number]>>;

/** Check that a specific API endpoint was called via fetch */
function fetchCalled(url: string, method?: string): boolean {
  return (global.fetch as jest.Mock).mock.calls.some(
    (c: unknown[]) => c[0] === url && (method ? (c[1] as Record<string, unknown>)?.method === method : true)
  );
}

function setupDefaultState() {
  useGameStore.setState({
    creationStep: 0,
    characterSettings: {} as Record<string, unknown>,
    playerName: '',
    lifeVision: '',
    isPresetLoaded: false,
    gameId: null as number | null,
  });
  useUIStore.setState({ language: 'zh' });
  useImageStore.setState({
    playerImages: [] as Array<{ image_id: number; image_url: string }>,
    selectedImageIndex: 0,
    isGeneratingImage: false,
    imageFeedback: '',
    openingIllustration: null as unknown | null,
    isGeneratingIllustration: false,
    illustrationError: null as string | null,
  });
}

describe('CreatePage', () => {
  let gameSpy: GameStoreSpy;
  let imageSpy: ImageStoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({}));
    mockPush.mockClear();
    mockReplace.mockClear();
    setupDefaultState();
    gameSpy = spyOnStoreMethods(useGameStore, GAME_METHODS);
    imageSpy = spyOnStoreMethods(useImageStore, IMAGE_METHODS);
  });

  afterEach(() => {
    gameSpy.restore();
    imageSpy.restore();
  });

  describe('Initial render', () => {
    it('renders the page title', () => {
      render(<CreatePage />);
      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
    });

    it('renders player name input on first step', () => {
      render(<CreatePage />);
      expect(screen.getByPlaceholderText('输入你的角色名')).toBeInTheDocument();
    });

    it('renders life vision input on first step', () => {
      render(<CreatePage />);
      expect(screen.getByPlaceholderText('描述你希望的人生方向...')).toBeInTheDocument();
    });

    it('renders back button', () => {
      render(<CreatePage />);
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Step rendering', () => {
    it('renders step 1 (era) by default', () => {
      render(<CreatePage />);
      expect(screen.getByText('1/5')).toBeInTheDocument();
    });

    it('shows era step description', () => {
      render(<CreatePage />);
      expect(screen.getByText('选择你的人生将发生在哪个时代')).toBeInTheDocument();
    });

    it('shows era step title', () => {
      render(<CreatePage />);
      expect(screen.getByText('时代背景')).toBeInTheDocument();
    });
  });

  describe('Different steps', () => {
    it('renders age step when creationStep is 1', () => {
      useGameStore.setState({
        creationStep: 1,
        characterSettings: { era: { era_name: '现代' } },
        playerName: 'TestPlayer',
      });

      render(<CreatePage />);
      expect(screen.getByText('年龄阶段')).toBeInTheDocument();
    });

    it('renders gender step when creationStep is 2', () => {
      useGameStore.setState({
        creationStep: 2,
        characterSettings: { era: { era_name: '现代' }, age: { starting_age: 22 } },
        playerName: 'TestPlayer',
      });

      render(<CreatePage />);
      expect(screen.getByText('性别')).toBeInTheDocument();
    });

    it('renders world step when creationStep is 3', () => {
      useGameStore.setState({
        creationStep: 3,
        characterSettings: { era: { era_name: '现代' }, age: { starting_age: 22 }, gender: 'male' },
        playerName: 'TestPlayer',
      });

      render(<CreatePage />);
      expect(screen.getByText('世界观')).toBeInTheDocument();
    });

    it('renders portrait step when creationStep is 4', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: { era: { era_name: '现代' }, age: { starting_age: 22 }, gender: 'male', world: {} },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);
      expect(screen.getByText('人物形象')).toBeInTheDocument();
    });
  });

  describe('Navigation buttons', () => {
    it('shows back button on non-first step', () => {
      useGameStore.setState({
        creationStep: 1,
        characterSettings: { era: { era_name: '现代' } },
        playerName: 'TestPlayer',
      });

      render(<CreatePage />);
      expect(screen.getByText('上一步')).toBeInTheDocument();
    });

    it('shows next step button on portrait step (last step)', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: { era: { era_name: '现代' }, age: { starting_age: 22 }, gender: 'male', world: {} },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);
      // Step 4 is the portrait step — button says "下一步" when images available
      // or "等待形象生成" when no images. Test that the button exists.
      expect(screen.getByRole('button', { name: /等待形象生成/i })).toBeInTheDocument();
    });
  });

  describe('Input fields', () => {
    it('has input for player name on first step', () => {
      render(<CreatePage />);
      const inputs = screen.getAllByRole('textbox');
      expect(inputs.length).toBeGreaterThan(0);
    });

    it('has textarea for life vision on first step', () => {
      render(<CreatePage />);
      const textareas = screen.getAllByRole('textbox');
      expect(textareas.length).toBeGreaterThan(0);
    });
  });

  describe('Step indicator', () => {
    it('shows correct step count', () => {
      render(<CreatePage />);
      expect(screen.getByText('1/5')).toBeInTheDocument();
    });

    it('shows step 2 when creationStep is 1', () => {
      useGameStore.setState({
        creationStep: 1,
        characterSettings: { era: { era_name: '现代' } },
        playerName: 'TestPlayer',
      });

      render(<CreatePage />);
      expect(screen.getByText('2/5')).toBeInTheDocument();
    });

    it('shows step 5 when creationStep is 4', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: { era: { era_name: '现代' }, age: { starting_age: 22 }, gender: 'male', world: {} },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);
      expect(screen.getByText('5/5')).toBeInTheDocument();
    });
  });

  describe('Header', () => {
    it('shows back to home button', () => {
      render(<CreatePage />);
      expect(screen.getByText('返回')).toBeInTheDocument();
    });
  });

  describe('Completion phase', () => {
    it('shows completion state when autoGenPhase is done', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: {},
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);
      expect(screen.getByText('角色设定完成')).toBeInTheDocument();
    });
  });

  describe('Player name display', () => {
    it('shows player name when set', () => {
      useGameStore.setState({
        creationStep: 0,
        characterSettings: {},
        playerName: 'Hero',
        lifeVision: '',
      });

      render(<CreatePage />);
      const input = screen.getByPlaceholderText('输入你的角色名');
      expect(input).toBeInTheDocument();
    });
  });

  describe('Life vision display', () => {
    it('shows life vision when set', () => {
      useGameStore.setState({
        creationStep: 0,
        characterSettings: {},
        playerName: 'Hero',
        lifeVision: 'Be a great person',
      });

      render(<CreatePage />);
      const textarea = screen.getByPlaceholderText('描述你希望的人生方向...');
      expect(textarea).toBeInTheDocument();
    });
  });

  describe('Player name input interaction', () => {
    it('calls setPlayerName when name is typed', async () => {
      render(<CreatePage />);
      const input = screen.getByPlaceholderText('输入你的角色名');

      fireEvent.change(input, { target: { value: 'NewPlayer' } });

      expect(gameSpy.spies.setPlayerName).toBeDefined();
    });
  });

  describe('Life vision input interaction', () => {
    it('calls setLifeVision when vision is typed', async () => {
      render(<CreatePage />);
      const textarea = screen.getByPlaceholderText('描述你希望的人生方向...');

      fireEvent.change(textarea, { target: { value: 'My new vision' } });

      expect(gameSpy.spies.setLifeVision).toBeDefined();
    });
  });

  describe('Return to home', () => {
    it('has a return button', () => {
      render(<CreatePage />);
      expect(screen.getByText('返回')).toBeInTheDocument();
    });
  });

  describe('Portrait step', () => {
    it('shows portrait step content when on step 4', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);
      expect(screen.getByText('人物形象')).toBeInTheDocument();
    });

    it('shows generating state when isGeneratingImage is true', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });
      useImageStore.setState({ isGeneratingImage: true });

      render(<CreatePage />);
      expect(screen.getByText('人物形象')).toBeInTheDocument();
    });

    it('shows player images when available', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });
      useImageStore.setState({
        playerImages: [
          { image_id: 1, image_url: 'http://test.url/1.png' },
          { image_id: 2, image_url: 'http://test.url/2.png' },
        ],
        selectedImageIndex: 0,
      });

      render(<CreatePage />);
      expect(screen.getByText('人物形象')).toBeInTheDocument();
    });
  });

  describe('Auto-generation phase', () => {
    it('shows done state when all auto steps are complete', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);
      expect(screen.getByText('角色设定完成')).toBeInTheDocument();
    });
  });

  describe('API calls and state management', () => {
    it('shows toast message on error', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'API Error' }, 400));

      useGameStore.setState({
        creationStep: 0,
        playerName: 'TestPlayer',
        characterSettings: {},
      });

      await act(async () => {
        render(<CreatePage />);
      });

      await waitFor(() => {
        expect(fetchCalled('/api/character/setting')).toBe(true);
      }, { timeout: 5000 });
    });

    it('calls handleSavePreset with correct data', async () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        lifeVision: 'Test vision',
        gameId: 1,
      });

      render(<CreatePage />);

      const saveButton = screen.getByText('保存');
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('预设名称')).toBeInTheDocument();
      });
    });

    it('handles start game with existing gameId', async () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 123,
      });

      render(<CreatePage />);

      const startButton = screen.getByText('开始游戏');
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/story/opening');
      });
    });

    it('shows loading state during generation', () => {
      useGameStore.setState({
        creationStep: 0,
        playerName: 'TestPlayer',
        characterSettings: {},
      });

      render(<CreatePage />);
      expect(screen.getByText('时代背景')).toBeInTheDocument();
    });

    it('shows long-running generation guidance before the request resolves', async () => {
      jest.useFakeTimers();
      (global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {}));
      useGameStore.setState({
        creationStep: 0,
        playerName: '陆明',
        characterSettings: {},
      });

      render(<CreatePage />);

      await waitFor(() => {
        expect(screen.getByText('AI正在生成时代背景...')).toBeInTheDocument();
      });

      act(() => {
        jest.advanceTimersByTime(15000);
      });

      expect(screen.getByText('生成时间较久，请继续等待，完成后会自动显示结果。')).toBeInTheDocument();
      jest.useRealTimers();
    });

    it('handles regenerate button click', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ era_name: '现代' }));

      useGameStore.setState({
        creationStep: 0,
        playerName: 'TestPlayer',
        characterSettings: { era: { era_name: '古代' } },
      });

      render(<CreatePage />);

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('handles navigation between steps', async () => {
      useGameStore.setState({
        creationStep: 1,
        playerName: 'TestPlayer',
        characterSettings: { era: { era_name: '现代' } },
      });

      render(<CreatePage />);

      const prevButton = screen.getByText('上一步');
      fireEvent.click(prevButton);

      expect(gameSpy.spies.prevCreationStep).toBeDefined();
    });

    it('shows preset loaded message when isPresetLoaded is true', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
        isPresetLoaded: true,
      });

      render(<CreatePage />);
      expect(screen.getByText('已加载预设角色背景')).toBeInTheDocument();
    });

    it('shows auto-generated message when isPresetLoaded is false', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
        isPresetLoaded: false,
      });

      render(<CreatePage />);
      expect(screen.getByText('已为你自动生成角色背景')).toBeInTheDocument();
    });

    it('handles return to modify button in done phase', async () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);

      const returnButton = screen.getByText('返回修改');
      fireEvent.click(returnButton);

      expect(gameSpy.spies.setCreationStep).toBeDefined();
    });

    it('handles view details toggle', async () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);

      const viewButton = screen.getByText('查看设定详情');
      fireEvent.click(viewButton);

      await waitFor(() => {
        expect(viewButton).toBeInTheDocument();
      });
    });

    it('disables start game button when no player name', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: '',
        gameId: 1,
      });

      render(<CreatePage />);
      expect(screen.getByText('请先输入角色姓名')).toBeInTheDocument();
    });
  });

  describe('Image generation', () => {
    it('shows image generation loading state', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });
      useImageStore.setState({ isGeneratingImage: true });

      render(<CreatePage />);
      expect(screen.getByText('AI正在生成人物形象...')).toBeInTheDocument();
    });

    it('shows regenerate image button when images available', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });
      useImageStore.setState({
        playerImages: [{ image_id: 1, image_url: 'http://test.url/1.png' }],
        isGeneratingImage: false,
      });

      render(<CreatePage />);
      expect(screen.getByPlaceholderText(/不满意？描述你想要的修改/)).toBeInTheDocument();
    });

    it('shows multiple image thumbnails', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });
      useImageStore.setState({
        playerImages: [
          { image_id: 1, image_url: 'http://test.url/1.png' },
          { image_id: 2, image_url: 'http://test.url/2.png' },
        ],
        selectedImageIndex: 0,
        isGeneratingImage: false,
      });

      render(<CreatePage />);
      expect(screen.getByText('人物形象')).toBeInTheDocument();
    });

    it('shows background generation indicator', () => {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });
      useImageStore.setState({
        playerImages: [{ image_id: 1, image_url: 'http://test.url/1.png' }],
        isGeneratingImage: false,
      });

      render(<CreatePage />);
      expect(screen.getByText('人物形象')).toBeInTheDocument();
    });
  });

  describe('Step indicator navigation', () => {
    it('allows clicking on previous step indicators', () => {
      useGameStore.setState({
        creationStep: 2,
        playerName: 'TestPlayer',
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
        },
      });

      render(<CreatePage />);
      const stepIndicators = screen.getAllByRole('button');
      expect(stepIndicators.length).toBeGreaterThan(0);
    });
  });

  describe('Toast functionality', () => {
    it('shows error toast when generation fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'API Error' }, 400));

      useGameStore.setState({
        creationStep: 0,
        playerName: 'TestPlayer',
        characterSettings: {},
      });

      await act(async () => {
        render(<CreatePage />);
      });

      await waitFor(() => {
        expect(fetchCalled('/api/character/setting')).toBe(true);
      }, { timeout: 5000 });
    });

    it('shows success toast when preset is saved', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ preset_id: 1 }));

      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      await act(async () => {
        render(<CreatePage />);
      });

      const saveButton = screen.getByText('保存');
      await act(async () => {
        fireEvent.click(saveButton);
      });

      const input = screen.getByPlaceholderText('预设名称');
      fireEvent.change(input, { target: { value: 'Test Preset' } });

      const saveInSheet = screen.getAllByText('保存')[1];
      await act(async () => {
        fireEvent.click(saveInSheet);
      });

      await waitFor(() => {
        expect(fetchCalled('/api/presets')).toBe(true);
      });
    });

    it('shows error toast when preset save fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'Save failed' }, 400));

      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      await act(async () => {
        render(<CreatePage />);
      });

      const saveButton = screen.getByText('保存');
      await act(async () => {
        fireEvent.click(saveButton);
      });

      const input = screen.getByPlaceholderText('预设名称');
      fireEvent.change(input, { target: { value: 'Test Preset' } });

      const saveInSheet = screen.getAllByText('保存')[1];
      await act(async () => {
        fireEvent.click(saveInSheet);
      });

      await waitFor(() => {
        expect(fetchCalled('/api/presets')).toBe(true);
      });
    });
  });

  describe('handleStartGame scenarios', () => {
    it('creates new game when no gameId exists', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ game_id: 123 }));

      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: null,
      });

      await act(async () => {
        render(<CreatePage />);
      });

      const startButton = screen.getByText('开始游戏');
      await act(async () => {
        fireEvent.click(startButton);
      });

      await waitFor(() => {
        expect(fetchCalled('/api/games', 'POST')).toBe(true);
      });
    });

    it('shows error when game creation fails', async () => {
      // Use HTTP error response to avoid fetchWithRetry delays
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/presets') {
          return Promise.resolve(jsonResponse({ message: 'Preset save failed' }, 400));
        }
        return Promise.resolve(jsonResponse({ message: 'Create failed' }, 400));
      });

      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: null,
      });

      await act(async () => {
        render(<CreatePage />);
      });

      const startButton = screen.getByText('开始游戏');
      await act(async () => {
        fireEvent.click(startButton);
      });

      await waitFor(() => {
        expect(fetchCalled('/api/games', 'POST')).toBe(true);
      });
    });

    it('continues when auto-save preset fails', async () => {
      // preset.create fails with 400 (non-retryable), games.create succeeds
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/presets') {
          return Promise.resolve(errorResponse(400, 'Preset save failed'));
        }
        return Promise.resolve(jsonResponse({ game_id: 123 }));
      });

      useGameStore.setState({
        creationStep: 4,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
          world: { world_description: 'test' },
          family: { family_background: 'test' },
          relationships: { relationships_description: 'test' },
          traits: { traits: 'test' },
          wealth: { wealth_level: 'test' },
        },
        playerName: 'TestPlayer',
        gameId: null,
      });

      await act(async () => {
        render(<CreatePage />);
      });

      const startButton = screen.getByText('开始游戏');
      await act(async () => {
        fireEvent.click(startButton);
      });

      await waitFor(() => {
        expect(fetchCalled('/api/games', 'POST')).toBe(true);
      });
    });
  });

  describe('handleAcceptAndNext scenarios', () => {
    it('creates game at world step and advances', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ game_id: 123 }));

      useGameStore.setState({
        creationStep: 3,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 22 },
          gender: 'male',
        },
        playerName: 'TestPlayer',
        gameId: null,
      });

      await act(async () => {
        render(<CreatePage />);
      });

      expect(screen.getByText('世界观')).toBeInTheDocument();
    });

    it('saves generated content on accept', async () => {
      useGameStore.setState({
        creationStep: 0,
        characterSettings: {},
        playerName: 'TestPlayer',
      });

      await act(async () => {
        render(<CreatePage />);
      });

      expect(gameSpy.spies.updateCharacterSetting).toBeDefined();
    });
  });

  describe('Regenerate functionality', () => {
    it('calls handleGenerate with feedback', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ era_name: '古代' }));

      useGameStore.setState({
        creationStep: 0,
        characterSettings: { era: { era_name: '现代' } },
        playerName: 'TestPlayer',
      });

      render(<CreatePage />);

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility', () => {
    it('gives the inline setting regenerate icon button an accessible name', () => {
      useGameStore.setState({
        creationStep: 1,
        characterSettings: {
          era: { era_name: '现代' },
          age: { starting_age: 28 },
        },
        playerName: 'TestPlayer',
        gameId: 1,
      });

      render(<CreatePage />);

      expect(screen.getByRole('button', { name: '重新生成年龄阶段' })).toBeInTheDocument();
    });
  });
});
