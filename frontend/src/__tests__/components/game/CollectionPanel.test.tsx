/**
 * CollectionPanel component tests — useEffect fetchCollection call count verification
 * Uses real useCollectionStore with setState, only mocks child components
 */
import React from 'react';
import { render } from '@testing-library/react';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';

// Mock child components to isolate fetchCollection behavior
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

function replaceStoreMethods() {
  const store = useCollectionStore.getState() as Record<string, unknown>;
  const originals: Record<string, Function> = {};
  const keys = ['fetchCollection'];
  for (const key of keys) {
    originals[key] = store[key] as Function;
    store[key] = jest.fn().mockResolvedValue(undefined);
  }
  return originals;
}

function restoreStoreMethods(originals: Record<string, Function>) {
  const store = useCollectionStore.getState() as Record<string, unknown>;
  for (const [key, fn] of Object.entries(originals)) {
    store[key] = fn;
  }
}

function getFetchCollectionMock(): jest.Mock {
  return useCollectionStore.getState().fetchCollection as unknown as jest.Mock;
}

describe('CollectionPanel', () => {
  let originals: Record<string, Function>;

  beforeEach(() => {
    setupDefaultState();
    originals = replaceStoreMethods();
  });

  afterEach(() => {
    restoreStoreMethods(originals);
  });

  it('initial mount calls fetchCollection exactly once', () => {
    render(<CollectionPanel gameId={1} />);
    expect(getFetchCollectionMock()).toHaveBeenCalledTimes(1);
    expect(getFetchCollectionMock()).toHaveBeenCalledWith(1);
  });

  it('same gameId re-render does not trigger extra request', () => {
    const { rerender } = render(<CollectionPanel gameId={1} />);
    expect(getFetchCollectionMock()).toHaveBeenCalledTimes(1);

    rerender(<CollectionPanel gameId={1} />);
    expect(getFetchCollectionMock()).toHaveBeenCalledTimes(1);
  });

  it('gameId change triggers re-fetch', () => {
    const { rerender } = render(<CollectionPanel gameId={1} />);
    expect(getFetchCollectionMock()).toHaveBeenCalledTimes(1);

    rerender(<CollectionPanel gameId={2} />);
    expect(getFetchCollectionMock()).toHaveBeenCalledTimes(2);
    expect(getFetchCollectionMock()).toHaveBeenLastCalledWith(2);
  });

  it('gameId 0 does not call fetchCollection', () => {
    render(<CollectionPanel gameId={0} />);
    expect(getFetchCollectionMock()).not.toHaveBeenCalled();
  });
});
