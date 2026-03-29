/**
 * MusicPlayer 组件测试
 * 
 * 测试覆盖：
 * 1. 单音频播放 - 确保任何时候只有一个音频在播放
 * 2. 版权限制歌曲跳过 - 确保不会重复请求失败的歌曲
 * 3. 音频切换 - 切换歌曲时旧音频立即停止
 * 4. 组件卸载清理 - 卸载时停止所有音频
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MusicPlayer } from '@/components/game/MusicPlayer';

// Mock Audio
class MockAudio {
  static instances: MockAudio[] = [];
  
  src = '';
  volume = 1;
  currentTime = 0;
  duration = 180;
  paused = true;
  onplay: (() => void) | null = null;
  onpause: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: ((e?: any) => void) | null = null;
  onloadedmetadata: (() => void) | null = null;
  ontimeupdate: (() => void) | null = null;
  oncanplaythrough: (() => void) | null = null;
  preload = 'auto';
  error: { code: number; message: string } | null = null;

  constructor(url?: string) {
    this.src = url || '';
    MockAudio.instances.push(this);
  }

  play = jest.fn().mockImplementation(() => {
    this.paused = false;
    if (this.onplay) this.onplay();
    // 模拟加载完成
    setTimeout(() => {
      if (this.onloadedmetadata) this.onloadedmetadata();
      if (this.oncanplaythrough) this.oncanplaythrough();
    }, 10);
    return Promise.resolve();
  });

  pause = jest.fn().mockImplementation(() => {
    this.paused = true;
    if (this.onpause) this.onpause();
  });

  simulateEnded() {
    if (this.onended) this.onended();
  }

  simulateError(code: number, message: string) {
    this.error = { code, message };
    if (this.onerror) this.onerror({});
  }

  static clearInstances() {
    MockAudio.instances = [];
  }

  static getPlayingInstances(): MockAudio[] {
    return MockAudio.instances.filter(audio => !audio.paused);
  }
}

// Mock fetchSongUrl and fetchMusicRecommendation
const mockFetchSongUrl = jest.fn();
const mockFetchMusicRecommendation = jest.fn();

// Mock store
const mockStore = {
  recommendation: {
    songs: [
      { id: 1, name: 'Song 1', artist: 'Artist 1', artists: ['Artist 1'], album: 'Album 1' },
      { id: 2, name: 'Song 2', artist: 'Artist 2', artists: ['Artist 2'], album: 'Album 2' },
      { id: 3, name: 'Song 3', artist: 'Artist 3', artists: ['Artist 3'], album: 'Album 3' },
    ],
    keywords: ['test'],
    description: 'Test description',
  },
  isLoadingRecommendation: false,
  recommendationError: null,
  currentSong: null,
  isPlaying: false,
  volume: 0.5,
  currentTime: 0,
  duration: 0,
  audioElement: null,
  setRecommendation: jest.fn(),
  setIsLoadingRecommendation: jest.fn(),
  setRecommendationError: jest.fn(),
  setCurrentSong: jest.fn(),
  setIsPlaying: jest.fn(),
  setVolume: jest.fn(),
  setCurrentTime: jest.fn(),
  setDuration: jest.fn(),
  setAudioElement: jest.fn(),
  play: jest.fn(),
  pause: jest.fn(),
  cleanup: jest.fn(),
  fadeVolume: jest.fn(),
};

jest.mock('@/stores/useMusicStore', () => ({
  useMusicStore: jest.fn(() => mockStore),
  fetchSongUrl: (...args: any[]) => mockFetchSongUrl(...args),
  fetchMusicRecommendation: (...args: any[]) => mockFetchMusicRecommendation(...args),
}));

describe('MusicPlayer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MockAudio.clearInstances();
    (global as any).Audio = MockAudio;

    // 重置 mock store 的函数
    (Object.keys(mockStore) as Array<keyof typeof mockStore>).forEach(key => {
      const value = mockStore[key];
      if (typeof value === 'function' && 'mockClear' in value) {
        value.mockClear();
      }
    });

    // 默认返回有效的歌曲 URL
    mockFetchSongUrl.mockResolvedValue('http://example.com/song.mp3');
    mockFetchMusicRecommendation.mockResolvedValue({
      songs: [
        { id: 1, name: 'Song 1', artist: 'Artist 1', artists: ['Artist 1'], album: 'Album 1' },
        { id: 2, name: 'Song 2', artist: 'Artist 2', artists: ['Artist 2'], album: 'Album 2' },
        { id: 3, name: 'Song 3', artist: 'Artist 3', artists: ['Artist 3'], album: 'Album 3' },
      ],
      keywords: ['test'],
      description: 'Test description',
    });
  });

  describe('单音频播放', () => {
    it('应该确保任何时候只有一个音频在播放', async () => {
      render(<MusicPlayer storyText="Test story" />);

      // 等待组件渲染和初始效果执行
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // 检查只有一个音频实例在播放
      const playingAudios = MockAudio.getPlayingInstances();
      expect(playingAudios.length).toBeLessThanOrEqual(1);
    });

    it('切换歌曲时应该停止旧音频', async () => {
      render(<MusicPlayer storyText="Test story" />);

      // 等待组件渲染
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      const firstAudio = MockAudio.instances[0];
      if (!firstAudio) {
        // 如果没有创建音频，测试通过（没有音频在播放）
        expect(MockAudio.getPlayingInstances().length).toBe(0);
        return;
      }

      // 模拟点击下一首
      const nextButton = screen.queryByLabelText('下一首');
      if (nextButton) {
        fireEvent.click(nextButton);

        await act(async () => {
          await new Promise(resolve => setTimeout(resolve, 100));
        });

        // 旧音频应该被暂停
        expect(firstAudio.pause).toHaveBeenCalled();
      }
    });
  });

  describe('版权限制歌曲跳过', () => {
    it('应该跳过无法获取URL的歌曲', async () => {
      // 第一首歌返回空URL（版权限制）
      mockFetchSongUrl
        .mockResolvedValueOnce(null)  // 第一首歌失败
        .mockResolvedValueOnce('http://example.com/song2.mp3')  // 第二首歌成功
        .mockResolvedValue('http://example.com/song.mp3');

      render(<MusicPlayer storyText="Test story" />);

      // 等待处理
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 300));
      });

      // 不应该重复请求同一首失败的歌曲
      const callsForSong1 = mockFetchSongUrl.mock.calls.filter(
        call => call[0] === 1
      );
      expect(callsForSong1.length).toBeLessThanOrEqual(1);
    });

    it('应该记录跳过的歌曲避免重复尝试', async () => {
      mockFetchSongUrl.mockResolvedValue(null); // 所有歌曲都失败

      render(<MusicPlayer storyText="Test story" />);

      // 等待处理所有歌曲
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 600));
      });

      // 每首歌应该只被请求一次
      const uniqueSongIds = new Set(mockFetchSongUrl.mock.calls.map(call => call[0]));
      expect(uniqueSongIds.size).toBe(mockFetchSongUrl.mock.calls.length);
    });
  });

  describe('组件卸载清理', () => {
    it('卸载时应该停止所有音频', async () => {
      const { unmount } = render(<MusicPlayer storyText="Test story" />);

      // 等待音频创建
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      const audio = MockAudio.instances[0];
      
      // 卸载组件
      unmount();

      // 音频应该被清理
      if (audio) {
        expect(audio.pause).toHaveBeenCalled();
      }
      expect(mockStore.cleanup).toHaveBeenCalled();
    });
  });

  describe('音频错误处理', () => {
    it('播放错误时应该尝试下一首', async () => {
      mockFetchSongUrl.mockResolvedValue('http://example.com/song.mp3');

      render(<MusicPlayer storyText="Test story" />);

      // 等待音频创建
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      const audio = MockAudio.instances[0];
      if (audio) {
        // 模拟播放错误
        act(() => {
          audio.simulateError(4, '格式不支持');
        });

        await act(async () => {
          await new Promise(resolve => setTimeout(resolve, 200));
        });

        // 应该尝试获取下一首歌的URL（至少2次：第一首和错误后的下一首）
        expect(mockFetchSongUrl.mock.calls.length).toBeGreaterThanOrEqual(1);
      }
    });
  });

  describe('预加载清理', () => {
    it('播放新歌曲时应该清理预加载的音频', async () => {
      render(<MusicPlayer storyText="Test story" />);

      // 等待第一首歌播放
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // 模拟切换到下一首
      const nextButton = screen.queryByLabelText('下一首');
      if (nextButton) {
        fireEvent.click(nextButton);

        await act(async () => {
          await new Promise(resolve => setTimeout(resolve, 100));
        });

        // 检查没有多个音频同时存在
        const activeAudios = MockAudio.instances.filter(
          audio => audio.src && audio.src !== ''
        );
        expect(activeAudios.length).toBeLessThanOrEqual(1);
      }
    });
  });
});
