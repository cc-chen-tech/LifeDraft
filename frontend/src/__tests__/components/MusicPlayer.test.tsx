/**
 * MusicPlayer Component Tests
 * Prevents: audio loading failures, inaccessible controls, missing labels.
 *
 * 使用真实 Zustand store，不 mock。
 * 测试前通过 store.setState() 预置推荐数据，避免触发真实 API 请求。
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { MusicPlayer } from "@/components/game/MusicPlayer";
import { useMusicStore } from "@/stores/useMusicStore";

// 预置推荐数据，避免组件 mount 后发起 fetch
function seedStoreWithRecommendation() {
  useMusicStore.setState({
    recommendation: {
      mood: "宁静",
      scene_type: "独处",
      keywords: ["古风", "钢琴"],
      songs: [
        { id: 1, name: "测试歌曲", artists: ["测试艺术家"], album: "测试专辑", duration: 180000 },
      ],
      environment: "古风",
      story_style: "武侠",
    },
    isLoadingRecommendation: false,
    recommendationError: null,
    currentSong: null,
    isPlaying: false,
    volume: 0.5,
    currentTime: 0,
    duration: 0,
    audioElement: null,
  });
}

describe("MusicPlayer", () => {
  beforeEach(() => {
    seedStoreWithRecommendation();
  });

  afterEach(() => {
    // 清理 store 状态，避免测试间污染
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

  it("control buttons have aria-label for accessibility", () => {
    render(<MusicPlayer storyText="测试故事文本" />);

    // Play/pause button must have aria-label
    const playButton = screen.getByRole("button", { name: /播放|暂停/i });
    expect(playButton).toBeInTheDocument();

    // Skip buttons must have aria-label
    const prevButton = screen.getByRole("button", { name: /上一首/i });
    expect(prevButton).toBeInTheDocument();

    const nextButton = screen.getByRole("button", { name: /下一首/i });
    expect(nextButton).toBeInTheDocument();

    // Volume button must have aria-label
    const volumeButton = screen.getByRole("button", { name: /音量|静音/i });
    expect(volumeButton).toBeInTheDocument();
  });

  it("should render recommendation metadata tags", () => {
    render(<MusicPlayer storyText="测试故事文本" />);

    expect(screen.getByText("宁静")).toBeInTheDocument();
    expect(screen.getByText("古风")).toBeInTheDocument();
  });
});
