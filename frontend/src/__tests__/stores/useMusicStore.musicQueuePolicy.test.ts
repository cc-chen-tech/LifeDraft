/**
 * Music store queue policy tests.
 *
 * These tests exercise the real zustand store and pure exported helpers; no fetch
 * mocks or copied policy functions are used.
 */
import { describe, expect, it, beforeEach } from "@jest/globals";
import {
  getMusicSourceLabel,
  mergeSongsPreservingCurrent,
  useMusicStore,
  type Song,
} from "@/stores/useMusicStore";

function song(id: number, name: string, source: Song["source"] = "netease"): Song {
  return {
    id,
    name,
    artists: ["A"],
    album: "B",
    duration: 1000,
    source,
  };
}

describe("music queue policy", () => {
  beforeEach(() => {
    useMusicStore.getState().reset();
  });

  it("pure merge helper preserves current song and the first upcoming song", () => {
    const current = song(1, "Current");
    const nearTerm = song(2, "NearTerm");
    const generated = song(9, "AI 雨夜码头", "ai_generated");

    const result = mergeSongsPreservingCurrent(current, [nearTerm], [
      song(1, "Backend Current"),
      song(3, "Fresh"),
      generated,
    ]);

    expect(result.currentSong).toEqual(current);
    expect(result.queue.map((item) => item.id)).toEqual([2, 3, 9]);
    expect(result.queue[2].source).toBe("ai_generated");
  });

  it("store mergePlaylist keeps current playback stable when backend songs arrive", async () => {
    useMusicStore.setState({
      currentSong: song(1, "Current"),
      queue: [song(2, "NearTerm")],
      playedSongs: [song(0, "Played")],
    });

    await useMusicStore.getState().mergePlaylist(101, [
      song(1, "Backend Current"),
      song(3, "Fresh"),
      song(9, "AI 雨夜码头", "ai_generated"),
    ]);

    const state = useMusicStore.getState();
    expect(state.currentSong?.id).toBe(1);
    expect(state.queue.map((item) => item.id)).toEqual([2, 3, 9]);
    expect(state.queue[2].source).toBe("ai_generated");
  });

  it("store mergePlaylist preserves played history when backend songs refresh", async () => {
    useMusicStore.setState({
      currentSong: song(1, "Current"),
      queue: [song(2, "NearTerm")],
      playedSongs: [song(0, "Already Heard")],
    });

    await useMusicStore.getState().mergePlaylist(101, [song(3, "Fresh")]);

    expect(useMusicStore.getState().playedSongs.map((item) => item.id)).toEqual([0]);
  });

  it("source label helper surfaces AI tracks without labeling Netease as mandatory", () => {
    expect(getMusicSourceLabel("ai_generated")).toBe("AI");
    expect(getMusicSourceLabel("netease")).toBe("");
    expect(getMusicSourceLabel(undefined)).toBe("");
  });
});
