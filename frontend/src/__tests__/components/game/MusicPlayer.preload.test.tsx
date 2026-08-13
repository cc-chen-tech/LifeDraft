import { act, render, waitFor } from "@testing-library/react";
import { MusicPlayer } from "@/components/game/MusicPlayer";
import { useMusicStore } from "@/stores/useMusicStore";

const createdAudioInstances: MockAudioClass[] = [];

class MockAudioClass {
  src = "";
  paused = true;
  currentTime = 0;
  duration = 180;
  volume = 1;
  preload = "";
  ended = false;
  error = null;
  play = jest.fn().mockResolvedValue(undefined);
  pause = jest.fn();
  onplay: (() => void) | null = null;
  onpause: (() => void) | null = null;
  ontimeupdate: (() => void) | null = null;
  onloadedmetadata: (() => void) | null = null;
  oncanplaythrough: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(src?: string) {
    this.src = src || "";
    createdAudioInstances.push(this);
  }
}

beforeAll(() => {
  (global as typeof globalThis & { Audio: typeof Audio }).Audio = MockAudioClass as never;
});

afterAll(() => {
  delete (global as Partial<typeof globalThis>).Audio;
});

describe("MusicPlayer preload", () => {
  beforeEach(() => {
    createdAudioInstances.length = 0;
    useMusicStore.setState({
      recommendation: {
        mood: "平静",
        scene_type: "独处",
        keywords: ["钢琴"],
        songs: [
          {
            id: 1,
            name: "当前曲目",
            artists: ["Score"],
            album: "影视配乐",
            duration: 180000,
            url: "https://example.com/current.mp3",
          },
          {
            id: 2,
            name: "已缓冲下一曲",
            artists: ["Score"],
            album: "影视配乐",
            duration: 180000,
            url: "https://example.com/next.mp3",
          },
        ],
      },
      currentSong: null,
      audioElement: null,
      isPlaying: false,
      queue: [],
      playedSongs: [],
      playlistGameId: null,
      volume: 0.5,
    } as never);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("reuses a ready preloaded audio element when advancing to the next song", async () => {
    jest.useFakeTimers();
    render(<MusicPlayer storyText="雨夜的影院即将开场。" autoFetchRecommendation={false} />);

    await waitFor(() => expect(createdAudioInstances).toHaveLength(1));
    const currentAudio = createdAudioInstances[0];
    act(() => currentAudio.onplay?.());

    await act(async () => {
      jest.advanceTimersByTime(5000);
      await Promise.resolve();
    });
    expect(createdAudioInstances).toHaveLength(2);
    const preloadedAudio = createdAudioInstances[1];
    act(() => preloadedAudio.oncanplaythrough?.());

    await act(async () => {
      currentAudio.onended?.();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(useMusicStore.getState().currentSong?.name).toBe("已缓冲下一曲");
    });
    expect(createdAudioInstances).toHaveLength(2);
    expect(preloadedAudio.play).toHaveBeenCalledTimes(1);
  });
});
