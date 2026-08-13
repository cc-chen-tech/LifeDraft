import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CollectionPanel } from '@/components/game/CollectionPanel';
import { useCollectionStore } from '@/stores/useCollectionStore';

const item = {
  name: '旧怀表',
  description: '祖父留下的旧物。',
  importance: 'important' as const,
  category: 'keepsake' as const,
  acquired_week: 2,
  acquired_context: '书房抽屉',
  is_key_item: true,
  image_url: '/watch.png',
  image_generated: true,
  description_generated: true,
  metadata: {},
};

const pendingLandmark = {
  name: '旧码头',
  description: '',
  category: 'area' as const,
  importance: 'normal' as const,
  first_appear_week: 1,
  appear_count: 2,
  last_appear_week: 2,
  context: '雨夜会面地点',
  is_key_location: false,
  image_url: null,
  image_generated: false,
  metadata: {},
};

const originalActions: Record<string, unknown> = {};
const actionNames = [
  'fetchCollection',
  'autoCollectRecognizedEntities',
  'regenerateItemImage',
  'deleteItem',
  'batchGenerateLandmarkImages',
  'clearError',
];

function fixtureStore(overrides: Record<string, unknown> = {}): void {
  const state = useCollectionStore.getState() as unknown as Record<string, unknown>;
  for (const actionName of actionNames) {
    originalActions[actionName] = state[actionName];
    state[actionName] = jest.fn().mockResolvedValue(undefined);
  }

  useCollectionStore.setState({
    characters: [
      {
        name: '林舟',
        role: '主角',
        description: '',
        affinity: 100,
        age: null,
        gender: null,
        occupation: null,
        personality_traits: [],
        image_url: null,
        image_generated: false,
        description_generated: true,
      },
      {
        name: '陈晓雨',
        role: '同事',
        description: '',
        affinity: 70,
        age: null,
        gender: null,
        occupation: null,
        personality_traits: [],
        image_url: null,
        image_generated: false,
        description_generated: true,
      },
    ],
    items: [item],
    landmarks: [],
    isLoading: false,
    isRefreshing: false,
    activeTab: 'items',
    selectedCharacter: null,
    selectedItem: item,
    selectedLandmark: null,
    generatingImageFor: null,
    generatingDescriptionFor: null,
    regeneratingImageFor: null,
    error: null,
    isRecognizing: false,
    recognizedEntities: null,
    isDeleting: false,
    deletingEntity: null,
    ...overrides,
  });
}

function actionMock(name: string): jest.Mock {
  return (useCollectionStore.getState() as unknown as Record<string, jest.Mock>)[name];
}

async function renderPanel(gameId: number) {
  const result = render(<CollectionPanel gameId={gameId} />);
  await waitFor(() => {
    expect(actionMock('fetchCollection')).toHaveBeenCalledWith(gameId);
  });
  return result;
}

describe('CollectionPanel action contracts', () => {
  beforeEach(() => {
    fixtureStore();
  });

  afterEach(() => {
    const state = useCollectionStore.getState() as unknown as Record<string, unknown>;
    for (const actionName of actionNames) {
      state[actionName] = originalActions[actionName];
    }
  });

  it('submits trimmed feedback for the selected item image regeneration', async () => {
    await renderPanel(71);

    fireEvent.click(screen.getByRole('button', { name: '修改图片' }));
    fireEvent.change(
      screen.getByPlaceholderText('输入修改意见，例如：颜色改深一点、增加细节...'),
      { target: { value: '  金色边框更清晰  ' } },
    );
    fireEvent.click(screen.getByRole('button', { name: '提交修改' }));

    await waitFor(() => {
      expect(actionMock('regenerateItemImage')).toHaveBeenCalledWith(
        71,
        '旧怀表',
        '金色边框更清晰',
      );
    });
  });

  it('routes confirmed item deletion to the selected store action', async () => {
    await renderPanel(72);
    const deleteButton = screen
      .getByRole('dialog', { name: '旧怀表' })
      .querySelector('button[data-variant="ghost"]');

    expect(deleteButton).toBeDefined();
    fireEvent.click(deleteButton as HTMLButtonElement);
    fireEvent.click(screen.getByRole('button', { name: '删除' }));

    await waitFor(() => {
      expect(actionMock('deleteItem')).toHaveBeenCalledWith(72, '旧怀表');
    });
  });

  it('runs the landmark batch action only when the landmarks tab exposes pending images', async () => {
    fixtureStore({
      activeTab: 'landmarks',
      items: [],
      landmarks: [pendingLandmark],
      selectedItem: null,
    });
    await renderPanel(73);

    fireEvent.click(screen.getByRole('button', { name: '批量生成图片' }));

    await waitFor(() => {
      expect(actionMock('batchGenerateLandmarkImages')).toHaveBeenCalledWith(73);
    });
  });

  it('exposes the visible error close action', async () => {
    fixtureStore({
      error: '图片生成额度暂时不可用，请稍后再试',
      selectedItem: null,
    });
    await renderPanel(74);

    fireEvent.click(screen.getByRole('button', { name: '关闭收集错误' }));

    expect(actionMock('clearError')).toHaveBeenCalledTimes(1);
  });
});
