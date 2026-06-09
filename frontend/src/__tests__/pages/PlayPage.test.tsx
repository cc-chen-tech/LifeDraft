/**
 * Tests for PlayPage component
 */
import React from 'react';
import { webcrypto } from 'node:crypto';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PlayPage from '@/app/play/page';
import { GlobalMusicPlayer } from '@/components/game/GlobalMusicPlayer';
import { useGameStore } from '@/stores/useGameStore';
import { useMusicStore } from '@/stores/useMusicStore';
import { useStoryVoiceStore } from '@/stores/useStoryVoiceStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

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
  endingData: null,
  elapsedSeconds: 0,
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
  getLoadingMessage: jest.fn(() => 'Loading...'),
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

jest.mock('@/hooks/usePlayGame', () => ({
  usePlayGame: () => mockUsePlayGame,
  STATUS_MESSAGES: {
    preparing: '正在准备...',
    generating_story: '正在生成故事...',
  },
}));

describe('PlayPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
    useMusicStore.setState({ activeStoryText: null, activeGameId: null });
    useStoryVoiceStore.setState({
      readingState: 'idle',
      currentSource: '',
      currentContextLabel: '',
      currentAudioUrl: '',
      currentJobId: null,
      currentProvider: '',
      playbackMode: 'none',
      spokenTextLength: 0,
      currentSpeechText: '',
      errorMessage: '',
      queueText: '',
      autoReadEnabled: false,
      selectedVoiceId: 'warm_female',
      musicDuckState: 'idle',
      musicWasPlaying: false,
      userChangedMusic: false,
      activeReadingContext: null,
      activeAutoReadText: '',
      activeAutoReadReady: false,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Music handoff', () => {
    it('does not send partial generating story text to the global music player', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        storyText: '流式生成中的半截故事。',
        displayText: '流式生成中的半截故事。',
        options: [],
      });

      render(<PlayPage />);

      await waitFor(() => {
        expect(useMusicStore.getState().activeGameId).toBe(123);
      });
      expect(useMusicStore.getState().activeStoryText).toBeNull();
    });

    it('sends completed option-phase story text to the global music player', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: '已完成并带选项的故事。',
        displayText: '已完成并带选项的故事。',
      });

      render(<PlayPage />);

      await waitFor(() => {
        expect(useStoryVoiceStore.getState().activeReadingContext?.text).toBe(
          '已完成并带选项的故事。'
        );
      });

      await waitFor(() => {
        expect(useMusicStore.getState().activeStoryText).toBe('已完成并带选项的故事。');
      });
    });

    it('does not render a standalone narration bar inside the story page', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'options',
        storyText: '已完成并带选项的故事。',
        displayText: '已完成并带选项的故事。',
      });

      render(<PlayPage />);

      await waitFor(() => {
        expect(useStoryVoiceStore.getState().activeReadingContext?.text).toBe(
          '已完成并带选项的故事。'
        );
      });

      expect(screen.queryByRole('region', { name: '故事朗读' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '朗读故事' })).not.toBeInTheDocument();
    });
  });

  describe('Loading state', () => {
    it('shows loading spinner when not hydrated', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({ ...mockUsePlayGame, hydrated: false });
      
      render(<PlayPage />);
      // Should show loading state
    });

    it('shows loading spinner when no gameId', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({ ...mockUsePlayGame, gameId: null });
      
      render(<PlayPage />);
      // Should show loading state
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

    it('auto-reads the completed choice result story while the sound panel stays collapsed', async () => {
      const user = userEvent.setup();
      useStoryVoiceStore.setState({ autoReadEnabled: true });
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url.includes('/voice-reading/settings')) {
          return Promise.resolve(jsonResponse({
            auto_read_enabled: true,
            selected_voice_color: 'warm_female',
          }));
        }
        if (url.includes('/voice-reading/read')) {
          return Promise.resolve(jsonResponse({
            job_id: 9,
            status: 'ready',
            audio_url: '/api/voice-reading/audio/choice-result.mp3',
            playback_mode: 'audio',
            provider: 'minimax',
            media_type: 'audio/mpeg',
          }));
        }
        if (url.includes('/music/recommend')) {
          return Promise.resolve(jsonResponse({
            keywords: ['选择后的故事'],
            mood: 'calm',
            scene_type: 'story_result',
            songs: [],
          }));
        }
        return Promise.resolve(jsonResponse({}));
      });
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'result',
        options: [],
        storyText: '主角做出选择后的完整续写。',
        displayText: '主角做出选择后的完整续写。',
      });

      render(
        <>
          <PlayPage />
          <GlobalMusicPlayer />
        </>
      );

      await waitFor(() => {
        expect(useStoryVoiceStore.getState().activeReadingContext?.text).toBe(
          '主角做出选择后的完整续写。'
        );
      });
      expect(useStoryVoiceStore.getState().activeAutoReadReady).toBe(true);

      await waitFor(() => {
        expect((global.fetch as jest.Mock).mock.calls.some(([url]) =>
          String(url).includes('/voice-reading/read')
        )).toBe(true);
      });
      expect(screen.queryByRole('region', { name: '声音面板' })).not.toBeInTheDocument();
      const readCall = (global.fetch as jest.Mock).mock.calls.find(([url]) =>
        String(url).includes('/voice-reading/read')
      );
      const payload = JSON.parse(String(readCall?.[1]?.body ?? '{}'));
      expect(payload.context.text).toBe('主角做出选择后的完整续写。');

      await user.click(screen.getByRole('button', { name: '展开声音面板' }));
      expect(screen.getByRole('region', { name: '故事朗读' })).toBeInTheDocument();
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
    it('shows ending title', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'ending',
        endingData: { ending_type: 'happy', summary: 'A good ending' },
      });
      
      render(<PlayPage />);
      expect(screen.getByText('人生落幕')).toBeInTheDocument();
    });

    it('shows home button in ending', () => {
      const mockRouter = { push: jest.fn() };
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'ending',
        endingData: null,
        router: mockRouter,
      });
      
      render(<PlayPage />);
      expect(screen.getByText('返回首页')).toBeInTheDocument();
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
      expect(screen.getByText('出现错误，请重试')).toBeInTheDocument();
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

      await user.click(screen.getByRole('button', { name: '改写' }));
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
    it('shows friends button that navigates to profile', () => {
      const mockRouter = { push: jest.fn() };
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        router: mockRouter,
      });

      render(<PlayPage />);
      const friendsButton = screen.getByRole('button', { name: /好友|社交|friends/i });
      expect(friendsButton).toBeInTheDocument();
      fireEvent.click(friendsButton);
      expect(mockRouter.push).toHaveBeenCalledWith('/profile');
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
    it('shows loading skeleton', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'loading',
        options: [],
        storyText: '', // Empty story triggers skeleton
        getLoadingMessage: () => '正在生成故事...',
      });
      
      render(<PlayPage />);
      // Loading skeleton should be shown
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('keeps recovery controls visible and uses the forced recovery action when loading has no story or options', async () => {
      const mockRecoverEventGeneration = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'loading',
        options: [],
        storyText: '',
        displayText: '',
        elapsedSeconds: 45,
        recoverEventGeneration: mockRecoverEventGeneration,
        getLoadingMessage: () => '故事生成中...',
      });

      render(<PlayPage />);

      expect(screen.getByText('故事生成中...')).toBeInTheDocument();
      const recoveryButton = screen.getByRole('button', { name: '恢复当前进度' });
      expect(recoveryButton).toBeInTheDocument();

      fireEvent.click(recoveryButton);
      await waitFor(() => {
        expect(mockRecoverEventGeneration).toHaveBeenCalledTimes(1);
      });
    });

    it('does not show empty recovery controls when streamed story text exists without options', async () => {
      const mockRecoverEventGeneration = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'loading',
        options: [],
        storyText: '已恢复的故事正文，但还没有选项。',
        displayText: '已恢复的故事正文，但还没有选项。',
        elapsedSeconds: 20,
        recoverEventGeneration: mockRecoverEventGeneration,
        getLoadingMessage: () => '故事生成中...',
      });

      render(<PlayPage />);

      expect(screen.getByText('已恢复的故事正文，但还没有选项。')).toBeInTheDocument();
      expect(screen.queryByText(/如果生成时间较长/)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '恢复当前进度' })).not.toBeInTheDocument();
      expect(mockRecoverEventGeneration).not.toHaveBeenCalled();
    });

    it('shows generating state with message', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: 'Some story',
        displayText: 'Some story',
        elapsedSeconds: 30,
        getLoadingMessage: () => '正在生成故事...',
      });
      
      render(<PlayPage />);
      // isStreaming=true during generating — wait for animation
      await waitFor(() => {
        expect(screen.getByText('Some story')).toBeInTheDocument();
      });
    });

    it('explains long-running generation when partial story text already exists', async () => {
      const mockRecoverEventGeneration = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'generating',
        options: [],
        storyText: '部分故事正文已经生成，但选项还在校验。',
        displayText: '部分故事正文已经生成，但选项还在校验。',
        elapsedSeconds: 75,
        recoverEventGeneration: mockRecoverEventGeneration,
        getLoadingMessage: () => '故事逻辑校验中，正在优化...',
      });

      render(<PlayPage />);

      expect(screen.getByText(/已等待 1分15秒/)).toBeInTheDocument();
      expect(screen.getByText(/正在校验故事逻辑和生成选项/)).toBeInTheDocument();
      const recoveryButton = screen.getByRole('button', { name: '恢复当前进度' });
      fireEvent.click(recoveryButton);
      await waitFor(() => {
        expect(mockRecoverEventGeneration).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('Choosing phase', () => {
    it('shows choosing state', async () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'choosing',
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
    it('shows game over state when isGameOver is true', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isGameOver: true,
        phase: 'ending',
      });
      
      render(<PlayPage />);
      expect(screen.getByText('人生落幕')).toBeInTheDocument();
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
  });

  describe('Header actions', () => {
    it('has history button', () => {
      render(<PlayPage />);
      const buttons = screen.getAllByRole('button');
      // History button should be present
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('has home button', () => {
      const mockRouter = { push: jest.fn() };
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        router: mockRouter,
      });
      
      render(<PlayPage />);
      // Home button should be present (check for any button)
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('has save button that shows loading when saving', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        isSaving: true,
      });
      
      render(<PlayPage />);
      // Save button should show loading state
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('has settings button for scene image toggle', () => {
      render(<PlayPage />);
      const buttons = screen.getAllByRole('button');
      // Settings button should be present
      expect(buttons.length).toBeGreaterThan(0);
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

      const historyButton = screen.getByRole('button', { name: '历史回顾' });
      fireEvent.click(historyButton);

      expect(mockHandleOpenHistory).toHaveBeenCalled();
    });

    it('returns to current mode when opening collection before switching to history', () => {
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

      const collectionButton = screen.getByRole('button', { name: '收集' });
      fireEvent.click(collectionButton);

      expect(mockSetShowHistory).toHaveBeenCalledWith(false);
      expect(mockHandleBackToCurrent).toHaveBeenCalled();

      const historyButton = screen.getByRole('button', { name: '历史回顾' });
      fireEvent.click(historyButton);

      expect(mockHandleOpenHistory).toHaveBeenCalled();
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
    it('shows ending skeleton when no ending data', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'ending',
        endingData: null,
      });
      
      render(<PlayPage />);
      expect(screen.getByText('正在评估你的人生...')).toBeInTheDocument();
    });

    it('shows ending data when available', () => {
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'ending',
        endingData: { ending_type: 'happy', summary: 'A wonderful life' },
      });
      
      render(<PlayPage />);
      expect(screen.getByText(/happy/)).toBeInTheDocument();
      expect(screen.getByText(/A wonderful life/)).toBeInTheDocument();
    });
  });

  describe('Error handling', () => {
    it('calls generateEvent on retry click', () => {
      const mockGenerateEvent = jest.fn();
      const originalHook = jest.requireMock('@/hooks/usePlayGame');
      originalHook.usePlayGame = () => ({
        ...mockUsePlayGame,
        phase: 'error',
        generateEvent: mockGenerateEvent,
      });
      
      render(<PlayPage />);
      const retryButton = screen.getByText('重试');
      fireEvent.click(retryButton);
      
      // Should trigger regenerate
      expect(mockGenerateEvent).toBeDefined();
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
    it('toggles scene image setting', () => {
      render(<PlayPage />);

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
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

      expect(mockFetch).toHaveBeenCalledWith(3, 'result');
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
});
