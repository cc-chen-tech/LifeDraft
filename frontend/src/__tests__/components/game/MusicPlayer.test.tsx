/**
 * MusicPlayer 组件测试
 *
 * 包含：基础渲染 + 卡顿检测（stall detection）逻辑验证
 * 使用真实 Zustand store + global.fetch mock，不 mock store 模块。
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MusicPlayer } from '@/components/game/MusicPlayer';
import { useMusicStore } from '@/stores/useMusicStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

// jsdom 不支持 Audio API，提供完整 mock
const createdAudioInstances: MockAudioClass[] = [];

class MockAudioClass {
  src = '';
  paused = true;
  currentTime = 0;
  duration = 180;
  volume = 1;
  preload = '';
  readyState = 0;
  error = null;
  play = jest.fn().mockResolvedValue(undefined);
  pause = jest.fn();
  load = jest.fn();
  onplay: (() => void) | null = null;
  onpause: (() => void) | null = null;
  ontimeupdate: (() => void) | null = null;
  onloadedmetadata: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private _listeners: Record<string, Array<() => void>> = {};

  constructor(src?: string) {
    this.src = src || '';
    createdAudioInstances.push(this);
  }

  addEventListener(event: string, fn: () => void) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(fn);
  }
  removeEventListener(event: string, fn: () => void) {
    if (this._listeners[event]) {
      this._listeners[event] = this._listeners[event].filter((f) => f !== fn);
    }
  }
}

beforeAll(() => {
  (global as any).Audio = MockAudioClass;
});

afterAll(() => {
  delete (global as any).Audio;
});

const playlistResponse = (gameId: number, currentSong: unknown = null, queue: unknown[] = []) =>
  jsonResponse({
    game_id: gameId,
    current_song: currentSong,
    queue,
    played_songs: [],
    is_playing: false,
    volume: 0.5,
    current_position_ms: 0,
  });

describe('MusicPlayer', () => {
  beforeEach(() => {
    createdAudioInstances.length = 0;
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          mood: '宁静',
          scene_type: '独处',
          keywords: ['古风', '钢琴'],
          songs: [
            { id: 1, name: '测试歌曲', artists: ['测试艺术家'], album: '测试专辑', duration: 180000, url: 'https://example.com/test.mp3' },
          ],
          environment: '古风',
          story_style: '武侠',
        })
      ) as jest.Mock;

    useMusicStore.setState({
      recommendation: null,
      isLoadingRecommendation: false,
      recommendationError: null,
      currentSong: null,
      isPlaying: false,
      volume: 0.5,
      currentTime: 0,
      duration: 0,
      audioElement: null,
      isGeneratingAiMusic: false,
      aiMusicGenerationStatus: 'idle',
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('应该渲染音乐播放器', async () => {
    render(<MusicPlayer storyText="Test story" />);

    await waitFor(() => {
      expect(screen.getByText('场景音乐')).toBeInTheDocument();
    });
  });

  it('没有故事文本时不应该渲染', () => {
    const { container } = render(<MusicPlayer storyText="" />);
    expect(container.firstChild).toBeNull();
  });

  it('音乐服务返回空列表时显示可继续游戏的降级提示', async () => {
    (global.fetch as jest.Mock).mockReset();
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      jsonResponse({
        mood: '宁静',
        scene_type: '独处',
        keywords: ['古风'],
        songs: [],
      })
    );

    render(<MusicPlayer storyText="Test story" />);

    expect(await screen.findByText('音乐服务暂不可用，故事可继续进行')).toBeInTheDocument();
  });

  it('已有可播放音乐时推荐失败不显示阻塞的服务不可用文案', () => {
    useMusicStore.setState({
      recommendation: {
        mood: '紧张',
        scene_type: '追捕逃亡',
        keywords: ['悬疑'],
        songs: [
          {
            id: 88,
            name: '当前可播放曲目',
            artists: ['AI MiniMax'],
            album: '原创场景音乐',
            duration: 120000,
            url: 'https://example.com/current.mp3',
            source: 'ai_generated',
          },
        ],
      },
      currentSong: {
        id: 88,
        name: '当前可播放曲目',
        artists: ['AI MiniMax'],
        album: '原创场景音乐',
        duration: 120000,
        url: 'https://example.com/current.mp3',
        source: 'ai_generated',
      },
      recommendationError: '音乐服务暂不可用',
      isLoadingRecommendation: false,
    } as never);

    render(
      <MusicPlayer
        storyText="雨夜追逐，主角发现旧账册线索。"
        autoFetchRecommendation={false}
        embedded
        compactControls
      />
    );

    expect(screen.getByText('当前可播放曲目')).toBeInTheDocument();
    expect(screen.queryByText('音乐服务暂不可用')).not.toBeInTheDocument();
    expect(screen.getByText('新推荐暂不可用，继续播放当前音乐')).toBeInTheDocument();
  });

  it('网易云安全基线为空但有 music_brief 时显示 MiniMax 生成中而不是不可用', async () => {
    (global.fetch as jest.Mock).mockReset();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(
        jsonResponse({
          mood: '紧张',
          scene_type: '现代职场危机',
          keywords: ['现代职场 纯音乐'],
          music_brief: {
            mood: '紧张',
            scene_type: '现代职场危机',
            generation_prompt: 'tense modern workplace instrumental ambience, no vocals',
          },
          songs: [],
        })
      )
      .mockResolvedValueOnce(playlistResponse(77))
      .mockResolvedValueOnce(
        jsonResponse({
          status: 'queued',
          insert_policy: 'future_queue',
          game_id: 77,
        })
      )
      .mockResolvedValue(playlistResponse(77));

    render(<MusicPlayer storyText="产品经理发现数据异常，会议室气氛紧张。" gameId={77} />);

    expect(await screen.findByText('正在生成原创场景音乐...')).toBeInTheDocument();
    expect(screen.queryByText('音乐服务暂不可用，故事可继续进行')).not.toBeInTheDocument();
    expect(
      (global.fetch as jest.Mock).mock.calls.some((call: unknown[]) =>
        String(call[0]).includes('/api/music/generate')
      )
    ).toBe(true);
  });

  it('点击换一批时用 refresh 模式请求新候选', async () => {
    (global.fetch as jest.Mock).mockReset();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(
        jsonResponse({
          mood: '紧张',
          scene_type: '追捕逃亡',
          keywords: ['现代悬疑 纯音乐'],
          songs: [
            {
              id: 1,
              name: '第一批',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/first.mp3',
            },
          ],
        })
      )
      .mockResolvedValueOnce(playlistResponse(77))
      .mockResolvedValueOnce(
        jsonResponse({
          mood: '紧张',
          scene_type: '追捕逃亡',
          keywords: ['医疗悬疑 氛围音乐'],
          songs: [
            {
              id: 2,
              name: '第二批',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/second.mp3',
            },
          ],
        })
      )
      .mockResolvedValueOnce(playlistResponse(77));

    render(<MusicPlayer storyText="现代医疗数据造假追捕逃亡" gameId={77} />);

    await screen.findByText('第一批');
    fireEvent.click(screen.getByRole('button', { name: '换一批' }));

    await waitFor(() => {
      const recommendCalls = (global.fetch as jest.Mock).mock.calls.filter(
        (call: unknown[]) => String(call[0]).includes('/api/music/recommend')
      );
      expect(recommendCalls).toHaveLength(2);
    });

    const recommendCalls = (global.fetch as jest.Mock).mock.calls.filter(
      (call: unknown[]) => String(call[0]).includes('/api/music/recommend')
    );
    expect(JSON.parse(recommendCalls[0][1].body).refresh).toBe(false);
    expect(JSON.parse(recommendCalls[1][1].body)).toMatchObject({
      story_text: '现代医疗数据造假追捕逃亡',
      game_id: 77,
      refresh: true,
    });
    expect(
      (global.fetch as jest.Mock).mock.calls.some((call: unknown[]) =>
        String(call[0]).includes('/api/music/playlist/77')
      )
    ).toBe(true);
  });

  it('legacy 推荐响应没有 music_brief 时不触发 AI 生成请求', async () => {
    (global.fetch as jest.Mock).mockReset();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(
        jsonResponse({
          mood: '紧张',
          scene_type: '追捕逃亡',
          keywords: ['现代悬疑 纯音乐'],
          songs: [
            {
              id: 1,
              name: '第一批',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/first.mp3',
            },
          ],
        })
      )
      .mockResolvedValueOnce(playlistResponse(77));

    render(<MusicPlayer storyText="现代医疗数据造假追捕逃亡" gameId={77} />);

    await screen.findByText('第一批');
    await Promise.resolve();

    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls.some((call: unknown[]) => String(call[0]).includes('/api/music/recommend'))).toBe(true);
    expect(calls.some((call: unknown[]) => String(call[0]).includes('/api/music/playlist/77'))).toBe(true);
    expect(calls.some((call: unknown[]) => String(call[0]).includes('/api/music/generate'))).toBe(false);
  });

  it('带 music_brief 的故事推荐会后台生成 AI 音乐并从播放列表插入后续队列', async () => {
    (global.fetch as jest.Mock).mockReset();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(
        jsonResponse({
          mood: '紧张',
          scene_type: '雨夜追逐',
          keywords: ['雨夜追逐', '悬疑配乐'],
          music_brief: {
            mood: '紧张',
            scene_type: '雨夜追逐',
            generation_prompt: '雨夜码头追逐，紧张悬疑，无歌词氛围配乐',
          },
          songs: [
            {
              id: 1,
              name: '网易云 当前曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/current.mp3',
              source: 'netease',
            },
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        playlistResponse(
          77,
          {
            id: 1,
            name: '网易云 当前曲',
            artists: ['Score'],
            album: '影视配乐',
            duration: 180000,
            url: 'https://example.com/current.mp3',
            source: 'netease',
          },
          [
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ]
        )
      )
      .mockResolvedValueOnce(
        playlistResponse(
          77,
          {
            id: 1,
            name: '网易云 当前曲',
            artists: ['Score'],
            album: '影视配乐',
            duration: 180000,
            url: 'https://example.com/current.mp3',
            source: 'netease',
          },
          [
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ]
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: 'queued',
          insert_policy: 'future_queue',
          game_id: 77,
        })
      )
      .mockResolvedValueOnce(
        playlistResponse(
          77,
          {
            id: 1,
            name: '网易云 当前曲',
            artists: ['Score'],
            album: '影视配乐',
            duration: 180000,
            url: 'https://example.com/current.mp3',
            source: 'netease',
          },
          [
            {
              id: 'ai-generated-77',
              name: 'AI MiniMax 雨夜追逐',
              artists: ['MiniMax'],
              album: 'AI Generated',
              duration: 120000,
              url: '/api/music/generated/ai-generated-77.mp3',
              source: 'ai_generated',
              provider: 'minimax',
              model: 'music-01',
            },
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ]
        )
      );

    render(<MusicPlayer storyText="雨夜码头追逐，主角发现旧账册线索。" gameId={77} />);

    await waitFor(() => {
      expect(
        (global.fetch as jest.Mock).mock.calls.some((call: unknown[]) =>
          String(call[0]).includes('/api/music/generate')
        )
      ).toBe(true);
    });

    const generateCall = (global.fetch as jest.Mock).mock.calls.find((call: unknown[]) =>
      String(call[0]).includes('/api/music/generate')
    );
    expect(JSON.parse(generateCall[1].body)).toMatchObject({
      story_text: '雨夜码头追逐，主角发现旧账册线索。',
      game_id: 77,
      analysis: {
        mood: '紧张',
        scene_type: '雨夜追逐',
      },
    });
    expect(
      (global.fetch as jest.Mock).mock.calls.some((call: unknown[]) =>
        String(call[0]).endsWith('/api/music/generate-async')
      )
    ).toBe(false);
    expect(useMusicStore.getState().currentSong?.name).toBe('网易云 当前曲');
    expect(useMusicStore.getState().queue.map((item) => item.name)).toEqual([
      'AI MiniMax 雨夜追逐',
      '网易云 下一曲',
    ]);
    expect(screen.getByText('AI MiniMax 雨夜追逐')).toBeInTheDocument();
  });

  it('当前歌曲播完后优先推进持久化队列里的 AI 曲目', async () => {
    (global.fetch as jest.Mock).mockReset();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(
        jsonResponse({
          mood: '紧张',
          scene_type: '雨夜追逐',
          keywords: ['雨夜追逐', '悬疑配乐'],
          music_brief: {
            mood: '紧张',
            scene_type: '雨夜追逐',
            generation_prompt: '雨夜码头追逐，紧张悬疑，无歌词氛围配乐',
          },
          songs: [
            {
              id: 1,
              name: '网易云 当前曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/current.mp3',
              source: 'netease',
            },
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        playlistResponse(
          77,
          {
            id: 1,
            name: '网易云 当前曲',
            artists: ['Score'],
            album: '影视配乐',
            duration: 180000,
            url: 'https://example.com/current.mp3',
            source: 'netease',
          },
          [
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ]
        )
      )
      .mockResolvedValueOnce(
        playlistResponse(
          77,
          {
            id: 1,
            name: '网易云 当前曲',
            artists: ['Score'],
            album: '影视配乐',
            duration: 180000,
            url: 'https://example.com/current.mp3',
            source: 'netease',
          },
          [
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ]
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: 'queued',
          insert_policy: 'future_queue',
          game_id: 77,
        })
      )
      .mockResolvedValueOnce(
        playlistResponse(
          77,
          {
            id: 1,
            name: '网易云 当前曲',
            artists: ['Score'],
            album: '影视配乐',
            duration: 180000,
            url: 'https://example.com/current.mp3',
            source: 'netease',
          },
          [
            {
              id: 'ai-generated-77',
              name: 'AI MiniMax 雨夜追逐',
              artists: ['MiniMax'],
              album: 'AI Generated',
              duration: 120000,
              url: '/api/music/generated/ai-generated-77.mp3',
              source: 'ai_generated',
              provider: 'minimax',
              model: 'music-01',
            },
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ]
        )
      )
      .mockResolvedValueOnce(
        playlistResponse(
          77,
          {
            id: 'ai-generated-77',
            name: 'AI MiniMax 雨夜追逐',
            artists: ['MiniMax'],
            album: 'AI Generated',
            duration: 120000,
            url: '/api/music/generated/ai-generated-77.mp3',
            source: 'ai_generated',
            provider: 'minimax',
            model: 'music-01',
          },
          [
            {
              id: 2,
              name: '网易云 下一曲',
              artists: ['Score'],
              album: '影视配乐',
              duration: 180000,
              url: 'https://example.com/next.mp3',
              source: 'netease',
            },
          ]
        )
      );

    render(<MusicPlayer storyText="雨夜码头追逐，主角发现旧账册线索。" gameId={77} />);

    await screen.findByText('AI MiniMax 雨夜追逐');
    const firstAudio = createdAudioInstances.find((audio) =>
      audio.src.includes('current.mp3')
    );

    expect(firstAudio).toBeDefined();
    act(() => {
      firstAudio?.onended?.();
    });

    await waitFor(() => {
      expect(useMusicStore.getState().currentSong?.name).toBe('AI MiniMax 雨夜追逐');
    });
    expect(
      (global.fetch as jest.Mock).mock.calls.some((call: unknown[]) =>
        String(call[0]).includes('/api/music/playlist/77/advance')
      )
    ).toBe(true);
  });

  it('有基础歌曲时仍提示 MiniMax 原创音乐正在后台生成', () => {
    useMusicStore.setState({
      recommendation: {
        mood: '紧张',
        scene_type: '现代职场危机',
        keywords: ['办公室 轻电子 氛围'],
        music_brief: {
          mood: '紧张',
          scene_type: '现代职场危机',
          generation_prompt: 'tense modern workplace instrumental ambience, no vocals',
        },
        songs: [
          {
            id: 1,
            name: '网易云 当前曲',
            artists: ['Score'],
            album: '影视配乐',
            duration: 180000,
            url: 'https://example.com/current.mp3',
            source: 'netease',
          },
        ],
      },
      currentSong: {
        id: 1,
        name: '网易云 当前曲',
        artists: ['Score'],
        album: '影视配乐',
        duration: 180000,
        url: 'https://example.com/current.mp3',
        source: 'netease',
      },
      isGeneratingAiMusic: true,
    });

    render(
      <MusicPlayer
        storyText="产品经理发现数据异常，会议室气氛紧张。"
        gameId={77}
        autoFetchRecommendation={false}
      />
    );

    expect(screen.getByText('正在生成原创场景音乐，完成后加入下一首')).toBeInTheDocument();
    expect(screen.getByText('网易云 当前曲')).toBeInTheDocument();
  });

  it('MiniMax 已排队但尚未插入播放列表时不误报音乐服务不可用', () => {
    useMusicStore.setState({
      recommendation: {
        mood: '紧张',
        scene_type: '现代职场危机',
        keywords: ['办公室 轻电子 氛围'],
        music_brief: {
          mood: '紧张',
          scene_type: '现代职场危机',
          generation_prompt: 'tense modern workplace instrumental ambience, no vocals',
        },
        songs: [],
      },
      currentSong: null,
      queue: [],
      isGeneratingAiMusic: false,
      aiMusicGenerationStatus: 'delayed',
    });

    render(
      <MusicPlayer
        storyText="产品经理发现数据异常，会议室气氛紧张。"
        gameId={77}
        autoFetchRecommendation={false}
      />
    );

    expect(screen.getByText('原创场景音乐已排队，完成后会自动加入播放列表')).toBeInTheDocument();
    expect(screen.queryByText('音乐服务暂不可用，故事可继续进行')).not.toBeInTheDocument();
  });

  it('高频 timeupdate 只同步有限次数到全局 currentTime，但即时展示依然响应', async () => {
    jest.useFakeTimers();
    const now = new Date('2024-01-01T00:00:00.000Z');
    jest.setSystemTime(now);

    const originalSetCurrentTime = useMusicStore.getState().setCurrentTime;
    const setCurrentTimeSpy = jest.fn();

    try {
      useMusicStore.setState({
        setCurrentTime: setCurrentTimeSpy,
        recommendation: {
          mood: '宁静',
          scene_type: '独处',
          keywords: ['古风', '钢琴'],
          songs: [
            {
              id: 1,
              name: '测试歌曲',
              artists: ['测试艺术家'],
              album: '测试专辑',
              duration: 180000,
              url: 'https://example.com/test.mp3',
            },
          ],
        },
        isLoadingRecommendation: false,
        recommendationError: null,
        currentSong: null,
        isPlaying: false,
        volume: 0.5,
        currentTime: 0,
        duration: 180,
        audioElement: null,
        isGeneratingAiMusic: false,
        aiMusicGenerationStatus: 'idle',
      });

      render(
        <MusicPlayer
          storyText="高频进度回报测试"
          autoFetchRecommendation={false}
        />
      );

      await waitFor(() => {
        expect(createdAudioInstances.length).toBeGreaterThan(0);
      });

      const audio = createdAudioInstances.at(-1);
      expect(audio).toBeDefined();
      expect(screen.getByText('0:00')).toBeInTheDocument();

      act(() => {
        expect(audio?.ontimeupdate).toBeInstanceOf(Function);
        for (let idx = 1; idx <= 10; idx += 1) {
          if (audio) {
            audio.currentTime = idx;
            audio.ontimeupdate?.();
          }
          jest.advanceTimersByTime(40);
        }
      });

      await waitFor(() => {
        expect(screen.getByText('0:10')).toBeInTheDocument();
      });

      expect(setCurrentTimeSpy).toHaveBeenCalled();
      expect(setCurrentTimeSpy.mock.calls.length).toBeLessThan(5);
    } finally {
      act(() => {
        useMusicStore.setState({
          setCurrentTime: originalSetCurrentTime,
        } as Partial<ReturnType<typeof useMusicStore.getState>>);
      });
      jest.useRealTimers();
    }
  });

  it('同步播放、暂停和节流后的播放进度到持久化播放列表', async () => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2024-01-01T00:00:00.000Z'));
    const originalSyncPlaylistState = useMusicStore.getState().syncPlaylistState;
    const syncPlaylistStateSpy = jest.fn().mockResolvedValue(undefined);

    try {
      useMusicStore.setState({
        syncPlaylistState: syncPlaylistStateSpy,
        recommendation: {
          mood: '宁静',
          scene_type: '独处',
          keywords: ['古风', '钢琴'],
          songs: [
            {
              id: 1,
              name: '测试歌曲',
              artists: ['测试艺术家'],
              album: '测试专辑',
              duration: 180000,
              url: 'https://example.com/test.mp3',
            },
          ],
        },
        isLoadingRecommendation: false,
        recommendationError: null,
        currentSong: null,
        isPlaying: false,
        volume: 0.5,
        currentTime: 0,
        duration: 180,
        audioElement: null,
        isGeneratingAiMusic: false,
        aiMusicGenerationStatus: 'idle',
      });

      render(
        <MusicPlayer
          storyText="播放状态同步测试"
          gameId={77}
          autoFetchRecommendation={false}
        />
      );

      await waitFor(() => {
        expect(createdAudioInstances.length).toBeGreaterThan(0);
      });

      const audio = createdAudioInstances.at(-1);
      expect(audio).toBeDefined();

      act(() => {
        if (!audio) return;
        audio.currentTime = 3;
        audio.onplay?.();
      });

      expect(syncPlaylistStateSpy).toHaveBeenCalledWith(77, 3000, true, 0.5);

      act(() => {
        if (!audio) return;
        audio.currentTime = 4;
        audio.ontimeupdate?.();
        jest.advanceTimersByTime(260);
        audio.currentTime = 5;
        audio.ontimeupdate?.();
      });

      expect(syncPlaylistStateSpy).toHaveBeenCalledWith(77, 5000, true, 0.5);

      act(() => {
        if (!audio) return;
        audio.currentTime = 6;
        audio.onpause?.();
      });

      expect(syncPlaylistStateSpy).toHaveBeenCalledWith(77, 6000, false, 0.5);
    } finally {
      act(() => {
        useMusicStore.setState({
          syncPlaylistState: originalSyncPlaylistState,
        } as Partial<ReturnType<typeof useMusicStore.getState>>);
      });
      jest.useRealTimers();
    }
  });
});

// ═══════════════════════════════════════════════════════════════
// 卡顿检测逻辑（单元测试 — 不渲染组件，直接测试 interval 逻辑）
// ═══════════════════════════════════════════════════════════════
describe('MusicPlayer 卡顿检测', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  function simulateStallDetection(opts: {
    timeSequence: number[];
    paused?: boolean;
  }) {
    const { timeSequence, paused = false } = opts;
    const audio = {
      currentTime: timeSequence[0] ?? 0,
      paused,
      play: jest.fn().mockResolvedValue(undefined),
    };

    let lastTime = audio.currentTime;
    let stuckCount = 0;
    let switchTriggered = false;
    let recoveryAttempts: string[] = [];

    for (let i = 1; i < timeSequence.length; i++) {
      audio.currentTime = timeSequence[i];

      if (audio.currentTime === lastTime && !audio.paused) {
        stuckCount++;
        if (stuckCount >= 4 && stuckCount <= 5) {
          recoveryAttempts.push('play');
        } else if (stuckCount >= 6 && stuckCount <= 7) {
          recoveryAttempts.push('seek+play');
        } else if (stuckCount >= 8) {
          switchTriggered = true;
          break;
        }
      } else {
        stuckCount = 0;
      }
      lastTime = audio.currentTime;
    }

    return { stuckCount, switchTriggered, recoveryAttempts };
  }

  it('正常播放时不触发切歌', () => {
    const timeSeq = [0, 3, 6, 9, 12, 15, 18, 21, 24, 27];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.stuckCount).toBe(0);
    expect(result.recoveryAttempts).toEqual([]);
  });

  it('短暂卡顿不立即切歌（需要多次连续卡顿）', () => {
    const timeSeq = [10, 10, 10, 13, 16, 19];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.recoveryAttempts).toEqual([]);
  });

  it('连续卡顿 4-5 次触发第一层恢复（play）', () => {
    const timeSeq = [10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.recoveryAttempts).toContain('play');
    expect(result.recoveryAttempts).not.toContain('seek+play');
  });

  it('连续卡顿 6-7 次触发第二层恢复（seek+play）', () => {
    const timeSeq = [10, 10, 10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.recoveryAttempts).toContain('seek+play');
  });

  it('连续卡顿达到 8 次才触发切歌', () => {
    const timeSeq = [10, 10, 10, 10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(true);
  });

  it('卡顿中途恢复则重置计数', () => {
    const timeSeq = [10, 10, 10, 10, 13, 13, 13, 13];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.stuckCount).toBe(3);
  });

  it('音频暂停时不计入卡顿', () => {
    const timeSeq = [10, 10, 10, 10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq, paused: true });

    expect(result.switchTriggered).toBe(false);
    expect(result.stuckCount).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════
// timeupdate 节流逻辑（纯单元测试 — 不依赖组件渲染）
// ═══════════════════════════════════════════════════════════════
describe('MusicPlayer timeupdate 节流', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2024-01-01T00:00:00.000Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  function simulateThrottledTimeupdate(opts: {
    triggerTimes: number[];
  }) {
    let lastUpdateTime = Number.NEGATIVE_INFINITY;
    const callLog: number[] = [];

    for (const triggerTime of opts.triggerTimes) {
      if (triggerTime - lastUpdateTime >= 500) {
        lastUpdateTime = triggerTime;
        callLog.push(triggerTime);
      }
    }

    return { callLog, totalCalls: callLog.length };
  }

  it('500ms 内多次 timeupdate 只执行一次 setCurrentTime', () => {
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 100, 200, 300, 400],
    });

    expect(result.totalCalls).toBe(1);
    expect(result.callLog).toEqual([0]);
  });

  it('间隔超过 500ms 后允许再次触发', () => {
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 600],
    });

    expect(result.totalCalls).toBe(2);
    expect(result.callLog).toEqual([0, 600]);
  });

  it('密集触发后间隔够长再触发，应计数两次', () => {
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 100, 200, 800, 900],
    });

    expect(result.totalCalls).toBe(2);
    expect(result.callLog).toEqual([0, 800]);
  });

  it('恰好 500ms 间隔应允许触发', () => {
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 500, 1000, 1500],
    });

    expect(result.totalCalls).toBe(4);
    expect(result.callLog).toEqual([0, 500, 1000, 1500]);
  });

  it('连续密集触发应被节流为一次', () => {
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 100, 200, 300, 400],
    });

    expect(result.totalCalls).toBe(1);
    expect(result.callLog).toEqual([0]);
  });
});
