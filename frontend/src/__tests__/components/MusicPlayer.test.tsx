/**
 * MusicPlayer Component Tests
 * Prevents: audio loading failures, inaccessible controls, missing labels.
 *
 * 使用真实 Zustand store + global.fetch mock，不 mock store 模块。
 * global.Audio mock 需完整（含 addEventListener/removeEventListener）。
 */
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { MusicPlayer } from "@/components/game/MusicPlayer";
import { useMusicStore } from "@/stores/useMusicStore";
import { jsonResponse } from "@/__tests__/helpers/fetch";

// jsdom 不支持 Audio API，提供完整 mock
class MockAudioClass {
  src = "";
  paused = true;
  currentTime = 0;
  duration = 180;
  volume = 1;
  preload = "";
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

describe("MusicPlayer", () => {
  beforeEach(() => {
    // 顺序: 1) fetchMusicRecommendation, 2) fetchSongUrl
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          mood: "宁静",
          scene_type: "独处",
          keywords: ["古风", "钢琴"],
          songs: [
            {
              id: 1,
              name: "测试歌曲",
              artists: ["测试艺术家"],
              album: "测试专辑",
              duration: 180000,
              url: "https://example.com/test.mp3",
            },
          ],
          environment: "古风",
          story_style: "武侠",
        })
      ) as jest.Mock;

    // 不预置 recommendation — 让组件自然 fetch
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

  it("control buttons have aria-label for accessibility", async () => {
    render(<MusicPlayer storyText="测试故事文本" />);

    // recommendation 由 fetch 填充，按钮随之出现
    expect(await screen.findByRole("button", { name: /播放|暂停/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /上一首/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /下一首/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /音量|静音/i })).toBeInTheDocument();
  });

  it("should render recommendation metadata tags", async () => {
    render(<MusicPlayer storyText="测试故事文本" />);

    expect(await screen.findByText("宁静")).toBeInTheDocument();
    expect(screen.getByText("古风")).toBeInTheDocument();
  });
});
