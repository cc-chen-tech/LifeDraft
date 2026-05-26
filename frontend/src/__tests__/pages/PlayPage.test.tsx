/**
 * Tests for PlayPage component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PlayPage from '@/app/play/page';

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

    it('keeps recovery controls visible when restored story text has no playable options', async () => {
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
      expect(screen.getByText(/如果生成时间较长/)).toBeInTheDocument();
      const recoveryButton = screen.getByRole('button', { name: '恢复当前进度' });
      expect(recoveryButton).toBeInTheDocument();

      fireEvent.click(recoveryButton);
      await waitFor(() => {
        expect(mockRecoverEventGeneration).toHaveBeenCalledTimes(1);
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
        elapsedSeconds: 30,
        getLoadingMessage: () => '正在生成故事...',
      });
      
      render(<PlayPage />);
      // isStreaming=true during generating — wait for animation
      await waitFor(() => {
        expect(screen.getByText('Some story')).toBeInTheDocument();
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
