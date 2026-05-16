/**
 * Saves Page State Branches Test
 *
 * Tests for the saves page to catch rendering and data handling issues early.
 * Covers: Loading, Error, Empty, and Data states
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
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

function setupStore(overrides: { savedGames?: GameListItem[]; isAuthenticated?: boolean } = {}) {
  useGameStore.setState({
    savedGames: overrides.savedGames ?? [],
  });
  useUserStore.setState({
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
    it('shows spinner when loading', () => {
      // Simulate loading by never resolving fetch
      fetchSavedGamesSpy.mockImplementation(() => new Promise(() => {}));

      render(<SavesPage />);

      expect(screen.getByText('加载中...')).toBeInTheDocument();
      expect(document.querySelector('[class*="animate-spin"]')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('shows error message when fetch fails', async () => {
      fetchSavedGamesSpy.mockRejectedValue(new Error('Network error'));

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByText('加载存档失败，请刷新页面重试')).toBeInTheDocument();
      });
    });

    it('shows retry button when error occurs', async () => {
      fetchSavedGamesSpy.mockRejectedValueOnce(new Error('Network error'));
      fetchSavedGamesSpy.mockResolvedValueOnce(undefined);

      render(<SavesPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
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
        expect(screen.getByText('加载存档失败，请刷新页面重试')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: '重试' });
      fireEvent.click(retryButton);

      // Verify that fetchSavedGames was called again (retry)
      expect(fetchSavedGamesSpy).toHaveBeenCalledTimes(2);

      // After clicking retry, should show loading state again
      expect(screen.getByText('加载中...')).toBeInTheDocument();
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
      const emptyMessage = await screen.findByText('暂无存档', {}, { timeout: 3000 });
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
    expect(screen.getByText('确认删除')).toBeInTheDocument();
    expect(screen.getByText('删除后无法恢复，确定要删除这个存档吗？')).toBeInTheDocument();
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
      const deleteBtn = screen.getByRole('button', { name: /^删除$/ });
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
      expect(screen.getByText('暂无存档')).toBeInTheDocument();
    });

    // Should not call fetchSavedGames when not authenticated
    expect(fetchSavedGamesSpy).not.toHaveBeenCalled();
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
      expect(screen.getByText('加载存档失败，请重试')).toBeInTheDocument();
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
      expect(screen.getByText('删除失败，请重试')).toBeInTheDocument();
    });
  });
});
