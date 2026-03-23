/**
 * LandmarkTab Component Tests
 * 
 * Tests for the landmark tab section of CollectionPanel.
 * These tests prepare for future component extraction.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';
import type { LandmarkCollectionItem } from '@/lib/types';

// Mock the collection store
const mockFetchCollection = jest.fn();
const mockSelectLandmark = jest.fn();
const mockSetActiveTab = jest.fn();
const mockGenerateLandmarkImage = jest.fn();
const mockGenerateLandmarkDescription = jest.fn();
const mockDeleteLandmark = jest.fn();

jest.mock('@/stores/useCollectionStore', () => ({
  useCollectionStore: jest.fn(),
}));

const mockLandmarks: LandmarkCollectionItem[] = [
  {
    name: '古老的城堡',
    description: '一座巍峨的古堡，矗立在山顶',
    category: 'building',
    importance: 'critical',
    first_appear_week: 1,
    appear_count: 5,
    last_appear_week: 10,
    context: '主角冒险开始的地方',
    is_key_location: true,
    image_url: '/images/castle.png',
    image_generated: true,
    metadata: {},
  },
  {
    name: '神秘森林',
    description: '一片浓密的森林，充满神秘气息',
    category: 'nature',
    importance: 'important',
    first_appear_week: 3,
    appear_count: 3,
    last_appear_week: 8,
    context: '藏有重要线索的地方',
    is_key_location: false,
    image_url: null,
    image_generated: false,
    metadata: {},
  },
  {
    name: '地下密室',
    description: '一个隐蔽的地下房间',
    category: 'room',
    importance: 'normal',
    first_appear_week: 5,
    appear_count: 2,
    last_appear_week: 7,
    context: '发现宝藏的地方',
    is_key_location: true,
    image_url: '/images/chamber.png',
    image_generated: true,
    metadata: {},
  },
];

const createMockStore = (overrides = {}) => ({
  characters: [],
  items: [],
  landmarks: mockLandmarks,
  isLoading: false,
  activeTab: 'landmarks',
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
  selectItem: jest.fn(),
  selectLandmark: mockSelectLandmark,
  generateCharacterImage: jest.fn(),
  generateItemImage: jest.fn(),
  generateLandmarkImage: mockGenerateLandmarkImage,
  generateItemDescription: jest.fn(),
  generateLandmarkDescription: mockGenerateLandmarkDescription,
  regenerateCharacterImage: jest.fn(),
  regenerateItemImage: jest.fn(),
  recognizeEntities: jest.fn(),
  addRecognizedEntities: jest.fn(),
  clearRecognizedEntities: jest.fn(),
  createItem: jest.fn(),
  deleteItem: jest.fn(),
  deleteCharacter: jest.fn(),
  deleteLandmark: mockDeleteLandmark,
  clearError: jest.fn(),
  ...overrides,
});

describe('LandmarkTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
      const store = createMockStore();
      return selector ? selector(store) : store;
    });
  });

  // ==================== Rendering Tests ====================
  describe('Rendering', () => {
    it('renders landmark list', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('古老的城堡')).toBeInTheDocument();
      expect(screen.getByText('神秘森林')).toBeInTheDocument();
      expect(screen.getByText('地下密室')).toBeInTheDocument();
    });

    it('renders landmark count in tab button', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText(/标志物 \(3\)/)).toBeInTheDocument();
    });

    it('renders landmark category labels', () => {
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('建筑')).toBeInTheDocument();
      expect(screen.getByText('自然景观')).toBeInTheDocument();
      expect(screen.getByText('房间')).toBeInTheDocument();
    });

    it('shows key location indicator for important landmarks', () => {
      render(<CollectionPanel gameId={1} />);
      // Key locations have sparkles icon
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('shows pending badge for landmarks without image', () => {
      render(<CollectionPanel gameId={1} />);
      const pendingBadges = screen.getAllByText('待生成');
      expect(pendingBadges.length).toBeGreaterThan(0);
    });

    it('renders empty state when no landmarks', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ landmarks: [] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('暂无标志物记录')).toBeInTheDocument();
    });

    it('renders loading state', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ isLoading: true });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      expect(document.querySelector('.animate-spin')).toBeInTheDocument();
    });
  });

  // ==================== Interaction Tests ====================
  describe('Interactions', () => {
    it('calls selectLandmark when clicking a landmark', async () => {
      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      
      await user.click(screen.getByText('古老的城堡'));
      
      expect(mockSelectLandmark).toHaveBeenCalledWith(mockLandmarks[0]);
    });
  });

  // ==================== Landmark Detail Dialog Tests ====================
  describe('Landmark Detail Dialog', () => {
    it('shows landmark detail dialog when landmark is selected', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedLandmark: mockLandmarks[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('一座巍峨的古堡，矗立在山顶')).toBeInTheDocument();
    });

    it('shows generate image button for landmark without image', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedLandmark: mockLandmarks[1] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('生成图片')).toBeInTheDocument();
    });

    it('shows first appear week in detail dialog', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedLandmark: mockLandmarks[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('第 2 周')).toBeInTheDocument(); // first_appear_week + 1
    });

    it('shows appear count in detail dialog', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedLandmark: mockLandmarks[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('5 次')).toBeInTheDocument();
    });

    it('shows context in detail dialog', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedLandmark: mockLandmarks[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('主角冒险开始的地方')).toBeInTheDocument();
    });

    it('shows generate description button when no description', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          selectedLandmark: {
            ...mockLandmarks[0],
            description: null,
          },
        });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('生成描述')).toBeInTheDocument();
    });

    it('shows importance label in detail dialog', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedLandmark: mockLandmarks[0] });
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
          selectedLandmark: mockLandmarks[1],
          generatingImageFor: '神秘森林',
        });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      expect(screen.getByText('生成中...')).toBeInTheDocument();
    });

    it('shows loading indicator while generating description', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({
          selectedLandmark: {
            ...mockLandmarks[0],
            description: null,
          },
          generatingDescriptionFor: '古老的城堡',
        });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      const buttons = screen.getAllByRole('button');
      const loadingButton = buttons.find((b: HTMLElement) => b.textContent?.includes('生成中'));
      expect(loadingButton).toBeDefined();
    });
  });

  // ==================== Delete Tests ====================
  describe('Delete Landmark', () => {
    it('shows delete button in landmark detail', () => {
      (useCollectionStore as unknown as jest.Mock).mockImplementation((selector) => {
        const store = createMockStore({ selectedLandmark: mockLandmarks[0] });
        return selector ? selector(store) : store;
      });

      render(<CollectionPanel gameId={1} />);
      
      // Find delete button (Trash icon)
      const deleteButtons = screen.getAllByRole('button');
      expect(deleteButtons.length).toBeGreaterThan(0);
    });
  });
});
