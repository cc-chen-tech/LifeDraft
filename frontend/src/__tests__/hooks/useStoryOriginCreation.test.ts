import { act, renderHook, waitFor } from '@testing-library/react';

import { useCharacterCreation } from '@/hooks/useCharacterCreation';
import { useCharacterStore, useGameStore } from '@/stores/useGameStore';
import { useImageStore } from '@/stores/useImageStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

const oldOrigin = {
  revision: 1,
  start_date: '0960-01-01',
  starting_age: 20,
  era_description: '北宋初年',
  life_stage_description: '初入成年',
  world_context: '州城社会',
};

const newOrigin = {
  revision: 2,
  start_date: '2026-08-13',
  starting_age: 28,
  era_description: '2020年代中期的现代都市',
  life_stage_description: '职业发展逐渐进入稳定探索期',
  world_context: 'AI工具与数字内容行业快速变化',
};

function setupDraft() {
  const settings = {
    story_origin: oldOrigin,
    gender: { gender: 'female' },
    world: { description: '旧世界' },
    family: { description: '旧家庭' },
    relationships: { key_people: [{ name: '旧友' }] },
    traits: { personality: ['谨慎'] },
  };
  useCharacterStore.setState({
    creationStep: 0,
    characterSettings: settings,
    playerName: '阿衡',
    lifeVision: '建立长久事业',
    isPresetLoaded: false,
  } as never);
  useGameStore.setState({
    creationStep: 0,
    characterSettings: settings,
    playerName: '阿衡',
    lifeVision: '建立长久事业',
    gameId: 42,
  } as never);
  useImageStore.setState({
    playerImages: [{ image_id: 7, image_url: '/old.png' }],
    playerImage: { image_id: 7, image_url: '/old.png' },
    selectedImageIndex: 0,
  } as never);
}

describe('story-origin creation flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupDraft();
  });

  it('commits the whole candidate with expected revision and invalidates descendants', async () => {
    global.fetch = jest.fn(async (input: string | URL) => {
      const url = String(input);
      if (url === '/api/character/story-origin') return jsonResponse(newOrigin);
      if (url === '/api/games/42/story-origin') {
        return jsonResponse({
          success: true,
          story_origin: newOrigin,
          timeline: { version: 2, start_date: newOrigin.start_date, current_date: newOrigin.start_date, day_index: 0 },
          character_settings: {
            story_origin: newOrigin,
            gender: { gender: 'female' },
            start_date: newOrigin.start_date,
          },
        });
      }
      throw new Error(`unexpected request ${url}`);
    }) as jest.Mock;

    const { result } = renderHook(() => useCharacterCreation());
    await act(async () => result.current.handleGenerate('改为2026年，28岁'));
    await waitFor(() => expect(result.current.generatedContent).toEqual(newOrigin));
    await act(async () => result.current.handleAcceptAndNext());

    const patchCall = (global.fetch as jest.Mock).mock.calls.find(
      ([url]) => url === '/api/games/42/story-origin',
    );
    expect(JSON.parse(patchCall[1].body)).toEqual({
      expected_revision: 1,
      story_origin: newOrigin,
    });
    expect(useGameStore.getState().characterSettings).toEqual({
      story_origin: newOrigin,
      gender: { gender: 'female' },
      start_date: newOrigin.start_date,
    });
    expect(useGameStore.getState().creationStep).toBe(2);
    expect(useImageStore.getState().playerImages).toEqual([]);
  });

  it('discards a late origin candidate after identity input changes', async () => {
    let resolveResponse!: (value: Response) => void;
    global.fetch = jest.fn(() => new Promise<Response>((resolve) => {
      resolveResponse = resolve;
    })) as jest.Mock;

    const { result } = renderHook(() => useCharacterCreation());
    let request!: Promise<void>;
    act(() => {
      request = result.current.handleGenerate();
    });
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    act(() => result.current.setPlayerName('新名字'));
    resolveResponse(jsonResponse(newOrigin));
    await act(async () => request);

    expect(result.current.generatedContent).toBeNull();
  });
});
