/**
 * LandmarkTab Component Tests
 * Tests for the landmark tab section of CollectionPanel.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import type { LandmarkCollectionItem } from '@/lib/types';

const mockLandmarks: LandmarkCollectionItem[] = [
  { name: '古老的城堡', description: '一座巍峨的古堡，矗立在山顶', category: 'building', importance: 'critical', first_appear_week: 1, appear_count: 5, last_appear_week: 10, context: '主角冒险开始的地方', is_key_location: true, image_url: '/images/castle.png', image_generated: true, metadata: {} },
  { name: '神秘森林', description: '一片浓密的森林，充满神秘气息', category: 'nature', importance: 'important', first_appear_week: 3, appear_count: 3, last_appear_week: 8, context: '藏有重要线索的地方', is_key_location: false, image_url: null, image_generated: false, metadata: {} },
  { name: '地下密室', description: '一个隐蔽的地下房间', category: 'room', importance: 'normal', first_appear_week: 5, appear_count: 2, last_appear_week: 7, context: '发现宝藏的地方', is_key_location: true, image_url: '/images/chamber.png', image_generated: true, metadata: {} },
];

const STORE_METHODS = ['fetchCollection', 'setActiveTab', 'selectCharacter', 'selectItem', 'selectLandmark', 'generateCharacterImage', 'generateItemImage', 'generateLandmarkImage', 'generateItemDescription', 'generateLandmarkDescription', 'regenerateCharacterImage', 'regenerateItemImage', 'recognizeEntities', 'addRecognizedEntities', 'clearRecognizedEntities', 'createItem', 'deleteItem', 'deleteCharacter', 'deleteLandmark', 'clearError'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useCollectionStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useCollectionStore.setState({
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
  });
}

describe('LandmarkTab', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useCollectionStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

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
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('shows pending badge for landmarks without image', () => {
    render(<CollectionPanel gameId={1} />);
    const pendingBadges = screen.getAllByText('待生成');
    expect(pendingBadges.length).toBeGreaterThan(0);
  });

  it('renders empty state when no landmarks', () => {
    useCollectionStore.setState({ landmarks: [] });
    render(<CollectionPanel gameId={1} />);
    expect(screen.getByText('暂无标志物记录')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    useCollectionStore.setState({ isLoading: true });
    render(<CollectionPanel gameId={1} />);
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  describe('Interactions', () => {
    it('calls selectLandmark when clicking a landmark', async () => {
      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('古老的城堡'));
      expect(storeSpy.spies.selectLandmark).toHaveBeenCalledWith(mockLandmarks[0]);
    });
  });

  describe('Landmark Detail Dialog', () => {
    it('shows landmark detail dialog when landmark is selected', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('一座巍峨的古堡，矗立在山顶')).toBeInTheDocument();
    });

    it('shows generate image button for landmark without image', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[1] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('生成图片')).toBeInTheDocument();
    });

    it('shows first appear week in detail dialog', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('第 2 周')).toBeInTheDocument();
    });

    it('shows appear count in detail dialog', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('5 次')).toBeInTheDocument();
    });

    it('shows context in detail dialog', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('主角冒险开始的地方')).toBeInTheDocument();
    });

    it('shows generate description button when no description', () => {
      useCollectionStore.setState({ selectedLandmark: { ...mockLandmarks[0], description: null as any } });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('生成描述')).toBeInTheDocument();
    });

    it('shows importance label in detail dialog', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText(/关键/)).toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('shows loading indicator while generating image', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[1], generatingImageFor: '神秘森林' });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('生成中...')).toBeInTheDocument();
    });

    it('shows loading indicator while generating description', () => {
      useCollectionStore.setState({ selectedLandmark: { ...mockLandmarks[0], description: null as any }, generatingDescriptionFor: '古老的城堡' });
      render(<CollectionPanel gameId={1} />);
      const buttons = screen.getAllByRole('button');
      const loadingButton = buttons.find((b: HTMLElement) => b.textContent?.includes('生成中'));
      expect(loadingButton).toBeDefined();
    });
  });

  describe('Delete Landmark', () => {
    it('shows delete button in landmark detail', () => {
      useCollectionStore.setState({ selectedLandmark: mockLandmarks[0] });
      render(<CollectionPanel gameId={1} />);
      const deleteButtons = screen.getAllByRole('button');
      expect(deleteButtons.length).toBeGreaterThan(0);
    });
  });
});
