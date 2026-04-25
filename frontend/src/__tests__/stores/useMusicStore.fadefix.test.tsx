/**
 * fadeVolume 修复测试
 *
 * 验证 fadeVolume 不再每 50ms 调用 set() 更新 store 的 volume，
 * 而是仅在渐变结束时同步一次，避免 20 次重渲染/秒。
 *
 * 测试策略：使用 React.Profiler 统计组件渲染次数，
 * fadeVolume 执行期间渲染次数应 <= 2（初始 mount + 结束同步）。
 */

import React, { Profiler, useState } from "react";
import { render, waitFor } from "@testing-library/react";
import { useMusicStore } from "@/stores/useMusicStore";

// 提供一个极简的 HTMLAudioElement 替代物，仅需 volume 属性
function createFakeAudio(initialVolume: number = 0.5): HTMLAudioElement {
  const el = {
    volume: initialVolume,
    paused: true,
    currentTime: 0,
    duration: 100,
    play: () => Promise.resolve(),
    pause: () => {},
  } as unknown as HTMLAudioElement;
  return el;
}

// 测试组件：订阅 store 的 volume，并通过 Profiler 统计渲染
function VolumeDisplay() {
  const volume = useMusicStore((state) => state.volume);
  return <div data-testid="volume">{volume.toFixed(2)}</div>;
}

describe("fadeVolume — 不应对 store 产生高频更新", () => {
  beforeEach(() => {
    useMusicStore.setState({
      volume: 0.5,
      audioElement: null,
      isPlaying: false,
      currentSong: null,
      currentTime: 0,
      duration: 0,
    });
  });

  it("fadeVolume 结束后 volume 应同步回 store 一次", async () => {
    const store = useMusicStore.getState();
    const audio = createFakeAudio(0.5);
    store.setAudioElement(audio);

    store.fadeVolume(0.8, 200);

    // 渐变期间（200ms），store volume 不应变化
    await new Promise((r) => setTimeout(r, 100));
    expect(useMusicStore.getState().volume).toBe(0.5);
    expect(audio.volume).toBeGreaterThan(0.5);

    // 等待渐变完全结束
    await new Promise((r) => setTimeout(r, 200));
    await waitFor(() => {
      expect(useMusicStore.getState().volume).toBe(0.8);
      expect(audio.volume).toBeCloseTo(0.8, 1);
    });
  });

  it("fadeVolume 执行期间组件渲染次数应 <= 2", async () => {
    let renderCount = 0;
    const onRender = () => {
      renderCount++;
    };

    const store = useMusicStore.getState();
    const audio = createFakeAudio(0.2);
    store.setAudioElement(audio);

    render(
      <Profiler id="VolumeDisplay" onRender={onRender}>
        <VolumeDisplay />
      </Profiler>
    );

    const initialCount = renderCount;
    expect(initialCount).toBeGreaterThanOrEqual(1);

    // 触发 fadeVolume（200ms 内不应触发额外渲染）
    store.fadeVolume(0.9, 200);

    await new Promise((r) => setTimeout(r, 100));
    const duringCount = renderCount;
    // 渐变期间不应有新渲染
    expect(duringCount).toBe(initialCount);

    // 等待渐变结束
    await new Promise((r) => setTimeout(r, 200));
    await waitFor(() => {
      // 结束时最多再渲染一次（同步最终 volume）
      expect(renderCount).toBeLessThanOrEqual(initialCount + 1);
      expect(useMusicStore.getState().volume).toBe(0.9);
    });
  });

  it("fadeVolume 从 0 渐变到 1 时 audio.volume 应逐步变化", async () => {
    const store = useMusicStore.getState();
    const audio = createFakeAudio(0);
    store.setAudioElement(audio);

    const checkpoints: number[] = [];
    store.fadeVolume(1.0, 300);

    // 在 50ms、100ms、150ms 采样 audio.volume
    for (let t = 50; t <= 150; t += 50) {
      await new Promise((r) => setTimeout(r, 50));
      checkpoints.push(audio.volume);
    }

    // 检查点应单调递增
    for (let i = 1; i < checkpoints.length; i++) {
      expect(checkpoints[i]).toBeGreaterThanOrEqual(checkpoints[i - 1]);
    }

    // 最终应接近 1.0
    await new Promise((r) => setTimeout(r, 200));
    await waitFor(() => {
      expect(audio.volume).toBeCloseTo(1.0, 1);
      expect(useMusicStore.getState().volume).toBe(1.0);
    });
  });

  it("连续调用 fadeVolume 时应取消前一个 interval，避免多个渐变冲突", async () => {
    const store = useMusicStore.getState();
    const audio = createFakeAudio(0.1);
    store.setAudioElement(audio);

    // 第一次：从 0.1 渐变到 1.0（300ms）
    store.fadeVolume(1.0, 300);

    // 等待 100ms（渐变中）
    await new Promise((r) => setTimeout(r, 100));
    const volumeAfterFirstFadeMid = audio.volume;
    expect(volumeAfterFirstFadeMid).toBeGreaterThan(0.1);

    // 第二次：反向渐变到 0.0（150ms）——应取消第一次
    store.fadeVolume(0.0, 150);

    // 等待第二次完成
    await new Promise((r) => setTimeout(r, 250));

    // 如果第一次 interval 没被清除，audio.volume 会朝 1.0 走
    // 实际应该朝 0.0 走
    expect(audio.volume).toBeCloseTo(0.0, 1);
    expect(useMusicStore.getState().volume).toBe(0.0);

    // 再等待一段时间（确保第一个 interval 的残留不会把音量拉回去）
    await new Promise((r) => setTimeout(r, 300));
    expect(audio.volume).toBeCloseTo(0.0, 1);
  });
});
