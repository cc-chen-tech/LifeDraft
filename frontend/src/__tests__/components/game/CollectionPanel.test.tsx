/**
 * CollectionPanel 组件测试 — useEffect fetchCollection 调用次数验证
 *
 * 直接 mock useCollectionStore，只关注 fetchCollection 被调用的时机和次数
 */
import { render } from '@testing-library/react';

// Mock 所有子组件，避免深层依赖
jest.mock('@/components/game/collection', () => ({
  CollectionTabs: () => <div data-testid="tabs" />,
  CharacterList: () => null,
  ItemList: () => null,
  LandmarkList: () => null,
  CharacterDetail: () => null,
  ItemDetail: () => null,
  LandmarkDetail: () => null,
  RecognizeDialog: () => null,
  AddItemDialog: () => null,
  DeleteConfirmDialog: () => null,
}));

jest.mock('@/components/ui/button', () => ({
  Button: (props: any) => <button {...props} />,
}));

jest.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({ children }: any) => <div>{children}</div>,
}));

jest.mock('lucide-react', () => ({
  Package: () => <span />,
  Wand2: () => <span />,
  Loader2: () => <span />,
  Plus: () => <span />,
}));

const mockFetchCollection = jest.fn();

jest.mock('@/stores/useCollectionStore', () => ({
  useCollectionStore: () => ({
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
    recognizeEntities: jest.fn(),
    addRecognizedEntities: jest.fn(),
    clearRecognizedEntities: jest.fn(),
    createItem: jest.fn(),
    deleteItem: jest.fn(),
    deleteCharacter: jest.fn(),
    deleteLandmark: jest.fn(),
    clearError: jest.fn(),
  }),
}));

import { CollectionPanel } from '@/components/game/CollectionPanel';

describe('CollectionPanel', () => {
  beforeEach(() => {
    mockFetchCollection.mockClear();
  });

  it('初始挂载时 fetchCollection 只调用 1 次', () => {
    render(<CollectionPanel gameId={1} />);
    expect(mockFetchCollection).toHaveBeenCalledTimes(1);
    expect(mockFetchCollection).toHaveBeenCalledWith(1);
  });

  it('相同 gameId 重新渲染不触发额外请求', () => {
    const { rerender } = render(<CollectionPanel gameId={1} />);
    expect(mockFetchCollection).toHaveBeenCalledTimes(1);

    rerender(<CollectionPanel gameId={1} />);
    expect(mockFetchCollection).toHaveBeenCalledTimes(1);
  });

  it('gameId 变化时重新获取', () => {
    const { rerender } = render(<CollectionPanel gameId={1} />);
    expect(mockFetchCollection).toHaveBeenCalledTimes(1);

    rerender(<CollectionPanel gameId={2} />);
    expect(mockFetchCollection).toHaveBeenCalledTimes(2);
    expect(mockFetchCollection).toHaveBeenLastCalledWith(2);
  });

  it('gameId 为 0 时不调用 fetchCollection', () => {
    render(<CollectionPanel gameId={0} />);
    expect(mockFetchCollection).not.toHaveBeenCalled();
  });
});
