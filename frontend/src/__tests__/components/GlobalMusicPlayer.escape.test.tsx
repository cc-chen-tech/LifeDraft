import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GlobalMusicPlayer } from "@/components/game/GlobalMusicPlayer";
import { useMusicStore } from "@/stores/useMusicStore";

function resetMusicStore() {
  useMusicStore.setState({
    playlistGameId: null,
    currentSong: null,
    queue: [],
    recommendation: null,
    activeStoryText: null,
    activeGameId: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    audioElement: null,
  } as never);
}

describe("GlobalMusicPlayer keyboard dismissal", () => {
  beforeEach(() => {
    localStorage.clear();
    resetMusicStore();
  });

  afterEach(() => {
    resetMusicStore();
  });

  it("collapses the expanded playlist on Escape so song buttons cannot intercept story choices", async () => {
    const user = userEvent.setup();
    useMusicStore.setState({
      activeStoryText: "雨夜码头的旧账册被风吹开。",
      recommendation: {
        mood: "紧张",
        keywords: ["雨夜", "码头"],
        songs: [
          {
            id: 1001,
            name: "雨夜码头",
            artists: ["测试歌手"],
            album: "测试专辑",
            duration: 180,
            source: "netease",
          },
          {
            id: 1002,
            name: "雾港暗流",
            artists: ["测试歌手"],
            album: "测试专辑",
            duration: 180,
            source: "netease",
          },
        ],
      },
      currentSong: {
        id: 1001,
        name: "雨夜码头",
        artists: ["测试歌手"],
        album: "测试专辑",
        duration: 180,
        source: "netease",
      },
    } as never);

    render(<GlobalMusicPlayer />);

    await user.click(
      within(screen.getByTestId("global-music-mini-bar")).getByText(
        "雨夜码头 · 测试歌手",
      ),
    );
    expect(screen.queryByRole("button", { name: "下一首" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "展开声音" }));
    expect(screen.getByRole("button", { name: "下一首" })).toBeVisible();

    fireEvent.keyDown(document, { key: "Escape", code: "Escape" });

    expect(screen.queryByRole("button", { name: "下一首" })).not.toBeInTheDocument();
  });
});
