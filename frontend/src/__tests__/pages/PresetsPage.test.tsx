/**
 * Presets Page Tests
 * Tests all interactive elements of the presets page
 */
import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
      expect(screen.getByRole('status')).toHaveTextContent('正在整理角色预设');
    });
  });

  describe('Empty state', () => {
    it('shows empty message when no presets', async () => {
      render(<PresetsPage />);

      await waitFor(() => {
        expect(screen.getByText('还没有角色预设')).toBeInTheDocument();
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
        expect(screen.getByRole('heading', { name: '删除角色预设“Warrior Preset”？' })).toBeInTheDocument();
        expect(screen.getByText(/删除后无法恢复/)).toBeInTheDocument();
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
        expect(screen.getByRole('heading', { name: '删除角色预设“Warrior Preset”？' })).toBeInTheDocument();
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
        expect(screen.getByRole('heading', { name: '删除角色预设“Warrior Preset”？' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: '取消' }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(deletePresetSpy).not.toHaveBeenCalled();
    });
  });

  describe('story101 management contract', () => {
    const longPresetName = '一份名字很长需要在三百二十像素宽度下自然换行的角色预设';
    const storyPreset = {
      preset_id: 31,
      preset_name: longPresetName,
      player_name: '林望舒',
      life_vision: '走过很远的路，再回到最初的小城。',
      character_settings: { courage: 7 },
      created_at: '2026-08-09T10:00:00Z',
    };

    async function openDeleteDialog() {
      const user = userEvent.setup();
      useGameStore.setState({ presets: [storyPreset] });
      render(<PresetsPage />);
      await user.click(await screen.findByRole('button', {
        name: `删除角色预设“${longPresetName}”`,
      }));
      return { user, dialog: await screen.findByRole('dialog') };
    }

    it('uses the lowercase brand, one reading surface, and no card wall', async () => {
      useGameStore.setState({ presets: [storyPreset] });
      const { container } = render(<PresetsPage />);

      await screen.findByText(longPresetName);

      expect(screen.getByText('story101')).toHaveClass('font-brand');
      expect(screen.getByRole('heading', { level: 1, name: '角色预设' })).toBeInTheDocument();
      expect(container.querySelectorAll('[data-slot="surface"][data-variant="reading"]')).toHaveLength(1);
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
    });

    it('shows a retryable alert when preset loading fails instead of an empty state', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      fetchPresetsSpy
        .mockRejectedValueOnce(new Error('first failure'))
        .mockRejectedValueOnce(new Error('second failure'));

      render(<PresetsPage />);

      expect(await screen.findByRole('alert')).toHaveTextContent('未能载入角色预设');
      fireEvent.click(screen.getByRole('button', { name: '重试载入角色预设' }));

      await waitFor(() => expect(fetchPresetsSpy).toHaveBeenCalledTimes(2));
      expect(await screen.findByRole('alert')).toHaveTextContent('未能载入角色预设');
      expect(screen.queryByText('还没有角色预设')).not.toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    it('gives long and unnamed presets exact touch-sized actions in separate danger rows', async () => {
      useGameStore.setState({
        presets: [
          storyPreset,
          {
            ...storyPreset,
            preset_id: 32,
            preset_name: '   ',
            player_name: '未命名人物',
          },
        ],
      });
      const { container } = render(<PresetsPage />);

      const longName = await screen.findByText(longPresetName);
      expect(longName).toHaveClass('break-words');
      expect(screen.getByText('未命名预设')).toBeInTheDocument();

      const useButton = screen.getByRole('button', {
        name: `使用角色预设“${longPresetName}”`,
      });
      const deleteButton = screen.getByRole('button', {
        name: `删除角色预设“${longPresetName}”`,
      });
      const dangerRow = deleteButton.closest('[data-slot="danger-row"]');

      expect(container.querySelector('[data-slot="management-row"]')).toHaveClass('min-w-0');
      expect(useButton).toHaveAttribute('data-size', 'touch');
      expect(deleteButton).toHaveAttribute('data-size', 'touch');
      expect(dangerRow).toContainElement(deleteButton);
      expect(dangerRow).not.toContainElement(useButton);
    });

    it('names the preset and explicitly focuses cancel in the delete dialog', async () => {
      const { dialog } = await openDeleteDialog();

      expect(within(dialog).getByRole('heading', {
        name: `删除角色预设“${longPresetName}”？`,
      })).toBeInTheDocument();
      expect(within(dialog).getByText(/删除后无法恢复/)).toBeInTheDocument();
      expect(within(dialog).getByRole('button', { name: '取消' })).toHaveFocus();
    });

    it('announces preset deletion progress and prevents duplicate submission or closing', async () => {
      let resolveDelete: () => void = () => {};
      deletePresetSpy.mockImplementation(() => new Promise<void>((resolve) => {
        resolveDelete = resolve;
      }));
      const { user, dialog } = await openDeleteDialog();
      const deleteButton = within(dialog).getByRole('button', { name: '删除' });

      fireEvent.click(deleteButton);
      fireEvent.click(deleteButton);

      await waitFor(() => expect(dialog).toHaveAttribute('aria-busy', 'true'));
      expect(within(dialog).getByRole('button', { name: '正在删除' })).toBeDisabled();
      expect(deletePresetSpy).toHaveBeenCalledTimes(1);
      await user.keyboard('{Escape}');
      expect(screen.getByRole('dialog')).toBeInTheDocument();

      resolveDelete();
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    });

    it('keeps preset deletion failures inside the dialog with the target name', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      deletePresetSpy.mockRejectedValueOnce(new Error('delete failed'));
      const { user, dialog } = await openDeleteDialog();

      await user.click(within(dialog).getByRole('button', { name: '删除' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        `未能删除角色预设“${longPresetName}”`,
      );
      expect(within(dialog).getByRole('button', { name: '删除' })).toBeEnabled();
      consoleErrorSpy.mockRestore();
    });

    it('announces a successful preset deletion with the target name', async () => {
      const { user, dialog } = await openDeleteDialog();

      await user.click(within(dialog).getByRole('button', { name: '删除' }));

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
      expect(screen.getByRole('status')).toHaveTextContent(`已删除角色预设“${longPresetName}”`);
      expect(deletePresetSpy).toHaveBeenCalledWith(31);
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
