/**
 * Tests for EndingPage component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EndingPage from '@/app/ending/page';
import { useGameStore } from '@/stores/useGameStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
  }),
}));

const STORE_METHODS = ['resetGame', 'loadGameState', 'fetchSavedGames'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useGameStore.setState({
    gameId: 123,
    playerState: { player_name: 'TestHero' },
  });
}

describe('EndingPage', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
      ending_name: '圆满人生',
      summary: 'You lived a great life.',
      ending_type: 'happy',
      achievements: { list: ['Achievement 1', 'Achievement 2'] },
      final_stats: {
        energy: 80,
        mood: 90,
        knowledge: 70,
        wealth: 100000,
        relationships: { '李明': 85, '王华': 70 },
      },
    }));
  });

  afterEach(() => {
    storeSpy.restore();
  });

  describe('Loading state', () => {
    it('shows loading skeleton initially', () => {
      render(<EndingPage />);
      expect(screen.getByText('正在回顾你的一生...')).toBeInTheDocument();
    });
  });

  describe('With ending data', () => {
    it('shows ending title', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('圆满人生')).toBeInTheDocument();
      });
    });

    it('shows player name in subtitle', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText(/TestHero的人生旅程到此结束/)).toBeInTheDocument();
      });
    });

    it('shows ending story', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('You lived a great life.')).toBeInTheDocument();
      });
    });

    it('hides final numeric resource stats', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('圆满人生')).toBeInTheDocument();
      });

      expect(screen.queryByText('最终状态')).not.toBeInTheDocument();
      expect(screen.queryByText('精力')).not.toBeInTheDocument();
      expect(screen.queryByText('情绪')).not.toBeInTheDocument();
      expect(screen.queryByText('学识')).not.toBeInTheDocument();
      expect(screen.queryByText('财富')).not.toBeInTheDocument();
    });

    it('shows relationships', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('人际关系')).toBeInTheDocument();
        expect(screen.getByText('李明')).toBeInTheDocument();
        expect(screen.getByText('85/100')).toBeInTheDocument();
      });
    });

    it('shows achievements', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('人生成就')).toBeInTheDocument();
        expect(screen.getByText('Achievement 1')).toBeInTheDocument();
        expect(screen.getByText('Achievement 2')).toBeInTheDocument();
      });
    });
  });

  describe('Navigation buttons', () => {
    it('shows home button', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('返回首页')).toBeInTheDocument();
      });
    });

    it('shows new game button', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('开始新人生')).toBeInTheDocument();
      });
    });

    it('navigates home on home button click', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        const homeButton = screen.getByText('返回首页');
        fireEvent.click(homeButton);
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    it('resets game and navigates to create on new game', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        const newGameButton = screen.getByText('开始新人生');
        fireEvent.click(newGameButton);
        expect(storeSpy.spies.resetGame).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith('/create');
      });
    });
  });

  describe('No gameId', () => {
    it('returns null when no gameId', () => {
      useGameStore.setState({ gameId: null });
      const { container } = render(<EndingPage />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('API error', () => {
    it('handles API error gracefully', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'API Error' }, 400));
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText(/TestHero的人生旅程到此结束/)).toBeInTheDocument();
      });
    });
  });

  describe('Partial ending data', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        ending_name: 'Simple Ending',
        summary: '',
        final_stats: null,
        achievements: null,
      }));
    });

    it('renders without final stats', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('Simple Ending')).toBeInTheDocument();
      });
      expect(screen.queryByText('最终状态')).not.toBeInTheDocument();
    });

    it('renders without achievements', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.queryByText('人生成就')).not.toBeInTheDocument();
      });
    });
  });
});
