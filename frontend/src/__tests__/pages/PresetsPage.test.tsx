/**
 * Presets Page Tests
 * Tests all interactive elements of the presets page
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PresetsPage from '@/app/presets/page';
import { useGameStore } from '@/stores/useGameStore';

// Mock useRouter
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

function setupDefaultState() {
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

describe('PresetsPage', () => {
  let fetchPresetsSpy: jest.SpyInstance;
  let deletePresetSpy: jest.SpyInstance;
  let loadPresetSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockClear();
    setupDefaultState();
    const store = useGameStore.getState();
    fetchPresetsSpy = jest.spyOn(store, 'fetchPresets').mockResolvedValue(undefined);
    deletePresetSpy = jest.spyOn(store, 'deletePreset').mockResolvedValue(undefined);
    loadPresetSpy = jest.spyOn(store, 'loadPreset');
  });

  afterEach(() => {
    fetchPresetsSpy.mockRestore();
    deletePresetSpy.mockRestore();
    loadPresetSpy.mockRestore();
  });

  describe('Loading state', () => {
    it('shows loading indicator initially', () => {
      fetchPresetsSpy.mockImplementation(() => new Promise(() => {}));

      render(<PresetsPage />);
      expect(screen.getByText('加载中...')).toBeInTheDocument();
    });
  });

  describe('Empty state', () => {
    it('shows empty message when no presets', async () => {
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('暂无角色预设')).toBeInTheDocument();
      });
    });

    it('shows create character button when empty', async () => {
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '创建角色' })).toBeInTheDocument();
      });
    });

    it('navigates to create when clicking create character', async () => {
      const user = userEvent.setup();
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '创建角色' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: '创建角色' }));
      expect(mockPush).toHaveBeenCalledWith('/create');
    });
  });

  describe('With presets', () => {
    const testPresets = [
      {
        preset_id: 1,
        preset_name: 'Warrior Preset',
        player_name: 'Warrior',
        life_vision: 'Become the strongest',
        character_settings: { strength: 10 },
        created_at: '2024-01-15T10:00:00Z',
      },
      {
        preset_id: 2,
        preset_name: 'Mage Preset',
        player_name: 'Mage',
        life_vision: 'Master all magic',
        character_settings: { magic: 10 },
        created_at: '2024-01-14T10:00:00Z',
      },
    ];

    beforeEach(() => {
      useGameStore.setState({ presets: testPresets });
    });

    it('displays presets list', async () => {
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('Warrior Preset')).toBeInTheDocument();
        expect(screen.getByText('Mage Preset')).toBeInTheDocument();
      });
    });

    it('displays player name for each preset', async () => {
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('Warrior')).toBeInTheDocument();
        expect(screen.getByText('Mage')).toBeInTheDocument();
      });
    });

    it('displays life vision if present', async () => {
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('Become the strongest')).toBeInTheDocument();
        expect(screen.getByText('Master all magic')).toBeInTheDocument();
      });
    });

    it('loads preset when clicking load button', async () => {
      const user = userEvent.setup();
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('Warrior Preset')).toBeInTheDocument();
      });

      const loadButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg.lucide-play')
      );
      await user.click(loadButtons[0]);

      expect(loadPresetSpy).toHaveBeenCalledWith(testPresets[0]);
      expect(mockPush).toHaveBeenCalledWith('/create');
    });

    it('opens delete confirmation when clicking delete button', async () => {
      const user = userEvent.setup();
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('Warrior Preset')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg.lucide-trash-2')
      );
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('确认删除')).toBeInTheDocument();
        expect(screen.getByText('删除后无法恢复，确定要删除这个预设吗？')).toBeInTheDocument();
      });
    });

    it('deletes preset when confirming delete', async () => {
      const user = userEvent.setup();
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('Warrior Preset')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg.lucide-trash-2')
      );
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('确认删除')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: '删除' }));

      await waitFor(() => {
        expect(deletePresetSpy).toHaveBeenCalledWith(1);
      });
    });

    it('cancels delete when clicking cancel', async () => {
      const user = userEvent.setup();
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('Warrior Preset')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg.lucide-trash-2')
      );
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('确认删除')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: '取消' }));

      await waitFor(() => {
        expect(screen.queryByText('确认删除')).not.toBeInTheDocument();
      });
      expect(deletePresetSpy).not.toHaveBeenCalled();
    });
  });

  describe('Navigation', () => {
    it('navigates back when clicking back button', async () => {
      const user = userEvent.setup();
      render(<PresetsPage />);

      await user.click(screen.getByRole('button', { name: /返回/i }));
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('Page title', () => {
    it('displays correct page title', async () => {
      render(<PresetsPage />);
      expect(screen.getByText('角色预设')).toBeInTheDocument();
    });
  });
});
