/**
 * Tests for OpeningStoryPage component
 * Note: This page has complex SSE streaming logic, tests focus on basic rendering
 */
import React from 'react';
import { act, render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OpeningStoryPage from '@/app/story/opening/page';
import { useGameStore } from '@/stores/useGameStore';
import { useImageStore } from '@/stores/useImageStore';
import { useUIStore } from '@/stores/useUIStore';
import { streamOpeningStory } from '@/lib/sse';
import { games } from '@/lib/api';

let isHydratedForTest = true;

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
  }),
}));

jest.mock('@/lib/sse', () => ({
  streamOpeningStory: jest.fn(),
}));

jest.mock('@/hooks/useHydration', () => ({
  useHydration: () => isHydratedForTest,
}));

jest.mock('@/lib/api', () => {
  const mockGames = {
    getActive: jest.fn(),
    patchCharacterSettings: jest.fn(),
  };
  return {
    __esModule: true,
    default: { games: mockGames },
    games: mockGames,
  };
});

const mockStreamOpeningStory = streamOpeningStory as jest.MockedFunction<typeof streamOpeningStory>;
const mockGetActive = games.getActive as jest.MockedFunction<typeof games.getActive>;
const mockPatchCharacterSettings = games.patchCharacterSettings as jest.MockedFunction<typeof games.patchCharacterSettings>;

function setupDefaultState() {
  useGameStore.setState({
    gameId: 123,
    openingStory: 'Test opening story content.',
    characterSettings: { era: { era_name: '现代' }, age: { starting_age: 22 } },
    playerName: 'TestHero',
    lifeVision: 'Be great',
  });
  useImageStore.setState({
    openingIllustration: null,
    isGeneratingIllustration: false,
    illustrationError: null,
  });
  useUIStore.setState({ language: 'zh' });
}

describe('OpeningStoryPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStreamOpeningStory.mockReset();
    mockGetActive.mockReset();
    mockPatchCharacterSettings.mockReset();
    mockPatchCharacterSettings.mockResolvedValue({} as never);
    delete (window as any).__TEST_DATA__;
    isHydratedForTest = true;
    setupDefaultState();
  });

  describe('Initial render', () => {
    it('renders without crashing', () => {
      render(<OpeningStoryPage />);
      // Page should render
    });

    it('renders correctly in hydrated state', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByText('Test opening story content.')).toBeInTheDocument();
    });

    it('displays opening story when available', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByText('Test opening story content.')).toBeInTheDocument();
    });

    it('displays continue button', () => {
      render(<OpeningStoryPage />);
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('displays player name in header', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByText('Test opening story content.')).toBeInTheDocument();
    });
  });

  describe('Narrative loading states', () => {
    it('does not reveal hydration loading until 250ms have elapsed', () => {
      jest.useFakeTimers();
      isHydratedForTest = false;
      useGameStore.setState({ openingStory: '' });

      render(<OpeningStoryPage />);

      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
      act(() => {
        jest.advanceTimersByTime(250);
      });
      expect(screen.getByTestId('narrative-loading-screen')).toHaveTextContent('正在打开这一页');
      jest.useRealTimers();
    });

    it('never shows an opening loading screen while hydration restores an existing opening', () => {
      jest.useFakeTimers();
      isHydratedForTest = false;
      const { rerender } = render(<OpeningStoryPage />);

      act(() => {
        jest.advanceTimersByTime(250);
      });
      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();

      isHydratedForTest = true;
      rerender(<OpeningStoryPage />);
      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
      expect(screen.getByText('Test opening story content.')).toBeInTheDocument();
      jest.useRealTimers();
    });

    it('replaces the opening screen with story text and an inline state after the first chunk', async () => {
      useGameStore.setState({ openingStory: '' });
      let handlers: Parameters<typeof streamOpeningStory>[4] | undefined;
      mockStreamOpeningStory.mockImplementation((...args) => {
        handlers = args[4];
        return Promise.resolve();
      });

      render(<OpeningStoryPage />);

      await waitFor(() => expect(handlers).toBeDefined());
      expect(screen.getByTestId('narrative-loading-screen')).toHaveTextContent('人生开篇，正在落笔');
      expect(screen.queryByTestId('narrative-loading-inline')).not.toBeInTheDocument();

      act(() => {
        handlers?.onStory('首段人生故事。');
      });

      expect(await screen.findByText('首段人生故事。')).toBeInTheDocument();
      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
      expect(document.querySelectorAll('[aria-live]')).toHaveLength(1);

      act(() => {
        handlers?.onComplete({ full_story: '首段人生故事。' });
      });

      expect(screen.queryByTestId('narrative-loading-inline')).not.toBeInTheDocument();
    });

    it('retries a failed opening stream without reloading the page', async () => {
      useGameStore.setState({ openingStory: '' });
      let handlers: Parameters<typeof streamOpeningStory>[4] | undefined;
      mockStreamOpeningStory.mockImplementation((...args) => {
        handlers = args[4];
        return Promise.resolve();
      });

      render(<OpeningStoryPage />);
      await waitFor(() => expect(handlers).toBeDefined());
      act(() => {
        handlers?.onError(new Error('stream dropped'));
      });

      fireEvent.click(await screen.findByRole('button', { name: '重试' }));
      expect(mockStreamOpeningStory).toHaveBeenCalledTimes(2);
      expect(mockPush).not.toHaveBeenCalled();
      expect(screen.getByTestId('narrative-loading-screen')).toBeInTheDocument();
    });
  });

  describe('Error handling', () => {
    it('shows error when missing player data', async () => {
      useGameStore.setState({ openingStory: '', characterSettings: {} as never, playerName: '' });
      render(<OpeningStoryPage />);
      await waitFor(() => {
        expect(screen.getByText(/缺少角色数据/)).toBeInTheDocument();
      });
    });

    it('generates opening story without gameId when character data is present', async () => {
      useGameStore.setState({ gameId: null as never, openingStory: '' });
      mockStreamOpeningStory.mockImplementation(
        (_settings, _name, _vision, _language, handlers) => {
          handlers.onStory('无存档开场片段');
          handlers.onComplete({ full_story: '无存档开场正文' });
          return Promise.resolve();
        }
      );

      render(<OpeningStoryPage />);

      await waitFor(() => {
        expect(screen.getByText('无存档开场正文')).toBeInTheDocument();
      });
      expect(screen.queryByText(/缺少角色数据|错误/)).not.toBeInTheDocument();
    });

    it('uses injected test data for generation request instead of stale store state', async () => {
      useGameStore.setState({
        openingStory: '',
        characterSettings: {} as never,
        playerName: '',
        lifeVision: '',
      });
      (window as any).__TEST_DATA__ = {
        playerName: 'InjectedHero',
        lifeVision: 'Injected Vision',
        characterSettings: { era: { era_name: '古代' } },
      };

      mockStreamOpeningStory.mockImplementation(
        (_settings, _name, _vision, _language, handlers) => {
          handlers.onStory('注入故事片段');
          handlers.onComplete({ full_story: '注入故事正文' });
          return Promise.resolve();
        }
      );

      render(<OpeningStoryPage />);

      await waitFor(() => {
        expect(mockStreamOpeningStory).toHaveBeenCalled();
      });

      expect(mockStreamOpeningStory).toHaveBeenCalledWith(
        { era: { era_name: '古代' } },
        'InjectedHero',
        'Injected Vision',
        'zh',
        expect.any(Object),
        expect.any(Object)
      );
      expect(screen.queryByText(/缺少角色数据/)).not.toBeInTheDocument();
    });

    it('recovers the active game before showing a missing character data error', async () => {
      const mockLoadGameState = jest.fn(async (gameId: number) => {
        useGameStore.setState({
          gameId,
          openingStory: 'Recovered opening story.',
          characterSettings: { era: { era_name: '近未来' } },
          playerName: 'RecoveredHero',
          lifeVision: 'Recover the truth',
        });
      });

      useGameStore.setState({
        gameId: null,
        openingStory: '',
        characterSettings: {} as never,
        playerName: '',
        lifeVision: '',
        loadGameState: mockLoadGameState as never,
      });
      mockGetActive.mockResolvedValue({
        game_id: 456,
        player_state: {} as never,
        progress: {} as never,
        round_info: {} as never,
        current_event: null,
        constraint_level: 'expert',
      });

      render(<OpeningStoryPage />);

      await waitFor(() => {
        expect(mockGetActive).toHaveBeenCalledTimes(1);
        expect(mockLoadGameState).toHaveBeenCalledWith(456);
      });

      await waitFor(() => {
        expect(screen.getByText('Recovered opening story.')).toBeInTheDocument();
      });
      expect(screen.queryByText(/缺少角色数据/)).not.toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('has navigation buttons', () => {
      render(<OpeningStoryPage />);
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Story display', () => {
    it('shows the story content', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByText('Test opening story content.')).toBeInTheDocument();
    });

    it('shows different story content when changed', () => {
      useGameStore.setState({ openingStory: 'A different opening story.' });
      render(<OpeningStoryPage />);
      expect(screen.getByText('A different opening story.')).toBeInTheDocument();
    });
  });

  describe('Illustration display', () => {
    it('shows illustration loading state', () => {
      useImageStore.setState({ isGeneratingIllustration: true });
      render(<OpeningStoryPage />);
      expect(screen.getByText(/AI正在为你绘制人生插画/)).toBeInTheDocument();
    });

    it('shows illustration when available', () => {
      useImageStore.setState({
        openingIllustration: { image_url: 'http://test.url/illustration.png', scene_description: 'A beautiful scene' },
      });
      render(<OpeningStoryPage />);
      expect(screen.getByAltText('开场插画')).toBeInTheDocument();
      expect(screen.getByText('A beautiful scene')).toBeInTheDocument();
    });

    it('shows illustration error state', () => {
      useImageStore.setState({ illustrationError: 'Failed to generate' });
      render(<OpeningStoryPage />);
      expect(screen.getByText(/插画生成失败/)).toBeInTheDocument();
    });

    it('shows retry button on illustration error', () => {
      useImageStore.setState({ illustrationError: 'Failed to generate' });
      render(<OpeningStoryPage />);
      expect(screen.getByText('重新生成插画')).toBeInTheDocument();
    });
  });

  describe('Start game button', () => {
    it('shows start game button when story is complete', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByText('开始我的人生')).toBeInTheDocument();
    });

    it('allows starting the game while opening illustration is still generating', async () => {
      useImageStore.setState({ isGeneratingIllustration: true });
      const user = userEvent.setup();
      render(<OpeningStoryPage />);

      const startButton = screen.getByRole('button', { name: '开始我的人生' });
      expect(startButton).toBeEnabled();

      await user.click(startButton);
      expect(mockPush).toHaveBeenCalledWith('/play');
    });

    it('allows starting immediately after a newly generated story while illustration is queued', async () => {
      useGameStore.setState({
        gameId: 123,
        openingStory: '',
        characterSettings: { era: { era_name: '现代' } },
        playerName: 'QueuedHero',
        lifeVision: 'Build carefully',
      });
      (window as any).__TEST_DATA__ = {
        playerName: 'QueuedHero',
        lifeVision: 'Build carefully',
        characterSettings: { era: { era_name: '现代' } },
      };
      mockStreamOpeningStory.mockImplementation(
        (_settings, _name, _vision, _language, handlers) => {
          handlers.onComplete({ full_story: '新生成的开场故事。' });
          return Promise.resolve();
        }
      );

      render(<OpeningStoryPage />);

      expect(await screen.findByText('新生成的开场故事。')).toBeInTheDocument();
      const startButton = screen.getByRole('button', { name: '开始我的人生' });
      expect(startButton).toBeEnabled();
    });

    it('navigates to play page when clicking start', async () => {
      const user = userEvent.setup();
      render(<OpeningStoryPage />);

      await user.click(screen.getByText('开始我的人生'));

      expect(mockPush).toHaveBeenCalledWith('/play');
    });

    it('persists the completed opening before entering play', async () => {
      const user = userEvent.setup();
      render(<OpeningStoryPage />);

      await user.click(screen.getByText('开始我的人生'));

      expect(mockPatchCharacterSettings).toHaveBeenCalledWith(
        123,
        expect.objectContaining({ opening_story: 'Test opening story content.' }),
        expect.objectContaining({ player_name: 'TestHero', life_vision: 'Be great' }),
      );
      expect(mockPush).toHaveBeenCalledWith('/play');
    });

    it('navigates to create page when no gameId', async () => {
      useGameStore.setState({ gameId: null as never });
      const user = userEvent.setup();
      render(<OpeningStoryPage />);

      await user.click(screen.getByText('开始我的人生'));

      expect(mockPush).toHaveBeenCalledWith('/create');
    });
  });
});
