/**
 * ItemTab Component Tests
 * 
 * Tests for the item tab section of CollectionPanel.
 * These tests prepare for future component extraction.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';
import type { ItemCollectionItem } from '@/lib/types';

// Mock the collection store
const mockFetchCollection = jest.fn();
const mockSelectItem = jest.fn();
const mockSetActiveTab = jest.fn();
const mockGenerateItemImage = jest.fn();
const mockGenerateItemDescription = jest.fn();
const mockRegenerateItemImage = jest.fn();
const mockCreateItem = jest.fn();
const mockDeleteItem = jest.fn();

jest.mock('@/stores/useCollectionStore', () => ({
  useCollectionStore: jest.fn(),
}));

const mockItems: ItemCollectionItem[] = [
  {
    name: '古老的钥匙',
    description: '一把锈迹斑斑的铜钥匙',
    importance: 'critical',
    category: 'keepsake',
    acquired_week: 3,
    acquired_context: '在地下室发现的',
    is_key_item: true,
    image_url: '/images/key.png',
    image_generated: true,
    description_generated: true,
    metadata: {},
  },
  {
    name: '药草',
    description: '一束新鲜的草药',
    importance: 'normal',
    category: 'tool',
    acquired_week: 5,
    acquired_context: '在山上采集的',
    is_key_item: false,
    image_url: null,
    image_generated: false,
    description_generated: true,
    metadata: {},
  },
  {
    name: '神秘日记',
    description: '一本残破的日记本',
    importance: 'important',
    category: 'document',
    acquired_week: 7,
    acquired_context: '图书馆角落里找到的',
    is_key_item: true,
    image_url: '/images/diary.png',
    image_generated: true,
    description_generated: false,
    metadata: {},
  },
];

const createMockStore = (overrides = {}) => ({
  characters: [],
  items: mockItems,
  landmarks: [],
  isLoading: false,
  activeTab: 'items',
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
  setActiveTab: mockSetActiveTab,
  selectCharacter: jest.fn(),
  selectItem: mockSelectItem,
  selectLandmark: jest.fn(),
  generateCharacterImage: jest.fn(),
  generateItemImage: mockGenerateItemImage,
  generateLandmarkImage: jest.fn(),
  generateItemDescription: mockGenerateItemDescription,
  generateLandmarkDescription: jest.fn(),
  regenerateCharacterImage: jest.fn(),
  regenerateItemImage: mockRegenerateItemImage,
  recognizeEntities: jest.fn(),
  addRecognizedEntities: jest.fn(),
  clearRecognizedEntities: jest.fn(),
  createItem: mockCreateItem,
  deleteItem: mockDeleteItem,
  deleteCharacter: jest.fn(),
  deleteLandmark: jest.fn(),
  clearError: jest.fn(),
  ...overrides,
});

describe('ItemTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
      const store = createMockStore();
      return selector ? selector(store) : store;
    });
  });

  // ==================== Rendering Tests ====================
  describe('Rendering', () => {
    it('renders item list', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('古老的钥匙')).toBeInTheDocument();
      expect(screen.getByText('药草')).toBeInTheDocument();
      expect(screen.getByText('神秘日记')).toBeInTheDocument();
    });

    it('renders item count in tab button', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText(/物品 \(3\)/)).toBeInTheDocument();
    });

    it('renders item category label', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('纪念品')).toBeInTheDocument();
      expect(screen.getByText('工具')).toBeInTheDocument();
      expect(screen.getByText('文件')).toBeInTheDocument();
    });

    it('shows key item indicator for important items', () => {
      render(<CollectionPanel gameId={1} />);
      // Sparkles icon for key items
      const itemCards = screen.getAllByRole('button');
      expect(itemCards.length).toBeGreaterThan(0);
    });

    it('shows pending badge for items without image', () => {
      render(<CollectionPanel gameId={1} />);
      const pendingBadges = screen.getAllByText('待生成');
      expect(pendingBadges.length).toBeGreaterThan(0);
    });

    it('renders empty state when no items', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ items: [] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('暂无物品记录')).toBeInTheDocument();
    });

    it('renders loading state', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ isLoading: true });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      expect(document.querySelector('.animate-spin')).toBeInTheDocument();
    });

    it('shows manual add button for items tab', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('手动添加')).toBeInTheDocument();
    });
  });

  // ==================== Interaction Tests ====================
  describe('Interactions', () => {
    it('calls selectItem when clicking an item', async () => {
      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('古老的钥匙'));
      
      expect(mockSelectItem).toHaveBeenCalledWith(mockItems[0]);
    });
  });

  // ==================== Item Detail Dialog Tests ====================
  describe('Item Detail Dialog', () => {
    it('shows item detail dialog when item is selected', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedItem: mockItems[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('一把锈迹斑斑的铜钥匙')).toBeInTheDocument();
    });

    it('shows generate image button for item without image', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedItem: mockItems[1] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('生成图片')).toBeInTheDocument();
    });

    it('shows modify button for item with image', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedItem: mockItems[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('修改图片')).toBeInTheDocument();
    });

    it('shows acquired week in detail dialog', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedItem: mockItems[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('第 4 周')).toBeInTheDocument(); // acquired_week + 1
    });

    it('shows acquired context in detail dialog', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedItem: mockItems[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('在地下室发现的')).toBeInTheDocument();
    });

    it('shows generate description button when description not generated', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          selectedItem: {
            ...mockItems[0],
            description: null,
            description_generated: false,
          },
        });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('生成描述')).toBeInTheDocument();
    });

    it('shows importance label in detail dialog', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedItem: mockItems[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText(/关键/)).toBeInTheDocument();
    });
  });

  // ==================== Loading State Tests ====================
  describe('Loading States', () => {
    it('shows loading indicator while generating image', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          selectedItem: mockItems[1],
          generatingImageFor: '药草',
        });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('生成中...')).toBeInTheDocument();
    });

    it('shows loading indicator while generating description', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          selectedItem: {
            ...mockItems[0],
            description: null,
            description_generated: false,
          },
          generatingDescriptionFor: '古老的钥匙',
        });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      // Looking for loading text in description button
      const buttons = screen.getAllByRole('button');
      const loadingButton = buttons.find((b: HTMLElement) => b.textContent?.includes('生成中'));
      expect(loadingButton).toBeDefined();
    });
  });

  // ==================== Delete Tests ====================
  describe('Delete Item', () => {
    it('shows delete button in item detail', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedItem: mockItems[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      // Find delete button (Trash icon)
      const deleteButton = screen.getByRole('button', { name: '' });
      expect(deleteButton).toBeInTheDocument();
    });
  });
});
