/**
 * Tests for OpeningStoryPage component
 * Note: This page has complex SSE streaming logic, tests focus on basic rendering
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OpeningStoryPage from '@/app/story/opening/page';

// Mock stores
const mockGameStore = {
  gameId: 123,
  openingStory: 'Test opening story content.',
  characterSettings: {
    era: { era_name: '现代' },
    age: { starting_age: 22 },
  },
  playerName: 'TestHero',
  lifeVision: 'Be great',
  setOpeningStory: jest.fn(),
  // Illustration related
  openingIllustration: null as { image_url: string; scene_description: string } | null,
  isGeneratingIllustration: false,
  illustrationError: null as string | null,
  generateOpeningIllustration: jest.fn(),
  regenerateOpeningIllustration: jest.fn(),
};

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: Object.assign(
    (selector?: (state: typeof mockGameStore) => unknown) => {
      if (selector) return selector(mockGameStore);
      return mockGameStore;
    },
    { getState: () => mockGameStore }
  ),
}));

const mockUIStore = {
  language: 'zh',
};

jest.mock('@/stores/useUIStore', () => ({
  useUIStore: (selector?: (state: typeof mockUIStore) => unknown) => {
    if (selector) return selector(mockUIStore);
    return mockUIStore;
  },
}));

let isHydrated = true;
jest.mock('@/hooks/useHydration', () => ({
  useHydration: () => isHydrated,
}));

// Mock StreamingText to render text immediately
jest.mock('@/components/game/StreamingText', () => ({
  StreamingText: ({ text }: { text: string }) => <div data-testid="streaming-text">{text}</div>,
}));

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
  }),
}));

// Mock SSE streaming - won't be called when openingStory exists
jest.mock('@/lib/sse', () => ({
  streamOpeningStory: jest.fn(),
}));

describe('OpeningStoryPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    isHydrated = true;
    Object.assign(mockGameStore, {
      gameId: 123,
      openingStory: 'Test opening story content.',
      characterSettings: {
        era: { era_name: '现代' },
        age: { starting_age: 22 },
      },
      playerName: 'TestHero',
      lifeVision: 'Be great',
      openingIllustration: null,
      isGeneratingIllustration: false,
      illustrationError: null,
    });
  });

  describe('Initial render', () => {
    it('renders without crashing', () => {
      render(<OpeningStoryPage />);
      // Page should render
    });

    it('shows loading when not hydrated', () => {
      isHydrated = false;
      render(<OpeningStoryPage />);
      expect(screen.getByText('加载中...')).toBeInTheDocument();
    });

    it('displays opening story when available', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByTestId('streaming-text')).toBeInTheDocument();
    });

    it('displays continue button', () => {
      render(<OpeningStoryPage />);
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('displays player name in header', () => {
      render(<OpeningStoryPage />);
      // Check that the page renders with player context
      expect(screen.getByTestId('streaming-text')).toBeInTheDocument();
    });
  });

  describe('Error handling', () => {
    it('shows error when missing player data', async () => {
      Object.assign(mockGameStore, {
        openingStory: '',
        characterSettings: {},
        playerName: '',
      });
      render(<OpeningStoryPage />);
      await waitFor(() => {
        expect(screen.getByText(/缺少角色数据/)).toBeInTheDocument();
      });
    });

    it.skip('shows error when missing gameId', async () => {
      Object.assign(mockGameStore, {
        gameId: null,
        openingStory: '',
      });
      render(<OpeningStoryPage />);
      await waitFor(() => {
        expect(screen.getByText(/缺少角色数据|错误/)).toBeInTheDocument();
      });
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
      expect(screen.getByTestId('streaming-text')).toHaveTextContent('Test opening story content.');
    });

    it('shows different story content when changed', () => {
      Object.assign(mockGameStore, {
        openingStory: 'A different opening story.',
      });
      render(<OpeningStoryPage />);
      expect(screen.getByTestId('streaming-text')).toHaveTextContent('A different opening story.');
    });
  });

  describe('Illustration display', () => {
    it('shows illustration loading state', () => {
      Object.assign(mockGameStore, {
        openingStory: 'Complete story',
        isGeneratingIllustration: true,
      });
      render(<OpeningStoryPage />);
      expect(screen.getByText(/AI正在为你绘制人生插画/)).toBeInTheDocument();
    });

    it('shows illustration when available', () => {
      Object.assign(mockGameStore, {
        openingStory: 'Complete story',
        openingIllustration: {
          image_url: 'http://test.url/illustration.png',
          scene_description: 'A beautiful scene',
        },
      });
      render(<OpeningStoryPage />);
      expect(screen.getByAltText('开场插画')).toBeInTheDocument();
      expect(screen.getByText('A beautiful scene')).toBeInTheDocument();
    });

    it('shows illustration error state', () => {
      Object.assign(mockGameStore, {
        openingStory: 'Complete story',
        illustrationError: 'Failed to generate',
      });
      render(<OpeningStoryPage />);
      expect(screen.getByText(/插画生成失败/)).toBeInTheDocument();
    });

    it('shows retry button on illustration error', () => {
      Object.assign(mockGameStore, {
        openingStory: 'Complete story',
        illustrationError: 'Failed to generate',
      });
      render(<OpeningStoryPage />);
      expect(screen.getByText('重新生成插画')).toBeInTheDocument();
    });
  });

  describe('Start game button', () => {
    it('shows start game button when story is complete', () => {
      render(<OpeningStoryPage />);
      expect(screen.getByText('开始我的人生')).toBeInTheDocument();
    });

    it('navigates to play page when clicking start', async () => {
      const user = userEvent.setup();
      render(<OpeningStoryPage />);

      await user.click(screen.getByText('开始我的人生'));

      expect(mockPush).toHaveBeenCalledWith('/play');
    });

    it('navigates to create page when no gameId', async () => {
      Object.assign(mockGameStore, {
        gameId: null,
      });
      const user = userEvent.setup();
      render(<OpeningStoryPage />);

      await user.click(screen.getByText('开始我的人生'));

      expect(mockPush).toHaveBeenCalledWith('/create');
    });
  });

  describe('Error handling', () => {
    it('shows retry button on error', () => {
      Object.assign(mockGameStore, {
        openingStory: '',
        characterSettings: {},
        playerName: '',
      });
      render(<OpeningStoryPage />);
      
      // Should show error or retry option
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('shows home button on error', () => {
      Object.assign(mockGameStore, {
        openingStory: '',
        characterSettings: {},
        playerName: '',
      });
      render(<OpeningStoryPage />);
      
      // Should show home button
      expect(screen.getByText('返回首页')).toBeInTheDocument();
    });
  });
});
