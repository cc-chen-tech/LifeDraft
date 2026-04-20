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

  /**
   * 模拟 MusicPlayer 中 timeupdate 的 250ms 节流逻辑。
   *
   * 组件中 timeUpdateThrottleRef.current 初始值为 0，Date.now() 初始值很大，
   * 所以第一次触发一定通过。之后按 250ms 间隔节流。
   */
  function simulateThrottledTimeupdate(opts: {
    /** 每次 timeupdate 触发的时间点（相对于起始时间的毫秒数） */
    triggerTimes: number[];
  }) {
    // 初始 ref 值为 0，但 Date.now() 是从系统时间开始，所以首次触发条件
    // 实际上是 (firstTriggerTime + baseTime) - 0 >= 250，总是成立。
    // 这里用负无穷表示"首次总是通过"。
    let lastUpdateTime = Number.NEGATIVE_INFINITY;
    const callLog: number[] = [];

    for (const triggerTime of opts.triggerTimes) {
      if (triggerTime - lastUpdateTime >= 250) {
        lastUpdateTime = triggerTime;
        callLog.push(triggerTime);
      }
    }

    return { callLog, totalCalls: callLog.length };
  }

  it('250ms 内多次 timeupdate 只执行一次 setCurrentTime', () => {
    // 在 200ms 内触发 5 次（时间间隔都小于 250ms）
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 50, 100, 150, 200],
    });

    expect(result.totalCalls).toBe(1);
    expect(result.callLog).toEqual([0]);
  });

  it('间隔超过 250ms 后允许再次触发', () => {
    // t=0, t=300（间隔 300ms > 250ms，允许）
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 300],
    });

    expect(result.totalCalls).toBe(2);
    expect(result.callLog).toEqual([0, 300]);
  });

  it('密集触发后间隔够长再触发，应计数两次', () => {
    // 快速触发 3 次 → 等待 300ms → 再触发 2 次
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 50, 100, 400, 450],
    });

    expect(result.totalCalls).toBe(2); // t=0 和 t=400 各一次
    expect(result.callLog).toEqual([0, 400]);
  });

  it('恰好 250ms 间隔应允许触发', () => {
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 250, 500, 750],
    });

    expect(result.totalCalls).toBe(4);
    expect(result.callLog).toEqual([0, 250, 500, 750]);
  });

  it('连续密集触发应被节流为一次', () => {
    // 所有触发点都在 250ms 窗口内
    const result = simulateThrottledTimeupdate({
      triggerTimes: [0, 50, 100, 150, 200],
    });

    expect(result.totalCalls).toBe(1);
    expect(result.callLog).toEqual([0]);
  });
});
