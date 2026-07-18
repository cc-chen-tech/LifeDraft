import { act, render, screen, waitFor } from '@testing-library/react';
import { MusicPlayer } from '@/components/game/MusicPlayer';
import { type Song, useMusicStore } from '@/stores/useMusicStore';

const createdAudioInstances: RecoveryAudio[] = [];

class RecoveryAudio {
  static nextPlayFailure: Error | null = null;

  src = '';
  paused = true;
  currentTime = 0;
  duration = 180;
  volume = 1;
  preload = '';
  error: { code: number; message: string } | null = null;
  play = jest.fn(() => {
    const failure = RecoveryAudio.nextPlayFailure;
    RecoveryAudio.nextPlayFailure = null;
    return failure ? Promise.reject(failure) : Promise.resolve();
  });
  pause = jest.fn();
  onplay: (() => void) | null = null;
  onpause: (() => void) | null = null;
  ontimeupdate: (() => void) | null = null;
  onloadedmetadata: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(src?: string) {
    this.src = src || '';
    createdAudioInstances.push(this);
  }
}

const firstSong: Song = {
  id: 1,
  name: '故障曲目',
  artists: ['测试艺术家'],
  album: '测试专辑',
  duration: 180_000,
  url: 'https://example.com/first.mp3',
};

const secondSong: Song = {
  id: 2,
  name: '恢复曲目',
  artists: ['测试艺术家'],
  album: '测试专辑',
  duration: 180_000,
  url: 'https://example.com/second.mp3',
};

beforeAll(() => {
  (global as typeof globalThis & { Audio: typeof RecoveryAudio }).Audio = RecoveryAudio;
});

afterAll(() => {
  delete (global as Partial<typeof globalThis>).Audio;
});

describe('MusicPlayer browser playback recovery contracts', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    createdAudioInstances.length = 0;
    RecoveryAudio.nextPlayFailure = null;
    useMusicStore.setState({
      recommendation: {
        mood: '紧张',
        scene_type: '追捕',
        keywords: ['悬疑'],
        songs: [firstSong, secondSong],
      },
      isLoadingRecommendation: false,
      recommendationError: null,
      currentSong: null,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      audioElement: null,
      queue: [],
      playedSongs: [],
      playlistGameId: null,
      isGeneratingAiMusic: false,
      aiMusicGenerationStatus: 'idle',
    });
  });

  afterEach(() => {
    jest.useRealTimers();
    useMusicStore.getState().cleanup();
  });

  it('skips an errored browser audio track and starts the next recommendation', async () => {
    render(<MusicPlayer storyText="追逐中的故事" autoFetchRecommendation={false} />);

    await waitFor(() => expect(createdAudioInstances).toHaveLength(1));
    const failedAudio = createdAudioInstances[0];
    failedAudio.error = { code: 2, message: 'network failed' };

    await act(async () => {
      failedAudio.onerror?.(new Event('error'));
    });

    expect(screen.getByText(/故障曲目.*网络错误/)).toBeInTheDocument();
    expect(screen.getByText(/已跳过 1 首/)).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(800);
    });

    await waitFor(() => expect(createdAudioInstances).toHaveLength(2));
    expect(useMusicStore.getState().currentSong).toMatchObject({ id: secondSong.id });
    expect(createdAudioInstances[1].src).toBe(secondSong.url);
  });

  it('settles switching UI after a browser autoplay rejection without a false service outage', async () => {
    RecoveryAudio.nextPlayFailure = new Error('NotAllowedError');

    render(<MusicPlayer storyText="需要恢复播放的故事" autoFetchRecommendation={false} />);

    await waitFor(() => expect(createdAudioInstances).toHaveLength(1));
    await waitFor(() => expect(createdAudioInstances[0].play).toHaveBeenCalled());
    await waitFor(() => {
      expect(screen.queryByText('切换歌曲中...')).not.toBeInTheDocument();
    });

    expect(useMusicStore.getState().currentSong).toMatchObject({ id: firstSong.id });
    expect(screen.queryByText('音乐服务暂不可用')).not.toBeInTheDocument();
    expect(screen.getAllByText(firstSong.name).length).toBeGreaterThan(0);
  });
});
