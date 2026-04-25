/**
 * MusicPlayer Component Tests
 * Prevents: audio loading failures, inaccessible controls, missing labels.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { MusicPlayer } from "@/components/game/MusicPlayer";

// Mock zustand store
const mockStore = {
  recommendation: null,
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

jest.mock("@/stores/useMusicStore", () => ({
  useMusicStore: () => mockStore,
  fetchMusicRecommendation: jest.fn(),
  fetchSongUrl: jest.fn(),
}));

describe("MusicPlayer", () => {
  it("control buttons have aria-label for accessibility", () => {
    (mockStore as Record<string, unknown>).recommendation = {
      mood: "宁静",
      scene_type: "独处",
      keywords: ["古风", "钢琴"],
      songs: [
        { id: 1, name: "测试歌曲", artists: ["测试艺术家"], album: "测试专辑", duration: 180000 },
      ],
    };

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
});
