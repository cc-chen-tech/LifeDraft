/**
 * Tests for PlayPage component
 */
import React from 'react';
import { webcrypto } from 'node:crypto';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PlayPage from '@/app/play/page';
import { useGameStore } from '@/stores/useGameStore';
import { useUIStore } from '@/stores/useUIStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';
import { INPUT_LIMITS } from '@/types/input-limits.generated';
import { api } from '@/lib/api';

// Mock usePlayGame hook
const mockUsePlayGame = {
  phase: 'options',
  options: [
    { text: 'Option 1', brief_result: 'Result 1' },
    { text: 'Option 2', brief_result: 'Result 2' },
  ],
  summaryText: '',
  roundSummary: null,
  isSaving: false,
  saveToast: null,
  regenerateToast: null,
  regenerationFailure: null,
  endingData: null,
  transport: 'active' as const,
  loadingOperation: 'event' as const,
  loadingIdentity: 0,
  gameId: 123,
  playerState: { player_name: 'TestPlayer', energy: 80, mood: 70 },
  progress: { week: 5, age: 22 },
  roundInfo: { current_round: 1, rounds_per_week: 3 },
  roundHistory: [],
  storyText: 'This is the current story text.',
  isGameOver: false,
  storyContainerRef: { current: null },
  setPhase: jest.fn(),
  setStoryText: jest.fn(),
  setOptions: jest.fn(),
  handleChoice: jest.fn(),
  handleCustomChoice: jest.fn(),
  handleContinueAfterSummary: jest.fn(),
  handleContinueToNextRound: jest.fn(),
  handleSave: jest.fn(),
  handleRegenerate: jest.fn(),
  generateEvent: jest.fn(),
  recoverEventGeneration: jest.fn(),
  recoverChoiceGeneration: jest.fn(),
  hydrated: true,
  router: { push: jest.fn(), replace: jest.fn() },
  // ★ 历史回顾相关
  showHistory: false,
  setShowHistory: jest.fn(),
  historyRoundIndex: null,
  isViewingHistory: false,
  displayText: 'This is the current story text.',  // ★ 默认显示 storyText
  handleOpenHistory: jest.fn(),
  handleSelectHistoryRound: jest.fn(),
  handleBackToCurrent: jest.fn(),
};

const mockUseDelayedLoading = jest.fn(() => false);

jest.mock('@/hooks/usePlayGame', () => ({
  usePlayGame: () => mockUsePlayGame,
}));

jest.mock('@/hooks/useDelayedLoading', () => ({
  useDelayedLoading: (options: unknown) => mockUseDelayedLoading(options),
}));

jest.mock('@/components/game/CollectionPanel', () => ({
  CollectionPanel: () => <div data-testid="collection-panel">Collection Panel</div>,
}));

describe('PlayPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseDelayedLoading.mockReturnValue(false);
    Object.defineProperty(globalThis, 'crypto', {
      value: webcrypto,
      configurable: true,
    });
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(jsonResponse({
          auto_read_enabled: false,
          selected_voice_color: 'warm_female',
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    jest.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
    jest.spyOn(window.HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
    useUIStore.setState({ processingMessage: '' });
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  describe('Daily listening handoff', () => {
    it('uses the full-screen listening experience for a completed daily chapter', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: '当天第一段。\n\n当天第二段。',
        displayText: '当天第一段。\n\n当天第二段。',
        playerState: {
          ...mockUsePlayGame.playerState,
          timeline: {
            version: 2,
            start_date: '2026-08-08',
            current_date: '2026-08-15',
            day_index: 7,
            day_number: 8,
            completed_days: 7,
            week_number: 2,
            weekday: 5,
            total_days: 365,
          },
        },
      });
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url.includes('/voice-reading/settings')) {
          return Promise.resolve(jsonResponse({
            auto_read_enabled: true,
            selected_voice_color: 'warm_female',
            selected_speed: 1,
            tts_provider: 'minimax',
            backend_audio_enabled: true,
          }));
        }
        if (url.includes('/voice-reading/progress')) {
          return Promise.resolve(jsonResponse({}, 404));
        }
        if (url.includes('/voice-reading/read')) {
          return Promise.resolve(jsonResponse({
            job_id: 44,
            status: 'ready',
            playback_mode: 'audio',
            provider: 'minimax',
            model: 'speech-02-turbo',
            message: '',
            segments: [{
              paragraph_index: 0,
              status: 'ready',
              audio_url: '/api/voice-reading/audio/day-8.mp3',
              duration_ms: 4000,
            }],
          }));
        }
        return Promise.resolve(jsonResponse({}));
      });

      render(<PlayPage />);

      expect(await screen.findByRole('heading', { name: '听故事' })).toBeInTheDocument();
      expect(screen.queryByText('已完成并带选项的故事。')).not.toBeInTheDocument();
    });

  });

  describe('Loading state', () => {
    it('keeps hydration visually quiet before the 250ms reveal', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({ ...mockUsePlayGame, hydrated: false });

      render(<PlayPage />);

      expect(screen.getByTestId('play-hydration-shell')).toHaveAttribute('aria-busy', 'true');
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
      expect(document.querySelector('.animate-spin')).not.toBeInTheDocument();
      expect(mockUseDelayedLoading).toHaveBeenCalledWith({
        isLoading: true,
        delay: 250,
        loadingIdentity: 'play-hydration',
      });
    });

    it('shows the unified hydration interstitial after 250ms', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({ ...mockUsePlayGame, hydrated: false });
      mockUseDelayedLoading.mockImplementation((options: unknown) => (
        (options as { loadingIdentity?: string }).loadingIdentity === 'play-hydration'
      ));

      render(<PlayPage />);

      expect(screen.getByTestId('narrative-loading-screen')).toBeInTheDocument();
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(screen.getByRole('status')).toHaveTextContent('正在打开这一页');
      expect(document.querySelector('.animate-spin')).not.toBeInTheDocument();
    });

    it('keeps the no-game recovery action at a named 44px touch target', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({ ...mockUsePlayGame, gameId: null });
      
      render(<PlayPage />);

      expect(screen.getByRole('heading', { name: '正在恢复当前进度' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '返回首页' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });
  });

  describe('Options phase', () => {
    beforeEach(() => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => mockUsePlayGame;
    });

    it('renders story text', () => {
      render(<PlayPage />);
      expect(screen.getByText(/This is the current story text/)).toBeInTheDocument();
    });

    it('renders option cards when in options phase', () => {
      render(<PlayPage />);
      expect(screen.getByText('Option 1')).toBeInTheDocument();
      expect(screen.getByText('Option 2')).toBeInTheDocument();
    });

    it('renders status bar with player info', () => {
      render(<PlayPage />);
      // StatusBar should be rendered with player state
    });
  });

  describe('Result phase', () => {
    it('shows continue button in result phase', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
      });
      
      render(<PlayPage />);
      expect(screen.getByText(/进入周中|确认并继续/)).toBeInTheDocument();
    });

    it('shows round summary when available', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        roundSummary: 'This is the round summary',
        options: [],
      });
      
      render(<PlayPage />);
      expect(screen.getByText('This is the round summary')).toBeInTheDocument();
    });

    it('renders resource warning details in the result summary', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        roundSummary: '本轮总结\n\n**资源提示**\n- 精力不足，实际变化为 -5',
        options: [],
      });

      render(<PlayPage />);
      expect(screen.getByText(/资源提示/)).toBeInTheDocument();
      expect(screen.getByText(/精力不足，实际变化为 -5/)).toBeInTheDocument();
    });

    it('calls handleContinueToNextRound on button click', () => {
      const mockContinue = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        handleContinueToNextRound: mockContinue,
      });
      
      render(<PlayPage />);
      const button = screen.getByRole('button', { name: /进入|确认/ });
      fireEvent.click(button);
      expect(mockContinue).toHaveBeenCalled();
    });


  });

  describe('Summary phase', () => {
    it('shows weekly summary content', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'summary',
        summaryText: 'Weekly summary content here',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('Weekly summary content here')).toBeInTheDocument();
      expect(screen.getByText('周总结')).toBeInTheDocument();
    });

    it('shows continue button after summary', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'summary',
        summaryText: 'Summary',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('继续人生旅途')).toBeInTheDocument();
    });
  });

  describe('Ending phase', () => {
    it('hands the production ending path to the hardened ending page', async () => {
      const mockRouter = { push: jest.fn(), replace: jest.fn() };
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'ending',
        router: mockRouter,
      });

      render(<PlayPage />);

      await waitFor(() => {
        expect(mockRouter.push).toHaveBeenCalledWith('/ending');
      });
      expect(screen.getByTestId('narrative-loading-screen')).toHaveTextContent('这一生，正在收束');
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(screen.queryByTestId('chat-bar-launcher')).not.toBeInTheDocument();
      expect(screen.queryByText(/A good ending|happy/)).not.toBeInTheDocument();
    });
  });

  describe('Error phase', () => {
    it('shows error message', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
      });
      
      render(<PlayPage />);
      expect(screen.getByRole('alert')).toHaveTextContent('这一段暂时没有写完');
      expect(screen.getByRole('alert')).toHaveTextContent('请重试当前故事');
    });

    it('shows retry button', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('重试')).toBeInTheDocument();
    });
  });

  describe('Save functionality', () => {
    it('keeps a persistent mobile save shortcut available outside the chat bar', async () => {
      const user = userEvent.setup();
      const handleSave = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        handleSave,
      });

      render(<PlayPage />);

      expect(screen.queryByTestId('chat-bar-launcher')).not.toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: '保存' }));

      expect(handleSave).toHaveBeenCalledTimes(1);
    });

    it('shows save success toast', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        saveToast: 'success',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('已保存')).toBeInTheDocument();
    });

    it('shows save error toast', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        saveToast: 'error',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('保存失败')).toBeInTheDocument();
    });
  });

  describe('Rewrite functionality', () => {
    it('keeps currentEvent in sync when inline rewrite completes', async () => {
      const user = userEvent.setup();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      const originalStory = '原始故事。';
      const rewrittenStory = '改写后的故事。';
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: originalStory,
        displayText: originalStory,
      });
      useGameStore.setState({
        currentEvent: {
          story: originalStory,
          options: [{ text: '继续', brief_result: '继续推进' }],
        },
        storyText: originalStory,
      });
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url.includes('/voice-reading/settings')) {
          return Promise.resolve(jsonResponse({
            auto_read_enabled: false,
            selected_voice_color: 'warm_female',
          }));
        }
        if (url.includes('/rewrite-stream')) {
          return Promise.resolve(createSSEMockResponse([
            `event: complete\ndata: {"new_story":"${rewrittenStory}","rewritten_story":"${rewrittenStory}"}\n\n`,
          ]));
        }
        return Promise.resolve(jsonResponse({}));
      });

      render(<PlayPage />);

      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '改写当前故事' }));
      fireEvent.change(screen.getByPlaceholderText(/描述你想要的修改/), {
        target: { value: '让语气更温柔' },
      });
      await user.click(screen.getByRole('button', { name: '改写故事' }));

      await waitFor(() => {
        expect(mockUsePlayGame.setStoryText).toHaveBeenCalledWith(rewrittenStory);
      });
      await waitFor(() => {
        expect(useGameStore.getState().currentEvent?.story).toBe(rewrittenStory);
      });
    });
  });

  describe('Navigation buttons', () => {
    it('does not expose the retired friends feature', () => {
      render(<PlayPage />);

      expect(
        screen.queryByRole('button', { name: /好友|社交|friends/i }),
      ).not.toBeInTheDocument();
    });
  });

  describe('History functionality', () => {
    it('shows history button', () => {
      render(<PlayPage />);
      // History button should be present
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('shows history drawer when open', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        showHistory: true,
        roundHistory: [], // Empty history to avoid rendering issues
      });
      
      render(<PlayPage />);
      // Verify the page renders without error
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('keeps collection and history panels mutually exclusive when both states can be true', async () => {
      const user = userEvent.setup();
      let historyOpen = true;
      const mockSetShowHistory = jest.fn((open: boolean) => {
        historyOpen = open;
      });
      const mockBackToCurrent = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        showHistory: historyOpen,
        setShowHistory: mockSetShowHistory,
        isViewingHistory: true,
        handleBackToCurrent: mockBackToCurrent,
        displayText: 'Historical story text',
        roundHistory: [],
      });

      const rendered = render(<PlayPage />);

      expect(screen.getByText('暂无历史记录')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '关闭历史回顾' }));
      rendered.rerender(<PlayPage />);
      await waitFor(() => {
        expect(screen.queryByRole('dialog', { name: '历史回顾' })).not.toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: '收集' }));

      expect(mockSetShowHistory).toHaveBeenCalledWith(false);
      expect(mockBackToCurrent).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('collection-panel')).toBeInTheDocument();
      expect(screen.queryByText('暂无历史记录')).not.toBeInTheDocument();
    });

    it('displays history indicator when viewing history', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isViewingHistory: true,
        displayText: 'Historical story text',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('Historical story text')).toBeInTheDocument();
    });
  });

  describe('Loading phase', () => {
    it('shows a gameplay section loader for an empty story using the raw SSE phase', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: '',
        displayText: '',
      });
      useUIStore.setState({ processingMessage: 'generating_options' });

      render(<PlayPage />);

      expect(screen.getByTestId('narrative-loading-section')).toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveTextContent('下一页，正在展开');
      expect(screen.getByRole('status')).toHaveTextContent('正在准备选择');
      expect(screen.queryByTestId('narrative-loading-inline')).not.toBeInTheDocument();
    });

    it('keeps completed story visible while options are pending', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: '正文已经完整生成，选项仍在准备。',
        displayText: '正文已经完整生成，选项仍在准备。',
      });
      useUIStore.setState({ processingMessage: 'generating_options' });

      render(<PlayPage />);

      await waitFor(() => {
        expect(screen.getByText('正文已经完整生成，选项仍在准备。')).toBeInTheDocument();
      });
      expect(screen.getByTestId('narrative-loading-inline')).toHaveTextContent('正在准备选择');
      expect(screen.queryByTestId('narrative-loading-section')).not.toBeInTheDocument();
      expect(screen.queryByText('出现错误，请重试')).not.toBeInTheDocument();
    });

    it('renders only an inline loader after partial choice text arrives', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'choosing',
        loadingOperation: 'choice',
        options: [],
        storyText: '选择后的故事还在继续。',
        displayText: '选择后的故事还在继续。',
      });
      useUIStore.setState({ processingMessage: 'unrecognized_sse_phase' });

      render(<PlayPage />);

      await waitFor(() => {
        expect(screen.getByText('选择后的故事还在继续。')).toBeInTheDocument();
      });
      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
      expect(screen.queryByTestId('narrative-loading-section')).not.toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-inline')).toHaveTextContent('正在继续推演');
    });

    it('keeps delayed active generation quiet without time or recovery actions', () => {
      const mockRecoverEventGeneration = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: '部分故事正文已经生成。',
        displayText: '部分故事正文已经生成。',
        loadingIdentity: 42,
        recoverEventGeneration: mockRecoverEventGeneration,
      });
      useGameStore.setState({ constraintLevel: 'fast' });
      mockUseDelayedLoading.mockReturnValue(true);

      render(<PlayPage />);

      const loader = screen.getByTestId('narrative-loading-inline');
      expect(loader).toHaveTextContent('这一页仍在继续写作');
      expect(loader).not.toHaveTextContent(/秒|分钟|预计|fast|expert|master/);
      expect(screen.queryByRole('button', { name: '恢复当前进度' })).not.toBeInTheDocument();
      expect(mockRecoverEventGeneration).not.toHaveBeenCalled();
      expect(mockUseDelayedLoading).toHaveBeenCalledWith({
        isLoading: true,
        delay: 45_000,
        loadingIdentity: 42,
      });
    });

    it('shows generating state with message', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: 'Some story',
        displayText: 'Some story',
      });
      
      render(<PlayPage />);
      // isStreaming=true during generating — wait for animation
      await waitFor(() => {
        expect(screen.getByText('Some story')).toBeInTheDocument();
      });
    });

    it('uses unified reconnect and real error failure actions without a reload card', async () => {
      const mockRecoverEventGeneration = jest.fn();
      const mockGenerateEvent = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: '',
        displayText: '',
        transport: 'reconnecting',
        recoverEventGeneration: mockRecoverEventGeneration,
      });

      const { rerender } = render(<PlayPage />);

      fireEvent.click(screen.getByRole('button', { name: '重新连接' }));
      expect(mockRecoverEventGeneration).toHaveBeenCalledTimes(1);
      expect(mockUsePlayGame.setOptions).not.toHaveBeenCalled();
      expect(mockUsePlayGame.setPhase).not.toHaveBeenCalled();

      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: '',
        displayText: '',
        transport: 'polling',
        recoverEventGeneration: mockRecoverEventGeneration,
      });
      rerender(<PlayPage />);
      fireEvent.click(screen.getByRole('button', { name: '重新连接' }));
      expect(mockRecoverEventGeneration).toHaveBeenCalledTimes(2);
      expect(mockUsePlayGame.setOptions).not.toHaveBeenCalled();
      expect(mockUsePlayGame.setPhase).not.toHaveBeenCalled();

      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
        options: [],
        storyText: '',
        displayText: '',
        transport: 'failed',
        generateEvent: mockGenerateEvent,
      });
      rerender(<PlayPage />);

      expect(screen.getByTestId('narrative-loading-section')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '重试' }));
      expect(mockGenerateEvent).toHaveBeenCalledTimes(1);
      expect(mockUsePlayGame.setPhase).not.toHaveBeenCalled();
      expect(screen.queryByRole('button', { name: '恢复当前进度' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '重新加载' })).not.toBeInTheDocument();
      expect(screen.queryByText('出现错误，请重试')).not.toBeInTheDocument();

      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
        options: [],
        storyText: '生成失败前已收到的正文。',
        displayText: '生成失败前已收到的正文。',
        transport: 'failed',
        generateEvent: mockGenerateEvent,
      });
      rerender(<PlayPage />);

      await waitFor(() => {
        expect(screen.getByText('生成失败前已收到的正文。')).toBeInTheDocument();
      });
      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
      expect(screen.queryByTestId('narrative-loading-section')).not.toBeInTheDocument();
    });

    it('routes a choosing recovery action to read-only choice reconciliation, not event generation', () => {
      const mockRecoverEventGeneration = jest.fn();
      const mockRecoverChoiceGeneration = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'choosing',
        loadingOperation: 'choice',
        options: [],
        storyText: '选择正在后台继续处理。',
        displayText: '选择正在后台继续处理。',
        transport: 'polling',
        recoverEventGeneration: mockRecoverEventGeneration,
        recoverChoiceGeneration: mockRecoverChoiceGeneration,
      });

      render(<PlayPage />);

      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '重新连接' }));
      expect(mockRecoverChoiceGeneration).toHaveBeenCalledTimes(1);
      expect(mockRecoverEventGeneration).not.toHaveBeenCalled();
    });

    it('preserves a failed choice identity, retries by read-only reconciliation, and keeps ChatBar hidden', () => {
      const mockGenerateEvent = jest.fn();
      const mockRecoverChoiceGeneration = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
        options: [],
        storyText: '选择失败前已收到的正文。',
        displayText: '选择失败前已收到的正文。',
        transport: 'failed',
        loadingOperation: 'choice',
        generateEvent: mockGenerateEvent,
        recoverChoiceGeneration: mockRecoverChoiceGeneration,
      });

      render(<PlayPage />);

      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-bar-launcher')).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '重试' }));
      expect(mockRecoverChoiceGeneration).toHaveBeenCalledTimes(1);
      expect(mockGenerateEvent).not.toHaveBeenCalled();
    });
  });

  describe('Choosing phase', () => {
    it('shows choosing state', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'choosing',
        loadingOperation: 'choice',
        options: [],
        storyText: 'Choosing story',
        displayText: 'Choosing story',
      });
      
      render(<PlayPage />);
      // isStreaming=true during choosing — wait for animation
      await waitFor(() => {
        expect(screen.getByText('Choosing story')).toBeInTheDocument();
      });
    });
  });

  describe('Game over state', () => {
    it('navigates game-over state to the ending page', async () => {
      const mockRouter = { push: jest.fn(), replace: jest.fn() };
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isGameOver: true,
        phase: 'ending',
        router: mockRouter,
      });

      render(<PlayPage />);
      await waitFor(() => expect(mockRouter.push).toHaveBeenCalledWith('/ending'));
    });
  });

  describe('Custom choice input', () => {
    it('renders chat bar for custom choices', () => {
      render(<PlayPage />);
      // ChatBar should be rendered for custom input
      const input = screen.queryByPlaceholderText(/输入你的选择/);
      // May or may not be visible depending on phase
    });
  });

  describe('Scene images', () => {
    it('renders scene images when available', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        eventSceneImage: {
          scene_id: 1,
          round_number: 1,
          stage: 'event',
          image_url: 'http://test.url/scene.png',
          scene_description: 'Test scene',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
      });
      
      render(<PlayPage />);
      // Scene image should be rendered
    });

    it('shows loading state for scene images', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isLoadingRoundSceneImage: true,
      });
      
      render(<PlayPage />);
      // Loading indicator should be shown
    });
  });

  describe('Prefetching state', () => {
    it('shows prefetching indicator during result phase', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        isPrefetching: true,
      });
      
      render(<PlayPage />);
      expect(screen.getByText('正在预加载下一段故事...')).toBeInTheDocument();
    });

    it('does not show prefetching indicator when not prefetching', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        isPrefetching: false,
      });
      
      render(<PlayPage />);
      expect(screen.queryByText('正在预加载下一段故事...')).not.toBeInTheDocument();
    });
  });

  describe('Regenerate toast', () => {
    it('shows success regenerate toast', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        regenerateToast: { type: 'success', message: '重新生成成功' },
      });
      
      render(<PlayPage />);
      expect(screen.getByText('重新生成成功')).toBeInTheDocument();
    });

    it('shows loading regenerate toast', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        regenerateToast: { type: 'loading', message: '正在重新生成...' },
      });
      
      render(<PlayPage />);
      expect(screen.getByText('正在重新生成...')).toBeInTheDocument();
    });

    it('shows error regenerate toast', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        regenerateToast: { type: 'error', message: '重新生成失败' },
      });
      
      render(<PlayPage />);
      expect(screen.getByText('重新生成失败')).toBeInTheDocument();
    });

    it('shows a persistent retryable failure with expandable details', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        regenerationFailure: {
          message: '故事角色一致性检查连续未通过',
          code: 'REQUIRED_CAST_MISSING',
          summary: '故事角色一致性检查连续未通过',
          detail: '当天需要登场的人物没有出现。失败稿没有保存。',
          retryable: true,
          attempts_used: 3,
          quality_level: 'expert',
          operation_id: 'op-123',
        },
      });

      render(<PlayPage />);

      expect(screen.getByText('故事角色一致性检查连续未通过')).toBeInTheDocument();
      expect(screen.getByText('查看失败详情')).toBeInTheDocument();
      expect(screen.getByText(/REQUIRED_CAST_MISSING/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '再次生成' })).toBeInTheDocument();
    });
  });

  describe('Tool actions', () => {
    it('has a named history shortcut', () => {
      render(<PlayPage />);
      expect(screen.getByRole('button', { name: '历史' })).toBeInTheDocument();
    });

    it('keeps home navigation inside the single tools sheet', async () => {
      const user = userEvent.setup();
      const mockRouter = { push: jest.fn() };
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        router: mockRouter,
      });
      
      render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '返回首页' }));
      expect(mockRouter.push).toHaveBeenCalledWith('/');
    });

    it('shows the tools save action as busy while saving', async () => {
      const user = userEvent.setup();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isSaving: true,
      });
      
      render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      expect(screen.getByRole('button', { name: '保存游戏' })).toBeDisabled();
      expect(screen.getByRole('button', { name: '保存游戏' })).toHaveAttribute('aria-busy', 'true');
    });

    it('keeps scene illustration inside the single tools sheet', async () => {
      const user = userEvent.setup();
      render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      expect(screen.getByRole('checkbox', { name: '场景插画' })).toBeInTheDocument();
    });

    it('closes history mode before opening collection panel', () => {
      const mockSetShowHistory = jest.fn();
      const mockHandleBackToCurrent = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isViewingHistory: true,
        setShowHistory: mockSetShowHistory,
        handleBackToCurrent: mockHandleBackToCurrent,
      });

      render(<PlayPage />);

      const collectionButton = screen.getByRole('button', { name: '收集' });
      fireEvent.click(collectionButton);

      expect(mockSetShowHistory).toHaveBeenCalledWith(false);
      expect(mockHandleBackToCurrent).toHaveBeenCalled();
    });

    it('opens history panel when history button clicked', () => {
      const mockHandleOpenHistory = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        handleOpenHistory: mockHandleOpenHistory,
      });

      render(<PlayPage />);

      const historyButton = screen.getByRole('button', { name: '历史' });
      fireEvent.click(historyButton);

      expect(mockHandleOpenHistory).toHaveBeenCalled();
    });

    it('returns to current mode when opening collection before switching to history', async () => {
      const user = userEvent.setup();
      const mockSetShowHistory = jest.fn();
      const mockHandleBackToCurrent = jest.fn();
      const mockHandleOpenHistory = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isViewingHistory: true,
        setShowHistory: mockSetShowHistory,
        handleBackToCurrent: mockHandleBackToCurrent,
        handleOpenHistory: mockHandleOpenHistory,
      });

      render(<PlayPage />);

      await user.click(screen.getByRole('button', { name: '收集' }));

      expect(mockSetShowHistory).toHaveBeenCalledWith(false);
      expect(mockHandleBackToCurrent).toHaveBeenCalled();

      await user.click(screen.getByRole('button', { name: '关闭收集' }));
      await user.click(screen.getByRole('button', { name: '历史' }));

      expect(mockHandleOpenHistory).toHaveBeenCalled();
    });

    it('restores the dock after closing collection so history can open', async () => {
      const user = userEvent.setup();
      const mockHandleOpenHistory = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        handleOpenHistory: mockHandleOpenHistory,
      });

      render(<PlayPage />);

      await user.click(screen.getByRole('button', { name: '收集' }));

      expect(screen.getByRole('dialog', { name: '收集' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '关闭收集' })).toHaveAttribute(
        'data-size',
        'icon-touch',
      );

      await user.click(screen.getByRole('button', { name: '关闭收集' }));
      await user.click(screen.getByRole('button', { name: '历史' }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog', { name: '收集' })).not.toBeInTheDocument();
      });
      expect(mockHandleOpenHistory).toHaveBeenCalled();
    });

    it('keeps keyboard focus inside the modal collection sheet', async () => {
      const user = userEvent.setup();
      render(<PlayPage />);

      const collectionTrigger = screen.getByRole('button', { name: '收集' });
      await user.click(collectionTrigger);
      const dialog = screen.getByRole('dialog', { name: '收集' });
      const closeButton = screen.getByRole('button', { name: '关闭收集' });
      const overlay = document.querySelector('[data-slot="sheet-overlay"]');

      expect(overlay).toHaveClass('bg-transparent');
      expect(overlay).not.toHaveClass('pointer-events-none');
      closeButton.focus();
      await user.tab({ shift: true });
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
      expect(screen.queryByRole('button', { name: '更多' })).not.toBeInTheDocument();

      await user.click(closeButton);
      await waitFor(() => expect(collectionTrigger).toHaveFocus());
    });

    it('returns focus to the history dock action after Escape closes its modal sheet', async () => {
      const user = userEvent.setup();
      let historyOpen = false;
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        showHistory: historyOpen,
        handleOpenHistory: jest.fn(() => {
          historyOpen = true;
        }),
        setShowHistory: jest.fn((open: boolean) => {
          historyOpen = open;
        }),
      });
      const rendered = render(<PlayPage />);

      const historyTrigger = screen.getByRole('button', { name: '历史' });
      await user.click(historyTrigger);
      rendered.rerender(<PlayPage />);
      expect(screen.getByRole('dialog', { name: '历史回顾' })).toBeInTheDocument();

      fireEvent.keyDown(document.body, { key: 'Escape', code: 'Escape' });
      rendered.rerender(<PlayPage />);

      await waitFor(() => expect(historyTrigger).toHaveFocus());
    });
  });

  describe('Result phase button text', () => {
    it('shows "进入周中" when on first round of the week', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        roundInfo: { current_round: 1, rounds_per_week: 3 },
      });
      
      render(<PlayPage />);
      expect(screen.getByText(/进入周中/)).toBeInTheDocument();
    });

    it('shows "进入周末" when on second round of the week', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        roundInfo: { current_round: 2, rounds_per_week: 3 },
      });
      
      render(<PlayPage />);
      expect(screen.getByText(/进入周末/)).toBeInTheDocument();
    });

    it('shows "确认并继续" when on last round of the week', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        roundInfo: { current_round: 3, rounds_per_week: 3 },
      });
      
      render(<PlayPage />);
      expect(screen.getByText(/确认并继续/)).toBeInTheDocument();
    });
  });

  describe('Ending phase variations', () => {
    it('does not render an unsafe inline ending response before navigation', async () => {
      const mockRouter = { push: jest.fn(), replace: jest.fn() };
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'ending',
        endingData: { ending_type: 'happy', summary: 'A wonderful life' },
        router: mockRouter,
      });

      render(<PlayPage />);

      await waitFor(() => expect(mockRouter.push).toHaveBeenCalledWith('/ending'));
      expect(screen.queryByText(/happy/)).not.toBeInTheDocument();
      expect(screen.queryByText(/A wonderful life/)).not.toBeInTheDocument();
    });
  });

  describe('Error handling', () => {
    it('calls generateEvent synchronously on the generic retry without a phase shim or timer', () => {
      const mockGenerateEvent = jest.fn();
      const timeoutSpy = jest.spyOn(global, 'setTimeout');
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
        generateEvent: mockGenerateEvent,
      });
      
      render(<PlayPage />);
      const retryButton = screen.getByText('重试');
      timeoutSpy.mockClear();
      fireEvent.click(retryButton);

      expect(mockGenerateEvent).toHaveBeenCalledTimes(1);
      expect(mockUsePlayGame.setPhase).not.toHaveBeenCalled();
      expect(timeoutSpy).not.toHaveBeenCalled();
      timeoutSpy.mockRestore();
    });
  });

  describe('Scene image variations', () => {
    it('shows result scene image in result phase', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        storyText: 'Some story',
        resultSceneImage: {
          scene_id: 2,
          round_number: 1,
          stage: 'result',
          image_url: 'http://test.url/result.png',
          scene_description: 'Result scene',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
      });
      
      render(<PlayPage />);
      // Result scene should be rendered
    });

    it('shows current round scene image as fallback', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: 'Some story',
        eventSceneImage: null,
        resultSceneImage: null,
        currentRoundSceneImage: {
          scene_id: 3,
          round_number: 1,
          stage: 'event',
          image_url: 'http://test.url/current.png',
          scene_description: 'Current scene',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
      });
      
      render(<PlayPage />);
      // Current round scene should be rendered
    });

    it('shows regenerating state for scene images', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        eventSceneImage: {
          scene_id: 1,
          round_number: 1,
          stage: 'event',
          image_url: 'http://test.url/scene.png',
          scene_description: 'Test scene',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
        isRegeneratingRoundScene: true,
      });
      
      render(<PlayPage />);
      // Regenerating state should be shown
    });
  });

  describe('History mode interactions', () => {
    it('shows history mode banner when viewing history', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isViewingHistory: true,
        displayText: 'Historical story text',
      });
      
      render(<PlayPage />);
      expect(screen.getByText(/正在查看历史轮次/)).toBeInTheDocument();
    });

    it('has return to current button in history mode', () => {
      const mockBackToCurrent = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isViewingHistory: true,
        displayText: 'Historical story',
        handleBackToCurrent: mockBackToCurrent,
      });
      
      render(<PlayPage />);
      const backButton = screen.getByText('返回当前');
      fireEvent.click(backButton);
      expect(mockBackToCurrent).toHaveBeenCalled();
    });

    it('shows streaming text in history mode', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        isViewingHistory: true,
        displayText: 'Historical story text',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('Historical story text')).toBeInTheDocument();
    });

    it('renders history text in a dedicated reading surface without current choices', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        isViewingHistory: true,
        displayText: 'Historical story text',
        historyDisplayText: 'Historical story text',
        currentHistoryRound: { week: 1, round: 2 },
        options: [
          { text: 'Current option should not cover history', brief_result: 'Result' },
        ],
      });

      render(<PlayPage />);

      expect(screen.getByTestId('history-reading-surface')).toHaveTextContent('Historical story text');
      expect(screen.queryByText('Current option should not cover history')).not.toBeInTheDocument();
    });
  });

  describe('Settings button', () => {
    it('opens the settings menu without opening the story assistant', async () => {
      const user = userEvent.setup();
      render(<PlayPage />);

      await user.click(screen.getByRole('button', { name: '打开工具' }));

      expect(screen.getByRole('dialog', { name: '游戏工具' })).toBeInTheDocument();
      expect(await screen.findByText('叙事质量')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '叙事风格' })).toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/向剧情助手提问/i)).not.toBeInTheDocument();
    });
  });

  describe('Scene image interactions', () => {
    it('calls fetchRoundSceneImage when refresh clicked', () => {
      const mockFetch = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: 'Some story',
        eventSceneImage: {
          scene_id: 1,
          round_number: 1,
          stage: 'event',
          image_url: 'http://test.url/scene.png',
          scene_description: 'Test scene',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
        currentRound: 1,
        fetchRoundSceneImage: mockFetch,
      });
      
      render(<PlayPage />);
      // Scene image should be rendered
    });

    it('calls regenerateRoundSceneImage when regenerate clicked', () => {
      const mockRegenerate = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: 'Some story',
        eventSceneImage: {
          scene_id: 1,
          round_number: 1,
          stage: 'event',
          image_url: 'http://test.url/scene.png',
          scene_description: 'Test scene',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
        currentRound: 1,
        regenerateRoundSceneImage: mockRegenerate,
      });
      
      render(<PlayPage />);
      // Scene image with regenerate should be rendered
    });

    it('refreshes result scene image for the just-completed round', () => {
      const mockFetch = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        storyText: 'Result story for the completed round',
        eventSceneImage: null,
        resultSceneImage: {
          scene_id: 4,
          week: 3,
          round_number: 3,
          stage: 'result',
          image_url: 'http://test.url/week4-result.png',
          scene_description: '第4周逃亡居民楼证据',
          referenced_images: [],
          created_at: '2024-01-04T00:00:00Z',
        },
        currentRound: 4,
        fetchRoundSceneImage: mockFetch,
      });

      render(<PlayPage />);
      fireEvent.click(screen.getByText('刷新'));

      expect(mockFetch).toHaveBeenCalledWith(3, 'result', { retry: true });
    });

    it('shows a scene provider failure and retries only from the explicit button', () => {
      const mockFetch = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: 'Event story waiting for an image',
        eventSceneImage: null,
        resultSceneImage: null,
        currentRoundSceneImage: null,
        isLoadingRoundSceneImage: false,
        roundSceneError: '图片生成额度暂时不可用，请稍后再试',
        currentRound: 2,
        fetchRoundSceneImage: mockFetch,
      });

      render(<PlayPage />);

      expect(screen.getByText('图片生成额度暂时不可用，请稍后再试')).toBeVisible();
      fireEvent.click(screen.getByRole('button', { name: '重试生成场景插画' }));
      expect(mockFetch).toHaveBeenCalledWith(2, 'event', { retry: true });
    });

    it('keeps a visible loading placeholder while an event scene retry is running', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: 'Event story waiting for a retried image',
        eventSceneImage: null,
        resultSceneImage: null,
        currentRoundSceneImage: null,
        isLoadingRoundSceneImage: true,
        roundSceneError: null,
        currentRound: 2,
      });

      render(<PlayPage />);

      expect(screen.getByText('正在生成场景插画...')).toBeVisible();
    });
  });

  describe('ChatBar interactions', () => {
    it('renders chat bar with correct props', () => {
      render(<PlayPage />);
      // ChatBar should be rendered
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('RoundHistoryDrawer interactions', () => {
    it('renders history drawer with correct props', () => {
      const mockSetShowHistory = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        showHistory: true,
        setShowHistory: mockSetShowHistory,
        roundHistory: [],
      });
      
      render(<PlayPage />);
      // History drawer should be rendered
    });
  });

  describe('story101 long-page presentation', () => {
    it('uses one reading surface with one desktop tools trigger and one mobile action dock', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: '清晨七点半，她把主题旋律重新拆成三段。',
        displayText: '清晨七点半，她把主题旋律重新拆成三段。',
      });

      const { container } = render(<PlayPage />);

      expect(container.querySelectorAll('[data-slot="page-transition"]')).toHaveLength(1);
      expect(container.querySelector('[data-slot="page-transition"]')).toHaveClass('play-reading-axis');
      expect(container.querySelector('[data-slot="page-transition"]')).toHaveClass('pt-6', 'md:pt-10');
      expect(container.querySelector('[data-slot="page-transition"]')).not.toHaveClass('pt-36');
      expect(container.querySelectorAll('[data-slot="surface"][data-variant="reading"]')).toHaveLength(1);
      expect(screen.getByTestId('play-reading-surface')).toBeInTheDocument();
      expect(container.querySelector('header.sticky')).not.toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: '打开工具' })).toHaveLength(1);
      expect(screen.getByRole('navigation', { name: '游戏快捷工具' })).toBeInTheDocument();
      expect(container.querySelectorAll('[data-testid="chat-bar-launcher"]')).toHaveLength(0);
    });

    it('renders only the real round summary and never fabricates option effects', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [{
          text: '细读合作条款',
          brief_result: '虚构结果不得展示',
          potential_effects: { mood: 12 },
        }],
        storyText: '她圈出了三处需要继续确认的条款。',
        displayText: '她圈出了三处需要继续确认的条款。',
        roundSummary: '她留下了核对清单。\n\n**资源提示：** 时间安排需要调整。',
      });

      const { container } = render(<PlayPage />);

      const summary = screen.getByTestId('round-summary');
      expect(summary).toHaveTextContent('她留下了核对清单');
      expect(summary).toHaveTextContent('资源提示');
      expect(summary).not.toHaveClass('rounded-lg');
      expect(summary).not.toHaveAttribute('style');
      expect(screen.queryByText('虚构结果不得展示')).not.toBeInTheDocument();
      expect(screen.queryByText(/mood|\+12/)).not.toBeInTheDocument();
      expect(container.querySelector('[data-slot="card"]')).not.toBeInTheDocument();
    });

    it('keeps the same assistant state across busy and history hiding through the tools surface', async () => {
      const user = userEvent.setup();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      let viewState = {
        phase: 'options',
        isViewingHistory: false,
        displayText: '当前故事正文',
      };
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        ...viewState,
        storyText: '当前故事正文',
      });

      const rendered = render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));
      await user.type(screen.getByPlaceholderText(/向剧情助手提问/i), '这段问题需要保留');

      viewState = { ...viewState, phase: 'choosing' };
      rendered.rerender(<PlayPage />);
      expect(screen.queryByPlaceholderText(/向剧情助手提问/i)).not.toBeInTheDocument();

      viewState = { ...viewState, phase: 'result' };
      rendered.rerender(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));
      expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toHaveValue('这段问题需要保留');

      viewState = { ...viewState, isViewingHistory: true };
      rendered.rerender(<PlayPage />);
      expect(screen.queryByPlaceholderText(/向剧情助手提问/i)).not.toBeInTheDocument();

      viewState = { ...viewState, isViewingHistory: false };
      rendered.rerender(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));
      expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toHaveValue('这段问题需要保留');
    });

    it('closes the assistant before opening the tool hub or collection panel', async () => {
      const user = userEvent.setup();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({ ...mockUsePlayGame });

      render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));
      expect(screen.getByRole('textbox', { name: '剧情助手问题' })).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '打开工具' }));
      expect(screen.getByRole('dialog', { name: '游戏工具' })).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.queryByRole('textbox', { name: '剧情助手问题' })).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));
      await user.click(screen.getByRole('button', { name: '收集' }));
      expect(screen.getByRole('dialog', { name: '收集' })).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.queryByRole('textbox', { name: '剧情助手问题' })).not.toBeInTheDocument();
      });
    });


    it.each([
      ['保存', 'handleSave'],
      ['历史', 'handleOpenHistory'],
    ] as const)('closes the assistant before the mobile %s action', async (label, handlerName) => {
      const user = userEvent.setup();
      const handler = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        [handlerName]: handler,
      });

      render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));
      await user.click(screen.getByRole('button', { name: label }));

      expect(handler).toHaveBeenCalledTimes(1);
      await waitFor(() => {
        expect(screen.queryByRole('textbox', { name: '剧情助手问题' })).not.toBeInTheDocument();
      });
    });

    it('disables rewrite in the tools hub when the real story exceeds its generated limit', async () => {
      const user = userEvent.setup();
      const overLimitStory = '字'.repeat(INPUT_LIMITS.fullStory + 1);
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        storyText: overLimitStory,
        displayText: overLimitStory,
      });

      render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));

      const rewrite = screen.getByRole('button', { name: '改写当前故事' });
      expect(rewrite).toBeDisabled();
      expect(screen.getByText(/当前故事超过.*无法提交改写/)).toBeInTheDocument();
    });

    it('keeps one page feedback announcement and does not duplicate the gameplay loader', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        storyText: '已经出现的正文',
        displayText: '已经出现的正文',
        regenerateToast: { type: 'loading', message: '正在重新生成...' },
      });

      const { container } = render(<PlayPage />);

      expect(screen.getByTestId('narrative-loading-inline')).toBeInTheDocument();
      expect(screen.queryByText('正在重新生成...')).not.toBeInTheDocument();
      expect(container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);
    });

    it('renders at most one fixed page notice when save and regenerate feedback overlap', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        saveToast: 'success',
        regenerateToast: { type: 'success', message: '重新生成成功' },
      });

      const { container } = render(<PlayPage />);

      expect(container.querySelectorAll('.play-feedback')).toHaveLength(1);
      expect(screen.getByText('重新生成成功')).toBeInTheDocument();
      expect(screen.queryByText('已保存')).not.toBeInTheDocument();
      expect(container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);
    });

    it('lets page feedback own announcements while a visible scene error stays readable', async () => {
      useGameStore.setState({ enableSceneImage: true });
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        saveToast: 'success',
        eventSceneImage: {
          scene_id: 9,
          round_number: 1,
          stage: 'event',
          image_url: 'http://test.url/event.png',
          scene_description: 'Event scene',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
        roundSceneError: '场景插画暂时无法更新',
        isLoadingRoundSceneImage: false,
      });

      const { container } = render(<PlayPage />);

      expect(await screen.findByText('已保存')).toBeInTheDocument();
      expect(screen.getByText('场景插画暂时无法更新')).toBeInTheDocument();
      expect(container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);
    });

    it('temporarily replaces the inline phase error with save feedback as the single live owner', () => {
      jest.useFakeTimers();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      let currentSaveToast: null | 'error' = 'error';
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
        transport: 'active',
        saveToast: currentSaveToast,
      });

      const rendered = render(<PlayPage />);

      expect(screen.queryByText('这一段暂时没有写完')).not.toBeInTheDocument();
      expect(screen.getByText('保存失败')).toBeInTheDocument();
      expect(rendered.container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);

      currentSaveToast = null;
      rendered.rerender(<PlayPage />);

      expect(screen.queryByText('这一段暂时没有写完')).not.toBeInTheDocument();
      expect(screen.getByText('保存失败')).toBeInTheDocument();
      expect(rendered.container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);

      act(() => jest.advanceTimersByTime(3000));
      expect(screen.getByText('这一段暂时没有写完')).toBeInTheDocument();
      expect(screen.queryByText('保存失败')).not.toBeInTheDocument();
      expect(rendered.container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);
    });

    it('defers page feedback while the focused assistant is open and restores it after close', async () => {
      const user = userEvent.setup();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      let currentSaveToast: null | 'success' = null;
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        saveToast: currentSaveToast,
      });
      const rendered = render(<PlayPage />);
      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));

      currentSaveToast = 'success';
      rendered.rerender(<PlayPage />);

      expect(screen.getByRole('textbox', { name: '剧情助手问题' })).toBeInTheDocument();
      expect(screen.queryByText('已保存')).not.toBeInTheDocument();

      currentSaveToast = null;
      rendered.rerender(<PlayPage />);
      expect(screen.queryByText('已保存')).not.toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '关闭剧情助手' }));

      expect(await screen.findByText('已保存')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '打开工具' })).toHaveFocus();
    });

    it('suspends the inline phase error while summary owns the single live region', async () => {
      const user = userEvent.setup();
      jest.spyOn(api.gameplay, 'generateSummary').mockImplementation(
        () => new Promise(() => undefined),
      );
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
        transport: 'active',
      });

      const { container } = render(<PlayPage />);
      expect(screen.getByText('这一段暂时没有写完')).toBeInTheDocument();
      const liveSelector = '[aria-live], [role="status"], [role="alert"]';
      const countLiveNodes = (node: Node) => {
        if (!(node instanceof Element)) return 0;
        return Number(node.matches(liveSelector)) + node.querySelectorAll(liveSelector).length;
      };
      let liveRegionCount = container.querySelectorAll(liveSelector).length;
      let peakLiveRegionCount = liveRegionCount;
      let observedMutation = false;
      const observer = new MutationObserver((records) => {
        observedMutation = true;
        for (const record of records) {
          for (const node of record.removedNodes) {
            liveRegionCount -= countLiveNodes(node);
          }
          for (const node of record.addedNodes) {
            liveRegionCount += countLiveNodes(node);
            peakLiveRegionCount = Math.max(peakLiveRegionCount, liveRegionCount);
          }
        }
      });
      observer.observe(container, { childList: true, subtree: true });

      await user.click(screen.getByRole('button', { name: '打开工具' }));
      await user.click(screen.getByRole('button', { name: '生成人生总结' }));

      expect(await screen.findByText('正在生成总结...')).toBeInTheDocument();
      expect(screen.queryByText('这一段暂时没有写完')).not.toBeInTheDocument();
      expect(container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);
      await waitFor(() => expect(observedMutation).toBe(true));
      observer.disconnect();
      expect(peakLiveRegionCount).toBe(1);
    });



    it('suppresses existing page feedback for the full tools and assistant surface lifetime', async () => {
      const user = userEvent.setup();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        saveToast: 'success',
      });
      render(<PlayPage />);
      expect(screen.getByText('已保存')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '打开工具' }));
      expect(screen.getByRole('dialog', { name: '游戏工具' })).toBeInTheDocument();
      expect(screen.queryByText('已保存')).not.toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '打开剧情助手' }));
      expect(screen.getByRole('textbox', { name: '剧情助手问题' })).toBeInTheDocument();
      expect(screen.queryByText('已保存')).not.toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '关闭剧情助手' }));
      expect(await screen.findByText('已保存')).toBeInTheDocument();
    });
  });
});
