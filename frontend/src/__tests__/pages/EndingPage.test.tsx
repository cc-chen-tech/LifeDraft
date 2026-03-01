/**
 * Tests for EndingPage component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EndingPage from '@/app/ending/page';

// Mock stores
const mockGameStore = {
  gameId: 123,
  playerState: {
    player_name: 'TestHero',
  },
  resetGame: jest.fn(),
};

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: (selector?: (state: typeof mockGameStore) => unknown) => {
    if (selector) return selector(mockGameStore);
    return mockGameStore;
  },
}));

jest.mock('@/hooks/useHydration', () => ({
  useHydration: () => true,
}));

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
  }),
}));

// Mock API
const mockGetEnding = jest.fn();
jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    gameplay: {
      getEnding: (...args: unknown[]) => mockGetEnding(...args),
    },
  },
}));

describe('EndingPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetEnding.mockResolvedValue({
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
    });
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

    it('shows final stats', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('最终状态')).toBeInTheDocument();
        expect(screen.getByText('80')).toBeInTheDocument(); // energy
        expect(screen.getByText('90')).toBeInTheDocument(); // mood
      });
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
        expect(mockGameStore.resetGame).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith('/create');
      });
    });
  });

  describe('No gameId', () => {
    beforeEach(() => {
      Object.assign(mockGameStore, { gameId: null });
    });

    afterEach(() => {
      Object.assign(mockGameStore, { gameId: 123 });
    });

    it('returns null when no gameId', () => {
      const { container } = render(<EndingPage />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('API error', () => {
    beforeEach(() => {
      mockGetEnding.mockRejectedValue(new Error('API Error'));
    });

    it('handles API error gracefully', async () => {
      render(<EndingPage />);
      // Should still render basic structure
      await waitFor(() => {
        expect(screen.getByText(/TestHero的人生旅程到此结束/)).toBeInTheDocument();
      });
    });
  });

  describe('Partial ending data', () => {
    beforeEach(() => {
      mockGetEnding.mockResolvedValue({
        ending_name: 'Simple Ending',
        summary: '',
        final_stats: null,
        achievements: null,
      });
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
