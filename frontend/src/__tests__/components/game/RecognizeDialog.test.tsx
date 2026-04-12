/**
 * RecognizeDialog Component Tests
 * 
 * Tests for the entity recognition dialog in CollectionPanel.
 * These tests prepare for future component extraction.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act as rtlAct } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';
import type { RecognizedEntity } from '@/lib/types';

// Mock the collection store
const mockFetchCollection = jest.fn();
const mockRecognizeEntities = jest.fn();
const mockAddRecognizedEntities = jest.fn();
const mockClearRecognizedEntities = jest.fn();

jest.mock('@/stores/useCollectionStore', () => ({
  useCollectionStore: jest.fn(),
}));

const mockRecognizedEntities = {
  items: [
    {
      name: '神秘宝石',
      description: '一颗闪烁着蓝光的宝石',
      category: 'treasure',
      importance: 'critical' as const,
      appear_count: 3,
      appear_contexts: ['在山洞中发现', '在战斗中使用'],
    },
    {
      name: '旧地图',
      description: '一张破旧的藏宝图',
      category: 'document',
      importance: 'important' as const,
      appear_count: 2,
      appear_contexts: ['在书房找到'],
    },
  ] as RecognizedEntity[],
  characters: [
    {
      name: '神秘老人',
      description: '一位身着长袍的老者',
      category: 'NPC',
      importance: 'important' as const,
      appear_count: 4,
      appear_contexts: ['在村庄入口相遇'],
    },
  ] as RecognizedEntity[],
  landmarks: [
    {
      name: '古老神殿',
      description: '一座废弃的神殿',
      category: 'building',
      importance: 'critical' as const,
      appear_count: 2,
      appear_contexts: ['第一次探索'],
    },
  ] as RecognizedEntity[],
};

const createMockStore = (overrides = {}) => ({
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
  fetchCollection: mockFetchCollection,
  setActiveTab: jest.fn(),
  selectCharacter: jest.fn(),
  selectItem: jest.fn(),
  selectLandmark: jest.fn(),
  generateCharacterImage: jest.fn(),
  generateItemImage: jest.fn(),
  generateLandmarkImage: jest.fn(),
  generateItemDescription: jest.fn(),
  generateLandmarkDescription: jest.fn(),
  regenerateCharacterImage: jest.fn(),
  regenerateItemImage: jest.fn(),
  recognizeEntities: mockRecognizeEntities,
  addRecognizedEntities: mockAddRecognizedEntities,
  clearRecognizedEntities: mockClearRecognizedEntities,
  createItem: jest.fn(),
  deleteItem: jest.fn(),
  deleteCharacter: jest.fn(),
  deleteLandmark: jest.fn(),
  clearError: jest.fn(),
  ...overrides,
});

describe('RecognizeDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
      const store = createMockStore();
      return selector ? selector(store) : store;
    });
  });

  // ==================== Dialog Open/Close Tests ====================
  describe('Dialog Open/Close', () => {
    it('shows recognize button', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('智能识别')).toBeInTheDocument();
    });

    it('calls recognizeEntities when clicking recognize button', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      expect(mockRecognizeEntities).toHaveBeenCalledWith(1);
    });

    it('disables button while recognizing', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ isRecognizing: true });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      const recognizeButton = screen.getByText('智能识别').closest('button');
      expect(recognizeButton).toBeDisabled();
    });
  });

  // ==================== Recognition Results Tests ====================
  describe('Recognition Results', () => {
    it('shows loading state while recognizing', async () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ isRecognizing: true });
        return selector ? selector(store) : store;
      });
      
      render(<CollectionPanel gameId={1} />);
      
      // Should show loading spinner
      expect(document.querySelector('.animate-spin')).toBeInTheDocument();
    });

    it('shows recognized items when available', async () => {
      // First click to open dialog
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      // Wait for dialog to be rendered
      await waitFor(() => {
        expect(screen.getByText('神秘宝石')).toBeInTheDocument();
      });
    });

    it('shows recognized characters when available', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        expect(screen.getByText('神秘老人')).toBeInTheDocument();
      });
    });

    it('shows recognized landmarks when available', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        expect(screen.getByText('古老神殿')).toBeInTheDocument();
      });
    });

    it('shows entity count labels', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

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
      mockRecognizeEntities.mockResolvedValue({
        items: [],
        characters: [],
        landmarks: [],
      });
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: { items: [], characters: [], landmarks: [] },
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        expect(screen.getByText('未识别到新的实体')).toBeInTheDocument();
      });
    });
  });

  // ==================== Selection Tests ====================
  describe('Entity Selection', () => {
    it('has checkboxes for each recognized entity', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        const checkboxes = screen.getAllByRole('checkbox');
        // 2 items + 1 character + 1 landmark = 4 checkboxes
        expect(checkboxes.length).toBe(4);
      });
    });

    it('shows appear count for each entity', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        expect(screen.getByText(/出现 3 次/)).toBeInTheDocument();
      });
    });
  });

  // ==================== Submit Tests ====================
  describe('Submit Recognition', () => {
    it('shows add to collection button', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        expect(screen.getByText(/添加到收集/)).toBeInTheDocument();
      });
    });

    it('disables submit when nothing selected', async () => {
      mockRecognizeEntities.mockResolvedValue({
        items: [],
        characters: [],
        landmarks: [],
      });
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: { items: [], characters: [], landmarks: [] },
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        const submitButton = screen.getByText('添加到收集').closest('button');
        expect(submitButton).toBeDisabled();
      });
    });
  });

  // ==================== Cancel Tests ====================
  describe('Cancel Recognition', () => {
    it('shows cancel button in dialog', async () => {
      mockRecognizeEntities.mockResolvedValue(mockRecognizedEntities);
      
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          recognizedEntities: mockRecognizedEntities,
        });
        return selector ? selector(store) : store;
      });

      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('智能识别'));
      
      await waitFor(() => {
        expect(screen.getByText('取消')).toBeInTheDocument();
      });
    });
  });
});
