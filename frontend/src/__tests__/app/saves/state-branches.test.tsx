/**
 * Saves Page State Branches Test
 *
 * Tests for the saves page to catch rendering and data handling issues early.
 * Covers: Loading, Error, Empty, and Data states
 */
import React from 'react';
import { act, render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { GameListItem } from '@/lib/types';
import { useGameStore } from '@/stores/useGameStore';
import { useUserStore } from '@/stores/useUserStore';

// Mock next/navigation
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => '/saves',
  useSearchParams: () => new URLSearchParams(),
}));

// Import component after mocks
import SavesPage from '@/app/saves/page';

function setupStore(overrides: { savedGames?: GameListItem[]; isAuthenticated?: boolean; userId?: number } = {}) {
  useGameStore.setState({
    savedGames: overrides.savedGames ?? [],
  });
  useUserStore.setState({
    user: overrides.userId
      ? {
          user_id: overrides.userId,
          public_id: `USER${overrides.userId}`,
          display_name: `User ${overrides.userId}`,
          private_id: `private-${overrides.userId}`,
        }
      : null,
    isAuthenticated: overrides.isAuthenticated ?? true,
  });
}

// Spies at module level for all describe blocks to share
let fetchSavedGamesSpy: jest.SpyInstance;
let deleteGameSpy: jest.SpyInstance;
let loadGameStateSpy: jest.SpyInstance;
let resetCreationSpy: jest.SpyInstance;
let setGameSessionSpy: jest.SpyInstance;

function setupSpies() {
  const store = useGameStore.getState();
  fetchSavedGamesSpy = jest.spyOn(store, 'fetchSavedGames').mockResolvedValue(undefined);
  deleteGameSpy = jest.spyOn(store, 'deleteGame').mockResolvedValue(undefined);
  loadGameStateSpy = jest.spyOn(store, 'loadGameState').mockResolvedValue(undefined);
  resetCreationSpy = jest.spyOn(store, 'resetCreation').mockReturnValue(undefined);
  setGameSessionSpy = jest.spyOn(store, 'setGameSession').mockReturnValue(undefined);
}

function restoreSpies() {
  fetchSavedGamesSpy?.mockRestore();
  deleteGameSpy?.mockRestore();
  loadGameStateSpy?.mockRestore();
  resetCreationSpy?.mockRestore();
  setGameSessionSpy?.mockRestore();
}

describe('SavesPage - 4 State Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockClear();
    setupStore();
    setupSpies();
  });

  afterEach(() => {
    restoreSpies();
  });

  describe('Loading State', () => {
    it('shows a quiet status when loading', () => {
      // Simulate loading by never resolving fetch
      fetchSavedGamesSpy.mockImplementation(() => new Promise(() => {}));

      render(<SavesPage />);

      expect(screen.getByRole('status')).toHaveTextContent('正在整理存档');
      expect(document.querySelector('[class*="animate-spin"]')).toBeNull();
    });

    it('hides the previous user saves while a new user save list is loading', async () => {
      setupStore({
        isAuthenticated: true,
        userId: 1,
        savedGames: [
          {
            game_id: 101,
            player_name: 'PreviousUserSave',
            age: 28,
            week: 0,
            updated_at: '2026-06-10T10:00:00Z',
          },
        ],
      });
      fetchSavedGamesSpy
        .mockResolvedValueOnce(undefined)
        .mockImplementationOnce(() => new Promise(() => {}));

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByText('PreviousUserSave')).toBeInTheDocument();
      });

      act(() => {
        useUserStore.setState({
          user: {
            user_id: 2,
            public_id: 'USER2',
            display_name: 'User 2',
            private_id: 'private-2',
          },
          isAuthenticated: true,
        });
      });

      await waitFor(() => {
        expect(fetchSavedGamesSpy).toHaveBeenCalledTimes(2);
      });
      expect(screen.getByRole('status')).toHaveTextContent('正在整理存档');
      expect(screen.queryByText('PreviousUserSave')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('shows error message when fetch fails', async () => {
      fetchSavedGamesSpy.mockRejectedValue(new Error('Network error'));

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('未能载入存档');
      });
    });

    it('shows retry button when error occurs', async () => {
      fetchSavedGamesSpy.mockRejectedValueOnce(new Error('Network error'));
      fetchSavedGamesSpy.mockResolvedValueOnce(undefined);

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '重试载入存档' })).toBeInTheDocument();
      });
    });

    it('calls fetchSavedGames when clicking retry button', async () => {
      // First fetch fails, subsequent calls hang (to stay in loading state)
      fetchSavedGamesSpy
        .mockRejectedValueOnce(new Error('Network error'))
        .mockImplementationOnce(() => new Promise(() => {}));

      render(<SavesPage />);

      // Wait for error state to show
      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('未能载入存档');
      });

      const retryButton = screen.getByRole('button', { name: '重试载入存档' });
      fireEvent.click(retryButton);

      // Verify that fetchSavedGames was called again (retry)
      expect(fetchSavedGamesSpy).toHaveBeenCalledTimes(2);

      // After clicking retry, should show loading state again
      expect(screen.getByRole('status')).toHaveTextContent('正在整理存档');
    });
  });

  describe('Empty State', () => {
    it('renders empty state when savedGames is empty', async () => {
      // Mock fetch to resolve immediately
      fetchSavedGamesSpy.mockResolvedValue(undefined);
      useGameStore.setState({ savedGames: [] });

      render(<SavesPage />);

      // Should show empty state after fetch completes
      // Use findBy which combines waitFor + getBy
      const emptyMessage = await screen.findByText('还没有存档', {}, { timeout: 3000 });
      expect(emptyMessage).toBeInTheDocument();
    });

    it('shows create new game button when empty', async () => {
      fetchSavedGamesSpy.mockResolvedValue(undefined);
      useGameStore.setState({ savedGames: [] });

      render(<SavesPage />);

      const newGameButton = await screen.findByRole('button', { name: '开始新游戏' }, { timeout: 3000 });
      expect(newGameButton).toBeInTheDocument();
    });

    it('navigates to create page when clicking new game button', async () => {
      fetchSavedGamesSpy.mockResolvedValue(undefined);
      useGameStore.setState({ savedGames: [] });

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '开始新游戏' })).toBeInTheDocument();
      });

      const newGameButton = screen.getByRole('button', { name: '开始新游戏' });
      fireEvent.click(newGameButton);

      expect(resetCreationSpy).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith('/create');
    });
  });

  describe('Data State', () => {
    it('shows save list when games exist', async () => {
      fetchSavedGamesSpy.mockResolvedValue(undefined);
      useGameStore.setState({ savedGames: [
        { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
      ] });

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByText('TestPlayer')).toBeInTheDocument();
      });
    });

    it('displays player age and week info', async () => {
      fetchSavedGamesSpy.mockResolvedValue(undefined);
      useGameStore.setState({ savedGames: [
        { game_id: 1, player_name: 'TestPlayer', age: 25, week: 10, updated_at: '2024-01-15T10:30:00Z' },
      ] });

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByText(/25岁/)).toBeInTheDocument();
        expect(screen.getByText(/第11周/)).toBeInTheDocument();
      });
    });

    it('shows new character badge for week 0 saves', async () => {
      fetchSavedGamesSpy.mockResolvedValue(undefined);
      useGameStore.setState({ savedGames: [
        { game_id: 1, player_name: 'NewPlayer', age: 18, week: 0, updated_at: '2024-01-15T10:30:00Z' },
      ] });

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByText('新角色')).toBeInTheDocument();
      });
    });
  });
});

describe('SavesPage - Data Filtering and Sorting', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupStore();
    setupSpies();
  });

  it('shows all games including empty player_name as fallback', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'ValidPlayer', age: 20, week: 1, updated_at: '2024-01-15T10:30:00Z' },
      { game_id: 2, player_name: '   ', age: 20, week: 1, updated_at: '2024-01-15T10:30:00Z' },
      { game_id: 3, player_name: '', age: 20, week: 1, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('ValidPlayer')).toBeInTheDocument();
    });

    // All 3 saves should be rendered; empty names show as "未知角色"
    const saveCards = screen.getAllByText(/岁.*第.*周/);
    expect(saveCards).toHaveLength(3);
    expect(screen.getAllByText('未知角色')).toHaveLength(2);
  });

  it('sorts games by updated_at descending (newest first)', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'OldSave', age: 20, week: 1, updated_at: '2024-01-10T10:00:00Z' },
      { game_id: 2, player_name: 'NewSave', age: 21, week: 5, updated_at: '2024-01-15T14:30:00Z' },
      { game_id: 3, player_name: 'MiddleSave', age: 20, week: 3, updated_at: '2024-01-12T08:00:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('NewSave')).toBeInTheDocument();
    });

    // Get all player name elements - they should be in order: NewSave, MiddleSave, OldSave
    const playerNames = screen.getAllByText(/Save$/);
    expect(playerNames[0]).toHaveTextContent('NewSave');
    expect(playerNames[1]).toHaveTextContent('MiddleSave');
    expect(playerNames[2]).toHaveTextContent('OldSave');
  });

  it('handles null updated_at gracefully', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'NoDate', age: 20, week: 1 },
      { game_id: 2, player_name: 'WithDate', age: 21, week: 5, updated_at: '2024-01-15T14:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('NoDate')).toBeInTheDocument();
      expect(screen.getByText('WithDate')).toBeInTheDocument();
    });
  });
});

describe('SavesPage - Interaction Handling', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupStore();
    setupSpies();
  });

  it('loads game when clicking continue button', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    loadGameStateSpy.mockResolvedValue(undefined);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('继续')).toBeInTheDocument();
    });

    const continueButton = screen.getByText('继续').closest('button');
    if (continueButton) {
      fireEvent.click(continueButton);
    }

    await waitFor(() => {
      expect(loadGameStateSpy).toHaveBeenCalledWith(1);
      expect(setGameSessionSpy).toHaveBeenCalledWith(1, 'session_1');
      expect(mockPush).toHaveBeenCalledWith('/play');
    });
  });

  it('shows loading state on continue button while loading game', async () => {
    // Create a promise that we can control
    let resolveLoad: () => void;
    const loadPromise = new Promise<void>((resolve) => {
      resolveLoad = resolve;
    });

    fetchSavedGamesSpy.mockResolvedValue(undefined);
    loadGameStateSpy.mockReturnValue(loadPromise);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('继续')).toBeInTheDocument();
    });

    const continueButton = screen.getByText('继续').closest('button');
    expect(continueButton).not.toBeDisabled();

    if (continueButton) {
      fireEvent.click(continueButton);
    }

    // After clicking, the button should be disabled (loading state)
    await waitFor(() => {
      expect(continueButton).toBeDisabled();
    });

    // Resolve the promise
    resolveLoad!();

    // After resolving, navigation should happen
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/play');
    });
  });

  it('opens delete confirmation dialog when clicking delete button', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('TestPlayer')).toBeInTheDocument();
    });

    // Find delete button by aria-label or by looking for the trash icon
    const allButtons = screen.getAllByRole('button');
    // The delete button is the one with trash icon (variant="ghost" with just an icon)
    const deleteButton = allButtons.find(btn => {
      const hasSvg = btn.querySelector('svg');
      const text = btn.textContent || '';
      // Delete button has SVG but no text content (just icon)
      return hasSvg && !text.includes('继续') && !text.includes('返回') && !text.includes('开始新游戏');
    });

    expect(deleteButton).toBeDefined();
    if (deleteButton) {
      fireEvent.click(deleteButton);
    }

    // Dialog should appear - look for dialog title in the document
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Check dialog content
    expect(screen.getByRole('heading', { name: '删除存档“TestPlayer”？' })).toBeInTheDocument();
    expect(screen.getByText(/删除后无法恢复/)).toBeInTheDocument();
  });

  it('closes delete dialog when clicking cancel', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('TestPlayer')).toBeInTheDocument();
    });

    // Open delete dialog
    const allButtons = screen.getAllByRole('button');
    const deleteButton = allButtons.find(btn => {
      const hasSvg = btn.querySelector('svg');
      const text = btn.textContent || '';
      return hasSvg && !text.includes('继续') && !text.includes('返回') && !text.includes('开始新游戏');
    });

    if (deleteButton) {
      fireEvent.click(deleteButton);
    }

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: '取消' });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    expect(deleteGameSpy).not.toHaveBeenCalled();
  });

  it('deletes game when confirming delete', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    deleteGameSpy.mockResolvedValue(undefined);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('TestPlayer')).toBeInTheDocument();
    });

    // Open delete dialog
    const allButtons = screen.getAllByRole('button');
    const deleteButton = allButtons.find(btn => {
      const hasSvg = btn.querySelector('svg');
      const text = btn.textContent || '';
      return hasSvg && !text.includes('继续') && !text.includes('返回') && !text.includes('开始新游戏');
    });

    if (deleteButton) {
      fireEvent.click(deleteButton);
    }

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Click delete
    const confirmDeleteButton = screen.getByRole('button', { name: /^删除$/ });
    fireEvent.click(confirmDeleteButton);

    await waitFor(() => {
      expect(deleteGameSpy).toHaveBeenCalledWith(1);
    });
  });

  it('shows loading state on delete button while deleting', async () => {
    let resolveDelete: () => void;
    const deletePromise = new Promise<void>((resolve) => {
      resolveDelete = resolve;
    });

    fetchSavedGamesSpy.mockResolvedValue(undefined);
    deleteGameSpy.mockReturnValue(deletePromise);
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('TestPlayer')).toBeInTheDocument();
    });

    // Open delete dialog
    const allButtons = screen.getAllByRole('button');
    const deleteButton = allButtons.find(btn => {
      const hasSvg = btn.querySelector('svg');
      const text = btn.textContent || '';
      return hasSvg && !text.includes('继续') && !text.includes('返回') && !text.includes('开始新游戏');
    });

    if (deleteButton) {
      fireEvent.click(deleteButton);
    }

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Click delete
    const confirmDeleteButton = screen.getByRole('button', { name: /^删除$/ });
    fireEvent.click(confirmDeleteButton);

    // Should show loading state
    await waitFor(() => {
      const deleteBtn = screen.getByRole('button', { name: '正在删除' });
      expect(deleteBtn).toBeDisabled();
    });

    resolveDelete!();
  });
});

describe('SavesPage - Unauthenticated State', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupStore({ isAuthenticated: false });
    setupSpies();
  });

  it('shows empty state when not authenticated', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('还没有存档')).toBeInTheDocument();
    });

    // Should not call fetchSavedGames when not authenticated
    expect(fetchSavedGamesSpy).not.toHaveBeenCalled();
  });

  it('does not render stale savedGames from a previous user when not authenticated', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    useGameStore.setState({
      savedGames: [
        {
          game_id: 88,
          player_name: 'PreviousUserSave',
          age: 31,
          week: 12,
          updated_at: '2026-06-09T10:30:00Z',
        },
      ],
    });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('还没有存档')).toBeInTheDocument();
    });

    expect(screen.queryByText('PreviousUserSave')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /继续/ })).not.toBeInTheDocument();
    expect(fetchSavedGamesSpy).not.toHaveBeenCalled();
    expect(loadGameStateSpy).not.toHaveBeenCalled();
    expect(deleteGameSpy).not.toHaveBeenCalled();
  });
});

describe('SavesPage - Navigation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupStore();
    setupSpies();
  });

  it('navigates to home when clicking return button', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('返回')).toBeInTheDocument();
    });

    const returnButton = screen.getByText('返回').closest('button');
    if (returnButton) {
      fireEvent.click(returnButton);
    }

    expect(mockPush).toHaveBeenCalledWith('/');
  });
});

describe('SavesPage - Error Handling', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupStore();
    setupSpies();
  });

  it('shows error toast when load game fails', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    loadGameStateSpy.mockRejectedValue(new Error('Load failed'));
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('继续')).toBeInTheDocument();
    });

    const continueButton = screen.getByText('继续').closest('button');
    if (continueButton) {
      fireEvent.click(continueButton);
    }

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('无法打开存档“TestPlayer”');
    });
  });

  it('shows error toast when delete game fails', async () => {
    fetchSavedGamesSpy.mockResolvedValue(undefined);
    deleteGameSpy.mockRejectedValue(new Error('Delete failed'));
    useGameStore.setState({ savedGames: [
      { game_id: 1, player_name: 'TestPlayer', age: 20, week: 5, updated_at: '2024-01-15T10:30:00Z' },
    ] });

    render(<SavesPage />);

    await waitFor(() => {
      expect(screen.getByText('TestPlayer')).toBeInTheDocument();
    });

    // Open delete dialog
    const allButtons = screen.getAllByRole('button');
    const deleteButton = allButtons.find(btn => {
      const hasSvg = btn.querySelector('svg');
      const text = btn.textContent || '';
      return hasSvg && !text.includes('继续') && !text.includes('返回') && !text.includes('开始新游戏');
    });

    if (deleteButton) {
      fireEvent.click(deleteButton);
    }

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Click delete
    const confirmDeleteButton = screen.getByRole('button', { name: /^删除$/ });
    fireEvent.click(confirmDeleteButton);

    await waitFor(() => {
      expect(within(screen.getByRole('dialog')).getByRole('alert')).toHaveTextContent(
        '未能删除存档“TestPlayer”',
      );
    });
  });
});

describe('SavesPage - story101 recovery and destructive actions', () => {
  const save: GameListItem = {
    game_id: 17,
    player_name: '林望舒',
    age: 28,
    week: 6,
    updated_at: '2026-08-09T10:00:00Z',
  };
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockClear();
    setupStore({ savedGames: [save], isAuthenticated: true, userId: 7 });
    setupSpies();
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    restoreSpies();
  });

  async function openDeleteDialog() {
    const user = userEvent.setup();
    render(<SavesPage />);
    await user.click(await screen.findByRole('button', {
      name: '删除存档“林望舒”（存档 17）',
    }));
    return { user, dialog: await screen.findByRole('dialog') };
  }

  it('keeps a second failed fetch retry in the error state instead of showing the empty state', async () => {
    fetchSavedGamesSpy
      .mockRejectedValueOnce(new Error('first failure'))
      .mockRejectedValueOnce(new Error('second failure'));
    useGameStore.setState({ savedGames: [] });

    render(<SavesPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('未能载入存档');
    fireEvent.click(screen.getByRole('button', { name: '重试载入存档' }));

    await waitFor(() => expect(fetchSavedGamesSpy).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('alert')).toHaveTextContent('未能载入存档');
    expect(screen.queryByText('还没有存档')).not.toBeInTheDocument();
  });

  it('names the delete target and explicitly focuses cancel when the dialog opens', async () => {
    const { dialog } = await openDeleteDialog();

    expect(within(dialog).getByRole('heading', { name: '删除存档“林望舒”？' })).toBeInTheDocument();
    expect(within(dialog).getByText(/删除后无法恢复/)).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: '取消' })).toHaveFocus();
    within(dialog).getAllByRole('button').forEach((button) => {
      expect(button).toHaveAttribute('data-size', 'touch');
    });
  });

  it('announces deletion progress, blocks closing, and submits only once while busy', async () => {
    let resolveDelete: () => void = () => {};
    deleteGameSpy.mockImplementation(() => new Promise<void>((resolve) => {
      resolveDelete = resolve;
    }));
    const { user, dialog } = await openDeleteDialog();

    const deleteButton = within(dialog).getByRole('button', { name: '删除' });
    fireEvent.click(deleteButton);
    fireEvent.click(deleteButton);

    await waitFor(() => expect(dialog).toHaveAttribute('aria-busy', 'true'));
    expect(within(dialog).getByRole('button', { name: '正在删除' })).toBeDisabled();
    expect(deleteGameSpy).toHaveBeenCalledTimes(1);
    await user.keyboard('{Escape}');
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    resolveDelete();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('keeps a failed deletion in the dialog with a target-specific alert and retry action', async () => {
    deleteGameSpy.mockRejectedValueOnce(new Error('delete failed'));
    const { user, dialog } = await openDeleteDialog();

    await user.click(within(dialog).getByRole('button', { name: '删除' }));

    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent('未能删除存档“林望舒”');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: '删除' })).toBeEnabled();
  });

  it('announces a successful deletion with the target name', async () => {
    const { user, dialog } = await openDeleteDialog();

    await user.click(within(dialog).getByRole('button', { name: '删除' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByRole('status')).toHaveTextContent('已删除存档“林望舒”');
    expect(deleteGameSpy).toHaveBeenCalledWith(17);
  });
});
