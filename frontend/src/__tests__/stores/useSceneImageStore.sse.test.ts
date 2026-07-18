import { useSceneImageStore } from '@/stores/useSceneImageStore';

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly url: string;
  readonly close = jest.fn();
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  emit(data: object): void {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

const initialState = {
  roundSceneImages: [],
  currentRoundSceneImage: null,
  eventSceneImage: null,
  resultSceneImage: null,
  isLoadingRoundSceneImage: false,
  roundSceneError: null,
  sseConnection: null,
};

describe('useSceneImageStore SSE contracts', () => {
  const originalEventSource = global.EventSource;

  beforeEach(() => {
    FakeEventSource.instances = [];
    Object.defineProperty(global, 'EventSource', {
      configurable: true,
      writable: true,
      value: FakeEventSource,
    });
    useSceneImageStore.getState().unsubscribeFromSceneImageEvents();
    useSceneImageStore.setState(initialState);
  });

  afterEach(() => {
    useSceneImageStore.getState().unsubscribeFromSceneImageEvents();
    Object.defineProperty(global, 'EventSource', {
      configurable: true,
      writable: true,
      value: originalEventSource,
    });
  });

  it('replaces an existing stage image when the matching ready event arrives', () => {
    const oldScene = {
      scene_id: 1,
      week: 3,
      round_number: 2,
      stage: 'event',
      image_url: '/old.png',
      scene_description: 'old scene',
      referenced_images: [],
      created_at: '2026-07-19T00:00:00Z',
    };
    useSceneImageStore.setState({
      roundSceneImages: [oldScene],
      eventSceneImage: oldScene,
      currentRoundSceneImage: oldScene,
      isLoadingRoundSceneImage: true,
      roundSceneError: 'old failure',
    });

    useSceneImageStore.getState().subscribeToSceneImageEvents(41);
    FakeEventSource.instances[0].emit({
      type: 'scene_image_ready',
      game_id: 41,
      week: 3,
      round_number: 2,
      stage: 'event',
      scene_id: 9,
      image_url: '/new.png',
      scene_description: 'new scene',
      timestamp: '2026-07-19T01:00:00Z',
    });

    const state = useSceneImageStore.getState();
    expect(state.roundSceneImages).toHaveLength(1);
    expect(state.roundSceneImages[0]).toMatchObject({ scene_id: 9, image_url: '/new.png' });
    expect(state.eventSceneImage).toMatchObject({ scene_id: 9, stage: 'event' });
    expect(state.currentRoundSceneImage).toMatchObject({ scene_id: 9, stage: 'event' });
    expect(state.isLoadingRoundSceneImage).toBe(false);
    expect(state.roundSceneError).toBeNull();
  });

  it('surfaces a terminal SSE failure without discarding the current image', () => {
    const currentScene = {
      scene_id: 2,
      week: 4,
      round_number: 1,
      stage: 'result',
      image_url: '/current.png',
      scene_description: 'current scene',
      referenced_images: [],
      created_at: '2026-07-19T00:00:00Z',
    };
    useSceneImageStore.setState({
      roundSceneImages: [currentScene],
      resultSceneImage: currentScene,
      isLoadingRoundSceneImage: true,
    });

    useSceneImageStore.getState().subscribeToSceneImageEvents(42);
    FakeEventSource.instances[0].emit({
      type: 'scene_image_failed',
      game_id: 42,
      week: 4,
      round_number: 1,
      stage: 'result',
      code: 'minimax_2056',
      message: '图片生成额度暂时不可用，请稍后再试',
      retryable: false,
      timestamp: '2026-07-19T01:00:00Z',
    });

    const state = useSceneImageStore.getState();
    expect(state.isLoadingRoundSceneImage).toBe(false);
    expect(state.roundSceneError).toBe('图片生成额度暂时不可用，请稍后再试');
    expect(state.resultSceneImage).toBe(currentScene);
    expect(state.roundSceneImages).toEqual([currentScene]);
  });

  it('keeps state unchanged for heartbeat messages', () => {
    useSceneImageStore.setState({
      roundSceneError: 'existing error',
      isLoadingRoundSceneImage: true,
    });

    useSceneImageStore.getState().subscribeToSceneImageEvents(43);
    FakeEventSource.instances[0].emit({
      type: 'heartbeat',
      game_id: 43,
      week: 0,
      round_number: 0,
      stage: 'result',
      timestamp: '2026-07-19T01:00:00Z',
    });

    expect(useSceneImageStore.getState()).toMatchObject({
      isLoadingRoundSceneImage: true,
      roundSceneError: 'existing error',
      roundSceneImages: [],
    });
  });

  it('closes a replaced connection and clears the active connection on unsubscribe', () => {
    useSceneImageStore.getState().subscribeToSceneImageEvents(44);
    const first = FakeEventSource.instances[0];

    useSceneImageStore.getState().subscribeToSceneImageEvents(45);
    const second = FakeEventSource.instances[1];

    expect(first.url).toBe('/api/images/scene/events/44');
    expect(first.close).toHaveBeenCalledTimes(1);
    expect(second.url).toBe('/api/images/scene/events/45');

    useSceneImageStore.getState().unsubscribeFromSceneImageEvents();

    expect(second.close).toHaveBeenCalledTimes(1);
    expect(useSceneImageStore.getState().sseConnection).toBeNull();
  });
});
