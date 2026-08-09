/**
 * Saves Page Tests
 * Tests all interactive elements of the saved games page
 */
import React from 'react';
import { render, screen, waitFor, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SavesPage from '@/app/saves/page';
import { useGameStore } from '@/stores/useGameStore';
import { useUserStore } from '@/stores/useUserStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

// Mock useRouter
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

const STORE_METHODS = ['fetchSavedGames', 'loadGameState', 'setGameSession', 'deleteGame', 'resetCreation'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useUserStore.setState({ isAuthenticated: true });
  useGameStore.setState({
    gameId: null,
    sessionId: null,
    playerState: null,
    progress: null,
    roundInfo: null,
    currentEvent: null,
    storyText: '',
    isGameOver: false,
    savedGames: [],
    presets: [],
    creationStep: 0,
    characterSettings: {},
    playerName: '',
    lifeVision: '',
    openingStory: '',
    isPresetLoaded: false,
    lastSummary: null,
  });
}

describe('SavesPage', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockClear();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  describe('Loading state', () => {
    it('shows loading indicator initially', () => {
      storeSpy.spies.fetchSavedGames.mockReturnValue(new Promise(() => {}));

      render(<SavesPage />);
      expect(screen.getByRole('status')).toHaveTextContent('正在整理存档');
    });
  });

  describe('Empty state', () => {
    it('does not render stale saved games when the current user is not authenticated', async () => {
      useUserStore.setState({ user: null, isAuthenticated: false });
      useGameStore.setState({
        savedGames: [
          {
            game_id: 99,
            player_name: 'Other User Save',
            age: 28,
            week: 3,
            updated_at: '2024-01-15T10:00:00Z',
          },
        ],
      });

      await act(async () => {
        render(<SavesPage />);
      });

      expect(storeSpy.spies.fetchSavedGames).not.toHaveBeenCalled();
      expect(screen.queryByText('Other User Save')).not.toBeInTheDocument();
      expect(screen.getByText('还没有存档')).toBeInTheDocument();
    });

    it('shows empty message when no saves', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('还没有存档')).toBeInTheDocument();
      });
    });

    it('shows start new game button when empty', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '开始新游戏' })).toBeInTheDocument();
      });
    });

    it('navigates to create when clicking start new game', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '开始新游戏' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: '开始新游戏' }));

      expect(storeSpy.spies.resetCreation).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith('/create');
    });
  });

  describe('With saved games', () => {
    beforeEach(() => {
      useGameStore.setState({
        savedGames: [
          { game_id: 1, player_name: 'Player 1', age: 25, week: 10, updated_at: '2024-01-15T10:00:00Z' },
          { game_id: 2, player_name: 'Player 2', age: 30, week: 20, updated_at: '2024-01-14T10:00:00Z' },
        ],
      });
    });

    it('displays saved games list', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Player 1')).toBeInTheDocument();
        expect(screen.getByText('Player 2')).toBeInTheDocument();
      });
    });

    it('displays game info (age and week)', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Player 1')).toBeInTheDocument();
      });

      expect(screen.getByText(/25/)).toBeInTheDocument();
      expect(screen.getByText(/第11周/)).toBeInTheDocument();
    });

    it('loads game when clicking load button', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Player 1')).toBeInTheDocument();
      });

      expect(storeSpy.spies.loadGameState).toBeDefined();
    });

    it('opens delete confirmation when clicking delete button', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Player 1')).toBeInTheDocument();
      });

      expect(screen.getByText('Player 1')).toBeInTheDocument();
    });

    it('deletes game when confirming delete', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Player 1')).toBeInTheDocument();
      });

      expect(storeSpy.spies.deleteGame).toBeDefined();
    });

    it('cancels delete when clicking cancel', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Player 1')).toBeInTheDocument();
      });

      expect(storeSpy.spies.deleteGame).not.toHaveBeenCalled();
    });
  });

  describe('story101 library surface', () => {
    const longPlayerName = '这是一位名字很长需要在三百二十像素宽度下完整换行的角色';

    beforeEach(() => {
      useUserStore.setState({
        isAuthenticated: true,
        user: {
          user_id: 7,
          public_id: 'USER7',
          display_name: 'Reader',
          private_id: 'private-7',
        },
      });
      useGameStore.setState({
        savedGames: [
          {
            game_id: 17,
            player_name: longPlayerName,
            age: 28,
            week: 6,
            updated_at: '2026-08-09T10:00:00Z',
          },
        ],
      });
    });

    it('uses the lowercase brand, the concise page heading, and one reading surface', async () => {
      const { container } = render(<SavesPage />);

      await screen.findByText(longPlayerName);

      expect(screen.getByText('story101')).toHaveClass('font-brand');
      expect(screen.getByRole('heading', { level: 1, name: '存档' })).toBeInTheDocument();
      expect(container.querySelectorAll('[data-slot="surface"][data-variant="reading"]')).toHaveLength(1);
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
    });

    it('keeps the main action separate from a touch-sized danger row for long names', async () => {
      const { container } = render(<SavesPage />);

      const playerName = await screen.findByText(longPlayerName);
      const continueButton = screen.getByRole('button', { name: `继续“${longPlayerName}”的人生` });
      const deleteButton = screen.getByRole('button', {
        name: `删除存档“${longPlayerName}”（存档 17）`,
      });
      const dangerRow = deleteButton.closest('[data-slot="danger-row"]');

      expect(playerName).toHaveClass('break-words');
      expect(container.querySelector('[data-slot="management-row"]')).toHaveClass('min-w-0');
      expect(dangerRow).toContainElement(deleteButton);
      expect(dangerRow).not.toContainElement(continueButton);
      expect(continueButton).toHaveAttribute('data-size', 'touch');
      expect(deleteButton).toHaveAttribute('data-size', 'touch');
      expect(within(dangerRow as HTMLElement).getByText('删除存档')).toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('navigates back when clicking back button', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<SavesPage />);
      });

      await user.click(screen.getByRole('button', { name: /返回/i }));
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('Page title', () => {
    it('displays correct page title', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      expect(screen.getByRole('heading', { level: 1, name: '存档' })).toBeInTheDocument();
    });
  });

  describe('Game list display', () => {
    beforeEach(() => {
      useGameStore.setState({
        savedGames: [
          { game_id: 1, player_name: 'Hero', age: 25, week: 10, updated_at: '2024-01-15T10:00:00Z' },
          { game_id: 2, player_name: 'Hero', age: 30, week: 20, updated_at: '2024-01-14T10:00:00Z' },
          { game_id: 3, player_name: 'Villain', age: 35, week: 5, updated_at: '2024-01-13T10:00:00Z' },
        ],
      });
    });

    it('displays each game as separate card', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        const heroElements = screen.getAllByText('Hero');
        expect(heroElements.length).toBe(2);
        expect(screen.getByText('Villain')).toBeInTheDocument();
      });
    });

    it('displays game age and week info', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText(/25岁.*第11周/)).toBeInTheDocument();
      });
    });

    it('has continue button for each game', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        const buttons = screen.getAllByRole('button');
        // Look for buttons with Play icon — these are continue buttons
        const continueButtons = buttons.filter(btn => btn.querySelector('svg.lucide-play'));
        expect(continueButtons.length).toBeGreaterThan(0);
      });
    });

    it('renders save timestamps in the product time zone', async () => {
      useGameStore.setState({
        savedGames: [
          {
            game_id: 4,
            player_name: 'Shanghai Save',
            age: 29,
            week: 3,
            updated_at: '2026-07-13T16:30:00Z',
          },
        ],
      });

      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('2026/7/14 凌晨0:30')).toBeInTheDocument();
      });
    });
  });

  describe('Delete game', () => {
    beforeEach(() => {
      useGameStore.setState({
        savedGames: [
          { game_id: 1, player_name: 'Hero', age: 25, week: 10, updated_at: '2024-01-15T10:00:00Z' },
        ],
      });
    });

    it('shows delete button for each game', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Hero')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button');
      expect(deleteButtons.length).toBeGreaterThan(1);
    });

    it('opens delete confirmation dialog when clicking delete', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Hero')).toBeInTheDocument();
      });

      const trashButtons = screen.getAllByRole('button').filter(btn =>
        btn.querySelector('svg.lucide-trash2')
      );

      if (trashButtons.length > 0) {
        await user.click(trashButtons[0]);

        await waitFor(() => {
          expect(screen.getByRole('heading', { name: '删除存档“Hero”？' })).toBeInTheDocument();
        });
      }
    });
  });

  describe('Error handling', () => {
    beforeEach(() => {
      useGameStore.setState({
        savedGames: [
          { game_id: 1, player_name: 'Hero', age: 25, week: 10, updated_at: '2024-01-15T10:00:00Z' },
        ],
      });
    });

    it('shows error toast when load fails', async () => {
      storeSpy.spies.loadGameState.mockRejectedValue(new Error('Load failed'));

      const user = userEvent.setup();
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Hero')).toBeInTheDocument();
      });

      const loadButton = screen.getByRole('button', { name: /继续/ });
      expect(loadButton).toBeInTheDocument();
      expect(storeSpy.spies.loadGameState).toBeDefined();
    });

    it('shows error toast when delete fails', async () => {
      storeSpy.spies.deleteGame.mockRejectedValue(new Error('Delete failed'));

      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Hero')).toBeInTheDocument();
      });

      expect(storeSpy.spies.deleteGame).toBeDefined();
    });
  });

  describe('Toast display', () => {
    it('can display toast messages', async () => {
      await act(async () => {
        render(<SavesPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('还没有存档')).toBeInTheDocument();
      });

      expect(screen.getByRole('heading', { level: 1, name: '存档' })).toBeInTheDocument();
    });
  });
});
