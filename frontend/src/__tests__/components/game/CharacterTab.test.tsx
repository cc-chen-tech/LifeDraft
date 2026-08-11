/**
 * CharacterTab Component Tests
 * Tests for the character tab section of CollectionPanel.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import type { CharacterCollectionItem } from '@/lib/types';

const mockCharacters: CharacterCollectionItem[] = [
  { name: '李明', role: '主角', description: '一个普通的年轻人', affinity: 100, age: 25, gender: '男', occupation: '学生', personality_traits: ['勇敢', '善良'], image_url: '/images/liming.png', image_generated: true, description_generated: true },
  { name: '王芳', role: 'NPC', description: '主角的朋友', affinity: 80, age: 24, gender: '女', occupation: '医生', personality_traits: ['聪明', '细心'], image_url: null, image_generated: false, description_generated: true },
  { name: '张三', role: 'NPC', description: '神秘的老人', affinity: 30, age: 70, gender: '男', occupation: '隐士', personality_traits: ['智慧'], image_url: '/images/zhangsan.png', image_generated: true, description_generated: true },
];

const STORE_METHODS = ['fetchCollection', 'setActiveTab', 'selectCharacter', 'selectItem', 'selectLandmark', 'generateCharacterImage', 'generateItemImage', 'generateLandmarkImage', 'generateItemDescription', 'generateLandmarkDescription', 'regenerateCharacterImage', 'regenerateItemImage', 'recognizeEntities', 'addRecognizedEntities', 'clearRecognizedEntities', 'createItem', 'deleteItem', 'deleteCharacter', 'deleteLandmark', 'clearError'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useCollectionStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useCollectionStore.setState({
    characters: mockCharacters,
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

describe('CharacterTab', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useCollectionStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  it('renders character list', () => {
    render(<CollectionPanel gameId={1} />);
    expect(screen.getByText('李明')).toBeInTheDocument();
    expect(screen.getByText('王芳')).toBeInTheDocument();
    expect(screen.getByText('张三')).toBeInTheDocument();
  });

  it('renders character count in tab button', () => {
    render(<CollectionPanel gameId={1} />);
    expect(screen.getByText(/人物 \(3\)/)).toBeInTheDocument();
  });

  it('renders character role', () => {
    render(<CollectionPanel gameId={1} />);
    expect(screen.getByText('主角')).toBeInTheDocument();
  });

  it('shows image status badge for characters with image', () => {
    render(<CollectionPanel gameId={1} />);
    const badges = screen.getAllByText('有图');
    expect(badges.length).toBeGreaterThan(0);
  });

  it('shows pending badge for characters without image', () => {
    render(<CollectionPanel gameId={1} />);
    const pendingBadges = screen.getAllByText('待生成');
    expect(pendingBadges.length).toBeGreaterThan(0);
  });

  it('renders empty state when no characters', () => {
    useCollectionStore.setState({ characters: [] });
    render(<CollectionPanel gameId={1} />);
    expect(screen.getByText('暂无人物记录')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    useCollectionStore.setState({ isLoading: true });
    render(<CollectionPanel gameId={1} />);
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  describe('Interactions', () => {
    it('calls selectCharacter when clicking a character', async () => {
      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      await user.click(screen.getByText('李明'));
      expect(storeSpy.spies.selectCharacter).toHaveBeenCalledWith(mockCharacters[0]);
    });

    it('calls setActiveTab when clicking tab buttons', async () => {
      const user = userEvent.setup();
      render(<CollectionPanel gameId={1} />);
      const itemsButton = screen.getByRole('tab', { name: /物品/ });
      await user.click(itemsButton);
      expect(storeSpy.spies.setActiveTab).toHaveBeenCalledWith('items');
    });

    it('fetches collection on mount', () => {
      render(<CollectionPanel gameId={1} />);
      expect(storeSpy.spies.fetchCollection).toHaveBeenCalledWith(1);
    });
  });

  describe('Character Detail Dialog', () => {
    it('shows character detail dialog when character is selected', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('一个普通的年轻人')).toBeInTheDocument();
    });

    it('shows generate image button for character without image', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[1] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('生成图片')).toBeInTheDocument();
    });

    it('shows modify button for character with image', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('修改画像')).toBeInTheDocument();
    });

    it('shows character age in detail dialog', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('25 岁')).toBeInTheDocument();
    });

    it('shows character occupation in detail dialog', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('学生')).toBeInTheDocument();
    });

    it('shows character affinity in detail dialog', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('100/100')).toBeInTheDocument();
    });

    it('shows personality traits as badges', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[0] });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('勇敢')).toBeInTheDocument();
      expect(screen.getByText('善良')).toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('shows loading indicator while generating image', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[1], generatingImageFor: '王芳' });
      render(<CollectionPanel gameId={1} />);
      expect(screen.getByText('生成中...')).toBeInTheDocument();
    });

    it('disables button while generating', () => {
      useCollectionStore.setState({ selectedCharacter: mockCharacters[1], generatingImageFor: '王芳' });
      render(<CollectionPanel gameId={1} />);
      const button = screen.getByText('生成中...').closest('button');
      expect(button).toBeDisabled();
    });
  });
});
