import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
  'createCharacter',
  'createItem',
  'createLandmark',
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
        can_delete: false,
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
        can_delete: true,
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

  it.each([
    ['characters', '添加人物', '新人物', 'createCharacter'],
    ['items', '添加物品', '新物品', 'createItem'],
    ['landmarks', '添加标志物', '新地点', 'createLandmark'],
  ] as const)('adds from the %s tab through %s', async (tab, buttonName, name, action) => {
    const user = userEvent.setup();
    fixtureStore({
      activeTab: tab,
      items: tab === 'items' ? [item] : [],
      landmarks: tab === 'landmarks' ? [pendingLandmark] : [],
      selectedItem: null,
    });
    actionMock(action).mockResolvedValue(true);

    await renderPanel(75);
    await user.click(screen.getByRole('button', { name: buttonName }));
    await user.type(screen.getByRole('textbox', { name: /名称/ }), name);
    await user.click(screen.getByRole('button', { name: '添加' }));

    if (action === 'createItem') {
      expect(actionMock(action)).toHaveBeenCalledWith(75, name, true);
    } else {
      expect(actionMock(action)).toHaveBeenCalledWith(75, name);
    }
  });

  it('shows history description extraction only while adding an item', async () => {
    const user = userEvent.setup();
    fixtureStore({ activeTab: 'items', selectedItem: null });
    await renderPanel(76);

    await user.click(screen.getByRole('button', { name: '添加物品' }));
    expect(screen.getByRole('checkbox', { name: '从故事历史中提取描述' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: '取消' }));

    fireEvent.click(screen.getByRole('tab', { name: /人物/ }));
    await user.click(screen.getByRole('button', { name: '添加人物' }));
    expect(screen.queryByRole('checkbox', { name: '从故事历史中提取描述' })).not.toBeInTheDocument();
  });

  it.each([
    ['档案/A', '名称不能包含 /'],
    ['A%20B', '名称不能包含 %'],
    ['.', '名称不能是 . 或 ..'],
    ['..', '名称不能是 . 或 ..'],
    [' . ', '名称不能是 . 或 ..'],
    [' .. ', '名称不能是 . 或 ..'],
  ])('blocks the name %s because it cannot round-trip through deletion routes', async (name, message) => {
    const user = userEvent.setup();
    fixtureStore({ activeTab: 'characters', selectedItem: null });
    await renderPanel(76);

    await user.click(screen.getByRole('button', { name: '添加人物' }));
    const dialog = screen.getByRole('dialog', { name: '添加人物' });
    await user.type(within(dialog).getByRole('textbox', { name: '人物名称' }), name);

    expect(within(dialog).getByText(message)).toBeVisible();
    expect(within(dialog).getByRole('button', { name: '添加' })).toBeDisabled();
    expect(actionMock('createCharacter')).not.toHaveBeenCalled();
  });

  it('allows dots inside an ordinary entity name', async () => {
    const user = userEvent.setup();
    fixtureStore({ activeTab: 'characters', selectedItem: null });
    actionMock('createCharacter').mockResolvedValue(true);
    await renderPanel(76);

    await user.click(screen.getByRole('button', { name: '添加人物' }));
    const dialog = screen.getByRole('dialog', { name: '添加人物' });
    await user.type(within(dialog).getByRole('textbox', { name: '人物名称' }), 'A.B');

    expect(within(dialog).queryByText(/名称不能/)).not.toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: '添加' })).toBeEnabled();
    await user.click(within(dialog).getByRole('button', { name: '添加' }));
    expect(actionMock('createCharacter')).toHaveBeenCalledWith(76, 'A.B');
  });

  it('only offers deletion for materialized characters', async () => {
    const user = userEvent.setup();
    fixtureStore({
      activeTab: 'characters',
      selectedItem: null,
      characters: [
        {
          name: '林舟', role: '主角', can_delete: false, description: '', affinity: 100,
          age: null, gender: null, occupation: null, personality_traits: [], image_url: null,
          image_generated: false, description_generated: true,
        },
        {
          name: '陈晓雨', role: '同事', can_delete: true, description: '', affinity: 70,
          age: null, gender: null, occupation: null, personality_traits: [], image_url: null,
          image_generated: false, description_generated: true,
        },
        {
          name: '母亲', role: '母亲', can_delete: false, description: '家人', affinity: 80,
          age: null, gender: null, occupation: null, personality_traits: [], image_url: null,
          image_generated: false, description_generated: true,
        },
      ],
    });
    await renderPanel(76);

    expect(screen.getByRole('button', { name: '删除人物陈晓雨' })).toBeVisible();
    expect(screen.queryByRole('button', { name: '删除人物母亲' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '查看人物：母亲' }));
    const detail = screen.getByRole('dialog', { name: '母亲' });
    expect(within(detail).queryByRole('button', { name: '删除人物母亲' })).not.toBeInTheDocument();
  });

  it('keeps a failed manual addition open with its name and error visible', async () => {
    const user = userEvent.setup();
    fixtureStore({ activeTab: 'characters', selectedItem: null });
    actionMock('createCharacter').mockImplementation(async () => {
      useCollectionStore.setState({ error: '人物名称已存在，请换一个名称' });
      return false;
    });
    await renderPanel(77);

    await user.click(screen.getByRole('button', { name: '添加人物' }));
    const dialog = screen.getByRole('dialog', { name: '添加人物' });
    const input = within(dialog).getByRole('textbox', { name: '人物名称' });
    await user.type(input, '林舟');
    await user.click(within(dialog).getByRole('button', { name: '添加' }));

    await waitFor(() => expect(actionMock('createCharacter')).toHaveBeenCalledWith(77, '林舟'));
    expect(screen.getByRole('dialog', { name: '添加人物' })).toBeVisible();
    expect(within(screen.getByRole('dialog', { name: '添加人物' })).getByRole('textbox', { name: '人物名称' })).toHaveValue('林舟');
    expect(within(screen.getByRole('dialog', { name: '添加人物' })).getByRole('alert')).toHaveTextContent('人物名称已存在，请换一个名称');
  });

  it('closes after persisted creation while retaining refresh feedback without resubmitting', async () => {
    const user = userEvent.setup();
    fixtureStore({ activeTab: 'characters', selectedItem: null });
    actionMock('createCharacter').mockImplementation(async () => {
      useCollectionStore.setState({ error: '人物已保存，但列表同步失败；无需重复添加' });
      return true;
    });
    await renderPanel(78);

    await user.click(screen.getByRole('button', { name: '添加人物' }));
    const dialog = screen.getByRole('dialog', { name: '添加人物' });
    await user.type(within(dialog).getByRole('textbox', { name: '人物名称' }), '陈舟');
    await user.click(within(dialog).getByRole('button', { name: '添加' }));

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '添加人物' })).not.toBeInTheDocument());
    expect(actionMock('createCharacter')).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('alert')).toHaveTextContent('人物已保存，但列表同步失败；无需重复添加');
    expect(actionMock('clearError')).toHaveBeenCalledTimes(1);
  });

  it('closes after persisted deletion while retaining refresh feedback without repeating deletion', async () => {
    const user = userEvent.setup();
    fixtureStore({ activeTab: 'items', selectedItem: null });
    actionMock('deleteItem').mockImplementation(async () => {
      useCollectionStore.setState({ error: '实体已删除，但列表同步失败；无需重复删除' });
      return true;
    });
    await renderPanel(79);

    await user.click(screen.getByRole('button', { name: '删除物品旧怀表' }));
    await user.click(
      within(screen.getByRole('dialog', { name: '确认删除' })).getByRole('button', { name: '删除' }),
    );

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '确认删除' })).not.toBeInTheDocument());
    expect(actionMock('deleteItem')).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('alert')).toHaveTextContent('实体已删除，但列表同步失败；无需重复删除');
  });
});
