/**
 * MusicPlayer 组件测试
 *
 * 包含：基础渲染 + 卡顿检测（stall detection）逻辑验证
 */
import { render, screen, waitFor, act } from '@testing-library/react';
import { MusicPlayer } from '@/components/game/MusicPlayer';

// Mock Audio API
global.Audio = class MockAudio {
  src = '';
  paused = true;
  currentTime = 0;
  duration = 180;
  volume = 1;
  preload = '';
  error: MediaError | null = null;
  play = jest.fn().mockResolvedValue(undefined);
  pause = jest.fn();
  onplay: (() => void) | null = null;
  onpause: (() => void) | null = null;
  ontimeupdate: (() => void) | null = null;
  onloadedmetadata: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: ((e: any) => void) | null = null;
  onstalled: (() => void) | null = null;
  onwaiting: (() => void) | null = null;
  oncanplay: (() => void) | null = null;
  oncanplaythrough: (() => void) | null = null;
  constructor(url?: string) {
    this.src = url || '';
  }
} as any;

describe('MusicPlayer', () => {
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

  /**
   * 模拟 MusicPlayer 内 stall-detection interval 的核心逻辑
   * （从组件中提取的纯逻辑，方便单元测试）
   */
  function simulateStallDetection(opts: {
    /** 每次 interval 回调时 audio.currentTime 的值序列 */
    timeSequence: number[];
    /** audio.paused 状态 */
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

    // 从 index=1 开始，模拟每次 3 秒 interval
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
    // currentTime 每 3 秒递增 3
    const timeSeq = [0, 3, 6, 9, 12, 15, 18, 21, 24, 27];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.stuckCount).toBe(0);
    expect(result.recoveryAttempts).toEqual([]);
  });

  it('短暂卡顿不立即切歌（需要多次连续卡顿）', () => {
    // 卡 2 个周期后恢复
    const timeSeq = [10, 10, 10, 13, 16, 19];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.recoveryAttempts).toEqual([]);
  });

  it('连续卡顿 4-5 次触发第一层恢复（play）', () => {
    // 卡 5 个周期
    const timeSeq = [10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.recoveryAttempts).toContain('play');
    expect(result.recoveryAttempts).not.toContain('seek+play');
  });

  it('连续卡顿 6-7 次触发第二层恢复（seek+play）', () => {
    // 卡 7 个周期
    const timeSeq = [10, 10, 10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    expect(result.recoveryAttempts).toContain('seek+play');
  });

  it('连续卡顿达到 8 次才触发切歌', () => {
    // 卡 8 个周期（24 秒）
    const timeSeq = [10, 10, 10, 10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(true);
  });

  it('卡顿中途恢复则重置计数', () => {
    // 卡 3 次 → 恢复 → 再卡 3 次
    const timeSeq = [10, 10, 10, 10, 13, 13, 13, 13];
    const result = simulateStallDetection({ timeSequence: timeSeq });

    expect(result.switchTriggered).toBe(false);
    // stuckCount 应该是 3（第二轮卡顿），没到切歌阈值
    expect(result.stuckCount).toBe(3);
  });

  it('音频暂停时不计入卡顿', () => {
    // currentTime 不变但 paused=true
    const timeSeq = [10, 10, 10, 10, 10, 10, 10, 10, 10];
    const result = simulateStallDetection({ timeSequence: timeSeq, paused: true });

    expect(result.switchTriggered).toBe(false);
    expect(result.stuckCount).toBe(0);
  });
});
