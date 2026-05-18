/**
 * RecognizeDialog Component Tests
 * Tests for the entity recognition dialog in CollectionPanel.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { RecognizeDialog } from '@/components/game/collection/RecognizeDialog';
import { useCollectionStore } from '@/stores/useCollectionStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import type { RecognizedEntity } from '@/lib/types';

const mockRecognizedEntities = {
  items: [
    { name: '神秘宝石', description: '一颗闪烁着蓝光的宝石', category: 'treasure', importance: 'critical' as const, appear_count: 3, appear_contexts: ['在山洞中发现', '在战斗中使用'] },
    { name: '旧地图', description: '一张破旧的藏宝图', category: 'document', importance: 'important' as const, appear_count: 2, appear_contexts: ['在书房找到'] },
  ] as RecognizedEntity[],
  characters: [
    { name: '神秘老人', description: '一位身着长袍的老者', category: 'NPC', importance: 'important' as const, appear_count: 4, appear_contexts: ['在村庄入口相遇'] },
  ] as RecognizedEntity[],
  landmarks: [
    { name: '古老神殿', description: '一座废弃的神殿', category: 'building', importance: 'critical' as const, appear_count: 2, appear_contexts: ['第一次探索'] },
  ] as RecognizedEntity[],
};

const STORE_METHODS = ['fetchCollection', 'setActiveTab', 'selectCharacter', 'selectItem', 'selectLandmark', 'generateCharacterImage', 'generateItemImage', 'generateLandmarkImage', 'generateItemDescription', 'generateLandmarkDescription', 'regenerateCharacterImage', 'regenerateItemImage', 'recognizeEntities', 'addRecognizedEntities', 'clearRecognizedEntities', 'createItem', 'deleteItem', 'deleteCharacter', 'deleteLandmark', 'clearError'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useCollectionStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useCollectionStore.setState({
    characters: [],
    items: [],
    landmarks: [],
    isLoading: false,
    activeTab: 'characters',
    selectedCharacter: null,
    selectedItem: null,
    selectedLandmark: null,
    generatingImageFor: null,
    generatingDescriptionFor: null,
    regeneratingImageFor: null,
    error: null,
    isRecognizing: false,
    recognizedEntities: null,
    isDeleting: false,
    deletingEntity: null,
  });
}

describe('RecognizeDialog', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useCollectionStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  describe('Dialog Open/Close', () => {
    it('shows recognize button', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('智能识别')).toBeInTheDocument();
    });

    it('calls recognizeEntities when clicking recognize button', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));
      expect(storeSpy.spies.recognizeEntities).toHaveBeenCalledWith(1);
    });

    it('disables button while recognizing', () => {
      useCollectionStore.setState({ isRecognizing: true });
      render(<CollectionPanel gameId={1} />);
      const recognizeButton = screen.getByText('智能识别').closest('button');
      expect(recognizeButton).toBeDisabled();
    });
  });

  describe('Recognition Results', () => {
    it('shows loading state while recognizing', () => {
      useCollectionStore.setState({ isRecognizing: true });
      render(<CollectionPanel gameId={1} />);
      expect(document.querySelector('.animate-spin')).toBeInTheDocument();
    });

    it('does not show add-in-progress copy while analysis is still running', () => {
      render(
        <RecognizeDialog
          open={true}
          onClose={jest.fn()}
          onSubmit={jest.fn()}
          isRecognizing={true}
          isLoading={true}
          recognizedEntities={null}
          selectedItems={[]}
          selectedCharacters={[]}
          selectedLandmarks={[]}
          onToggleItemSelection={jest.fn()}
          onToggleCharacterSelection={jest.fn()}
          onToggleLandmarkSelection={jest.fn()}
        />
      );

      expect(screen.getByText('正在分析故事历史...')).toBeInTheDocument();
      expect(screen.queryByText('添加中...')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: '分析中...' })).toBeDisabled();
    });

    it('shows recognized results instead of stale loading copy once candidates exist', () => {
      render(
        <RecognizeDialog
          open={true}
          onClose={jest.fn()}
          onSubmit={jest.fn()}
          isRecognizing={true}
          isLoading={false}
          recognizedEntities={mockRecognizedEntities}
          selectedItems={mockRecognizedEntities.items}
          selectedCharacters={mockRecognizedEntities.characters}
          selectedLandmarks={mockRecognizedEntities.landmarks}
          onToggleItemSelection={jest.fn()}
          onToggleCharacterSelection={jest.fn()}
          onToggleLandmarkSelection={jest.fn()}
        />
      );

      expect(screen.queryByText('正在分析故事历史...')).not.toBeInTheDocument();
      expect(screen.getByText('神秘老人')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /添加到收集/ })).toBeEnabled();
    });

    it('shows an explicit empty state instead of a blank dialog when no result is available', () => {
      render(
        <RecognizeDialog
          open={true}
          onClose={jest.fn()}
          onSubmit={jest.fn()}
          isRecognizing={false}
          isLoading={false}
          recognizedEntities={null}
          selectedItems={[]}
          selectedCharacters={[]}
          selectedLandmarks={[]}
          onToggleItemSelection={jest.fn()}
          onToggleCharacterSelection={jest.fn()}
          onToggleLandmarkSelection={jest.fn()}
        />
      );

      expect(screen.getByText('未识别到新的实体')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '添加到收集' })).toBeDisabled();
    });

    it('shows recognized items when available', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText('神秘宝石')).toBeInTheDocument();
      });
    });

    it('shows recognized characters when available', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText('神秘老人')).toBeInTheDocument();
      });
    });

    it('shows recognized landmarks when available', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText('古老神殿')).toBeInTheDocument();
      });
    });

    it('shows entity count labels', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText(/识别到的物品 \(2\)/)).toBeInTheDocument();
        expect(screen.getByText(/识别到的人物 \(1\)/)).toBeInTheDocument();
        expect(screen.getByText(/识别到的地点 \(1\)/)).toBeInTheDocument();
      });
    });

    it('shows empty state when no entities recognized', async () => {
      const empty = { items: [], characters: [], landmarks: [] };
      storeSpy.spies.recognizeEntities.mockResolvedValue(empty);
      useCollectionStore.setState({ recognizedEntities: empty });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText('未识别到新的实体')).toBeInTheDocument();
      });
    });
  });

  describe('Entity Selection', () => {
    it('has checkboxes for each recognized entity', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        const checkboxes = screen.getAllByRole('checkbox');
        expect(checkboxes.length).toBe(4);
      });
    });

    it('shows appear count for each entity', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText(/出现 3 次/)).toBeInTheDocument();
      });
    });
  });

  describe('Submit Recognition', () => {
    it('shows add to collection button', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText(/添加到收集/)).toBeInTheDocument();
      });
    });

    it('disables submit when nothing selected', async () => {
      const empty = { items: [], characters: [], landmarks: [] };
      storeSpy.spies.recognizeEntities.mockResolvedValue(empty);
      useCollectionStore.setState({ recognizedEntities: empty });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        const submitButton = screen.getByText('添加到收集').closest('button');
        expect(submitButton).toBeDisabled();
      });
    });
  });

  describe('Cancel Recognition', () => {
    it('shows cancel button in dialog', async () => {
      storeSpy.spies.recognizeEntities.mockResolvedValue(mockRecognizedEntities);
      useCollectionStore.setState({ recognizedEntities: mockRecognizedEntities });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('智能识别'));

      await waitFor(() => {
        expect(screen.getByText('取消')).toBeInTheDocument();
      });
    });
  });
});
