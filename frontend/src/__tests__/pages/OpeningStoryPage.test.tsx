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

  afterEach(() => {
    jest.useRealTimers();
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

    it('routes a pre-reader stream rejection into the unified failed state', async () => {
      useGameStore.setState({ openingStory: '' });
      mockStreamOpeningStory.mockRejectedValueOnce(new Error('network before response body'));

      render(<OpeningStoryPage />);

      expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-screen')).toBeInTheDocument();
      expect(screen.getAllByRole('status')).toHaveLength(1);
    });

    it('treats an empty stream completion as failed instead of completing a blank opening', async () => {
      useGameStore.setState({ openingStory: '' });
      let handlers: Parameters<typeof streamOpeningStory>[4] | undefined;
      mockStreamOpeningStory.mockImplementation((...args) => {
        handlers = args[4];
        return Promise.resolve();
      });

      render(<OpeningStoryPage />);
      await waitFor(() => expect(handlers).toBeDefined());
      act(() => {
        handlers?.onComplete({});
      });

      expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-screen')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '开始我的人生' })).not.toBeInTheDocument();
    });

    it('keeps partial opening text visible with an inline retry after the stream fails', async () => {
      useGameStore.setState({ openingStory: '' });
      let handlers: Parameters<typeof streamOpeningStory>[4] | undefined;
      mockStreamOpeningStory.mockImplementation((...args) => {
        handlers = args[4];
        return Promise.resolve();
      });

      render(<OpeningStoryPage />);
      await waitFor(() => expect(handlers).toBeDefined());
      act(() => {
        handlers?.onStory('已经写下的开场。');
        handlers?.onError(new Error('stream dropped after first chunk'));
      });

      expect(await screen.findByText('已经写下的开场。')).toBeInTheDocument();
      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.getAllByRole('status')).toHaveLength(1);
    });

    it('renders two synchronously delivered chunks exactly once', async () => {
      jest.useFakeTimers();
      useGameStore.setState({ openingStory: '' });
      let handlers: Parameters<typeof streamOpeningStory>[4] | undefined;
      mockStreamOpeningStory.mockImplementation((...args) => {
        handlers = args[4];
        return new Promise(() => undefined);
      });

      render(<OpeningStoryPage />);
      await act(async () => {
        await Promise.resolve();
      });
      expect(handlers).toBeDefined();

      act(() => {
        handlers?.onStory('第一段。');
        handlers?.onStory('第二段。');
      });
      act(() => {
        jest.advanceTimersByTime(1_000);
      });

      expect(document.querySelector('.markdown-mock')).toHaveTextContent('第一段。第二段。');
      expect(document.querySelector('.markdown-mock')?.textContent).toBe('第一段。第二段。');
    });

    it('restarts a pending stream in the new language and fences the aborted attempt', async () => {
      useGameStore.setState({ openingStory: '' });
      const attempts: Array<{
        language: string;
        handlers: Parameters<typeof streamOpeningStory>[4];
        signal?: AbortSignal;
      }> = [];
      mockStreamOpeningStory.mockImplementation((...args) => {
        attempts.push({
          language: args[3],
          handlers: args[4],
          signal: args[5]?.signal,
        });
        return new Promise(() => undefined);
      });

      render(<OpeningStoryPage />);
      await waitFor(() => expect(attempts).toHaveLength(1));

      act(() => {
        useUIStore.getState().setLanguage('en');
      });

      await waitFor(() => expect(attempts).toHaveLength(2));
      expect(attempts[0].language).toBe('zh');
      expect(attempts[0].signal?.aborted).toBe(true);
      expect(attempts[1].language).toBe('en');
      expect(attempts[1].signal?.aborted).toBe(false);

      act(() => {
        attempts[0].handlers.onStory('不应出现的旧语言正文。');
        attempts[1].handlers.onStory('New-language opening.');
      });

      expect(await screen.findByText('New-language opening.')).toBeInTheDocument();
      expect(screen.queryByText('不应出现的旧语言正文。')).not.toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
    });

    it('starts exactly one live opening stream under StrictMode effect replay', async () => {
      useGameStore.setState({ openingStory: '' });
      const signals: AbortSignal[] = [];
      mockStreamOpeningStory.mockImplementation((...args) => {
        if (args[5]?.signal) signals.push(args[5].signal);
        return new Promise(() => undefined);
      });

      render(
        <React.StrictMode>
          <OpeningStoryPage />
        </React.StrictMode>
      );

      await waitFor(() => expect(signals).toHaveLength(1));
      expect(signals[0].aborted).toBe(false);
    });

    it('ignores callbacks from the failed attempt after a retry starts', async () => {
      useGameStore.setState({ openingStory: '' });
      const attempts: Array<Parameters<typeof streamOpeningStory>[4]> = [];
      mockStreamOpeningStory.mockImplementation((...args) => {
        attempts.push(args[4]);
        return new Promise(() => undefined);
      });

      render(<OpeningStoryPage />);
      await waitFor(() => expect(attempts).toHaveLength(1));
      act(() => {
        attempts[0].onStory('第一版残稿。');
        attempts[0].onError(new Error('first attempt failed'));
      });
      fireEvent.click(await screen.findByRole('button', { name: '重试' }));
      await waitFor(() => expect(attempts).toHaveLength(2));

      act(() => {
        attempts[0].onComplete({ full_story: '迟到的旧版完整故事。' });
        attempts[1].onStory('第二版正文。');
      });

      expect(await screen.findByText('第二版正文。')).toBeInTheDocument();
      expect(screen.queryByText('迟到的旧版完整故事。')).not.toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
    });

    it('routes a retry promise rejection back to the inline failed state', async () => {
      useGameStore.setState({ openingStory: '' });
      let firstHandlers: Parameters<typeof streamOpeningStory>[4] | undefined;
      mockStreamOpeningStory
        .mockImplementationOnce((...args) => {
          firstHandlers = args[4];
          return Promise.resolve();
        })
        .mockRejectedValueOnce(new Error('retry failed before response body'));

      render(<OpeningStoryPage />);
      await waitFor(() => expect(firstHandlers).toBeDefined());
      act(() => {
        firstHandlers?.onStory('保留的残稿。');
        firstHandlers?.onError(new Error('first attempt failed'));
      });
      fireEvent.click(await screen.findByRole('button', { name: '重试' }));

      await waitFor(() => expect(mockStreamOpeningStory).toHaveBeenCalledTimes(2));
      expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.getByText('保留的残稿。')).toBeInTheDocument();
      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
    });

    it.each([
      ['fast', 45_000],
      ['expert', 90_000],
      ['master', 180_000],
    ] as const)(
      'uses the %s upper bound for calm loading copy before and after the first chunk',
      async (constraintLevel, delay) => {
        jest.useFakeTimers();
        useGameStore.setState({ openingStory: '', constraintLevel });
        let handlers: Parameters<typeof streamOpeningStory>[4] | undefined;
        mockStreamOpeningStory.mockImplementation((...args) => {
          handlers = args[4];
          return Promise.resolve();
        });

        render(<OpeningStoryPage />);
        await act(async () => {
          await Promise.resolve();
        });

        expect(handlers).toBeDefined();
        expect(screen.getByTestId('narrative-loading-screen')).toBeInTheDocument();
        act(() => {
          jest.advanceTimersByTime(delay - 1);
        });
        expect(screen.queryByText('这一页仍在继续写作')).not.toBeInTheDocument();

        act(() => {
          jest.advanceTimersByTime(1);
        });
        expect(screen.getByTestId('narrative-loading-screen')).toHaveTextContent('这一页仍在继续写作');
        expect(document.body).not.toHaveTextContent(/fast|expert|master|45|90|180|秒|预计|AI/i);

        act(() => {
          handlers?.onStory('首段人生故事。');
        });

        expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
        expect(screen.getByTestId('narrative-loading-inline')).toHaveTextContent('这一页仍在继续写作');
        expect(screen.getAllByRole('status')).toHaveLength(1);
      },
    );
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
    it('pre-persists a restored opening before the player clicks start', async () => {
      render(<OpeningStoryPage />);

      await waitFor(() => {
        expect(mockPatchCharacterSettings).toHaveBeenCalledWith(
          123,
          expect.objectContaining({ opening_story: 'Test opening story content.' }),
          expect.objectContaining({ player_name: 'TestHero', life_vision: 'Be great' }),
        );
      });
    });

    it('pre-persists a newly completed streamed opening', async () => {
      useGameStore.setState({
        gameId: 123,
        openingStory: '',
        characterSettings: { era: { era_name: '现代' } },
        playerName: 'StreamHero',
        lifeVision: 'Keep going',
      });
      (window as any).__TEST_DATA__ = {
        playerName: 'StreamHero',
        lifeVision: 'Keep going',
        characterSettings: { era: { era_name: '现代' } },
      };
      mockStreamOpeningStory.mockImplementation(
        (_settings, _name, _vision, _language, handlers) => {
          handlers.onComplete({ full_story: '刚刚完成的开场。' });
          return Promise.resolve();
        },
      );

      render(<OpeningStoryPage />);

      await waitFor(() => {
        expect(mockPatchCharacterSettings).toHaveBeenCalledWith(
          123,
          expect.objectContaining({ opening_story: '刚刚完成的开场。' }),
          expect.objectContaining({ player_name: 'StreamHero', life_vision: 'Keep going' }),
        );
      });
    });

    it('retries opening persistence once without creating a second operation', async () => {
      mockPatchCharacterSettings
        .mockRejectedValueOnce(new Error('temporary failure'))
        .mockResolvedValueOnce({} as never);

      render(<OpeningStoryPage />);

      await waitFor(() => expect(mockPatchCharacterSettings).toHaveBeenCalledTimes(2));
    });

    it('shows start game button when story is complete', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByText('开始我的人生')).toBeInTheDocument();
    });

    it('shows the unified loading state while generation is incomplete', async () => {
      useGameStore.setState({ openingStory: '' });
      mockStreamOpeningStory.mockImplementation(() => new Promise(() => undefined));

      render(<OpeningStoryPage />);

      expect(await screen.findByTestId('narrative-loading-screen')).toHaveTextContent(
        '人生开篇，正在落笔',
      );
      expect(screen.queryByRole('button', { name: '开始我的人生' })).not.toBeInTheDocument();
      expect(screen.getAllByRole('status')).toHaveLength(1);
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
      await waitFor(() => expect(startButton).toBeEnabled());
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

    it('shows an entering state and navigates after the two-second persistence bound', async () => {
      jest.useFakeTimers();
      mockPatchCharacterSettings.mockImplementation(() => new Promise(() => undefined));
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

      render(<OpeningStoryPage />);
      await act(async () => {
        await Promise.resolve();
      });

      const startButton = screen.getByRole('button', { name: '开始我的人生' });
      await user.click(startButton);

      const enteringButton = screen.getByRole('button', { name: '正在进入' });
      expect(enteringButton).toBeDisabled();
      fireEvent.click(enteringButton);
      expect(mockPatchCharacterSettings).toHaveBeenCalledTimes(1);
      expect(mockPush).not.toHaveBeenCalled();

      await act(async () => {
        jest.advanceTimersByTime(1999);
        await Promise.resolve();
      });
      expect(mockPush).not.toHaveBeenCalled();

      await act(async () => {
        jest.advanceTimersByTime(1);
        await Promise.resolve();
      });
      expect(mockPush).toHaveBeenCalledWith('/play');
    });

    it('allows entry after the single persistence retry also fails', async () => {
      mockPatchCharacterSettings.mockRejectedValue(new Error('persistent failure'));
      const user = userEvent.setup();
      render(<OpeningStoryPage />);

      await waitFor(() => expect(mockPatchCharacterSettings).toHaveBeenCalledTimes(2));
      await user.click(screen.getByRole('button', { name: '开始我的人生' }));

      expect(mockPatchCharacterSettings).toHaveBeenCalledTimes(2);
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
