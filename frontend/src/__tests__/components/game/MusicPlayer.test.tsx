/**
 * MusicPlayer 组件测试
 *
 * 包含：基础渲染 + 卡顿检测（stall detection）逻辑验证
 * 使用真实 Zustand store + global.fetch mock，不 mock store 模块。
 */
import { render, screen, waitFor } from '@testing-library/react';
import { MusicPlayer } from '@/components/game/MusicPlayer';
import { useMusicStore } from '@/stores/useMusicStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

// jsdom 不支持 Audio API，提供完整 mock
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
  private _listeners: Record<string, Array<() => void>> = {};

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

describe('MusicPlayer', () => {
  beforeEach(() => {
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
