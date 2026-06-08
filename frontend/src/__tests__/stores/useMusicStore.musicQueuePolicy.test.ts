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

function song(id: number | string, name: string, source: Song["source"] = "netease"): Song {
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
    jest.restoreAllMocks();
    delete (global as typeof globalThis & { fetch?: unknown }).fetch;
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

  it("store loadPlaylist restores persisted server playlist including generated tracks", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        game_id: 101,
        current_song: song(1, "网易云 当前曲"),
        queue: [
          song(2, "网易云 下一曲"),
          song("ai-generated-77", "AI MiniMax 雨夜追逐", "ai_generated"),
        ],
        played_songs: [song(0, "已播曲")],
        is_playing: true,
        volume: 0.8,
        current_position_ms: 42000,
      }),
    }) as jest.Mock;

    await useMusicStore.getState().loadPlaylist(101);

    const state = useMusicStore.getState();
    expect(global.fetch).toHaveBeenCalledWith("/api/music/playlist/101", {
      credentials: "include",
    });
    expect(state.playlistGameId).toBe(101);
    expect(state.currentSong?.id).toBe(1);
    expect(state.queue.map((item) => item.id)).toEqual([2, "ai-generated-77"]);
    expect(state.queue[1].source).toBe("ai_generated");
    expect(state.playedSongs.map((item) => item.id)).toEqual([0]);
    expect(state.isPlaying).toBe(true);
    expect(state.volume).toBe(0.8);
    expect(state.currentTime).toBe(42);
  });

  it("store mergePlaylist persists the Netease baseline queue before generated music arrives", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        game_id: 101,
        current_song: song(1, "网易云 当前曲"),
        queue: [song(2, "网易云 下一曲"), song(3, "网易云 后续曲")],
        played_songs: [],
        is_playing: false,
        volume: 0.5,
        current_position_ms: 0,
      }),
    }) as jest.Mock;

    await useMusicStore.getState().mergePlaylist(
      101,
      [song(1, "网易云 当前曲"), song(2, "网易云 下一曲"), song(3, "网易云 后续曲")],
      "紧张",
      ["雨夜追逐"]
    );

    expect(global.fetch).toHaveBeenCalledWith("/api/music/playlist/101", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        songs: [
          song(1, "网易云 当前曲"),
          song(2, "网易云 下一曲"),
          song(3, "网易云 后续曲"),
        ],
        mood: "紧张",
        keywords: ["雨夜追逐"],
      }),
    });
    expect(useMusicStore.getState().queue.map((item) => item.id)).toEqual([2, 3]);
  });

  it("store generateAiMusicForStory persists the current Netease baseline before async AI insertion", async () => {
    const aiSong = {
      ...song("ai-generated-77", "AI MiniMax 雨夜追逐", "ai_generated"),
      url: "/api/music/generated/brief-77.wav",
      provider: "minimax",
    };
    global.fetch = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/music/playlist/101") && init?.method === "PUT") {
        return {
          ok: true,
          json: async () => ({
            game_id: 101,
            current_song: song(1, "网易云 当前曲"),
            queue: [song(2, "网易云 下一曲"), song(3, "网易云 后续曲")],
            played_songs: [],
            is_playing: false,
            volume: 0.5,
            current_position_ms: 0,
          }),
        } as Response;
      }
      if (url.endsWith("/api/music/generate-async")) {
        return {
          ok: true,
          json: async () => ({
            status: "queued",
            game_id: 101,
            insert_policy: "future_queue",
          }),
        } as Response;
      }
      if (url.endsWith("/api/music/playlist/101")) {
        return {
          ok: true,
          json: async () => ({
            game_id: 101,
            current_song: song(1, "网易云 当前曲"),
            queue: [aiSong, song(2, "网易云 下一曲"), song(3, "网易云 后续曲")],
            played_songs: [],
            is_playing: false,
            volume: 0.5,
            current_position_ms: 0,
          }),
        } as Response;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;
    useMusicStore.setState({
      currentSong: song(1, "网易云 当前曲"),
      queue: [song(2, "网易云 下一曲"), song(3, "网易云 后续曲")],
    });

    await useMusicStore.getState().generateAiMusicForStory("雨夜码头故事", 101, {
      mood: "紧张",
    });

    expect(global.fetch).toHaveBeenNthCalledWith(1, "/api/music/playlist/101", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        songs: [
          song(1, "网易云 当前曲"),
          song(2, "网易云 下一曲"),
          song(3, "网易云 后续曲"),
        ],
        mood: "紧张",
        keywords: undefined,
      }),
    });
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      "/api/music/generate-async",
      expect.objectContaining({ method: "POST" })
    );
    const state = useMusicStore.getState();
    expect(state.currentSong?.id).toBe(1);
    expect(state.queue.map((item) => item.id)).toEqual(["ai-generated-77", 2, 3]);
  });

  it("store insertGeneratedTrack places AI music as the next upcoming track", () => {
    useMusicStore.setState({
      currentSong: song(1, "Current"),
      queue: [song(2, "NearTerm"), song(3, "Later")],
      playedSongs: [],
    });

    useMusicStore.getState().insertGeneratedTrack({
      ...song(77, "AI MiniMax 雨夜追逐", "ai_generated"),
      url: "/api/music/generated/brief-77.wav",
      asset_id: 77,
    });
    useMusicStore.getState().insertGeneratedTrack({
      ...song(77, "AI MiniMax 雨夜追逐", "ai_generated"),
      url: "/api/music/generated/brief-77.wav",
      asset_id: 77,
    });

    const state = useMusicStore.getState();
    expect(state.currentSong?.id).toBe(1);
    expect(state.queue.map((item) => item.id)).toEqual([77, 2, 3]);
    expect(state.queue.filter((item) => item.id === 77)).toHaveLength(1);
    expect(state.queue[0].source).toBe("ai_generated");
    expect(state.queue[0].url).toBe("/api/music/generated/brief-77.wav");
  });

  it("store insertGeneratedTrack starts AI music when no current song exists", () => {
    useMusicStore.setState({
      currentSong: null,
      queue: [],
      playedSongs: [],
    });

    useMusicStore.getState().insertGeneratedTrack({
      ...song("ai-generated-empty", "AI 职场专注氛围", "ai_generated"),
      url: "/api/music/generated/empty.wav",
      asset_id: 78,
    });

    const state = useMusicStore.getState();
    expect(state.currentSong?.id).toBe("ai-generated-empty");
    expect(state.queue).toEqual([]);
  });

  it("store insertGeneratedTrack also exposes generated music in recommendation songs", () => {
    useMusicStore.setState({
      recommendation: {
        keywords: ["雨夜"],
        mood: "紧张",
        scene_type: "追逐",
        songs: [song(1, "Current"), song(2, "NearTerm"), song(3, "Later")],
      },
      currentSong: song(1, "Current"),
      queue: [song(2, "NearTerm"), song(3, "Later")],
    });

    useMusicStore.getState().insertGeneratedTrack({
      ...song("ai-generated-77", "AI MiniMax 雨夜追逐", "ai_generated"),
      url: "/api/music/generated/brief-77.wav",
      asset_id: 77,
    });

    const recommendation = useMusicStore.getState().recommendation;
    expect(recommendation?.songs.map((item) => item.id)).toEqual([
      1,
      "ai-generated-77",
      2,
      3,
    ]);
    expect(recommendation?.songs[1].source).toBe("ai_generated");
  });

  it("store advanceQueue wraps played songs when the future queue is empty", async () => {
    useMusicStore.setState({
      currentSong: song(1, "Current"),
      queue: [],
      playedSongs: [song(0, "Previously Played")],
    });

    await useMusicStore.getState().advanceQueue();

    const state = useMusicStore.getState();
    expect(state.currentSong?.id).toBe(0);
    expect(state.queue.map((item) => item.id)).toEqual([1]);
    expect(state.playedSongs).toEqual([]);
  });

  it("store advanceQueue uses persisted playlist advance when a game playlist is active", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        game_id: 101,
        current_song: song(2, "Persisted Next"),
        queue: [song("ai-generated-77", "AI MiniMax 雨夜追逐", "ai_generated")],
        played_songs: [song(1, "Persisted Current")],
        is_playing: true,
        volume: 0.7,
        current_position_ms: 0,
      }),
    }) as jest.Mock;
    useMusicStore.setState({
      playlistGameId: 101,
      currentSong: song(1, "Current"),
      queue: [song(2, "Next"), song("ai-generated-77", "AI MiniMax 雨夜追逐", "ai_generated")],
      playedSongs: [],
    });

    await useMusicStore.getState().advanceQueue();

    expect(global.fetch).toHaveBeenCalledWith("/api/music/playlist/101/advance", {
      method: "POST",
      credentials: "include",
    });
    const state = useMusicStore.getState();
    expect(state.currentSong?.id).toBe(2);
    expect(state.queue.map((item) => item.id)).toEqual(["ai-generated-77"]);
    expect(state.queue[0].source).toBe("ai_generated");
  });

  it("source label helper surfaces AI tracks without labeling Netease as mandatory", () => {
    expect(getMusicSourceLabel("ai_generated")).toBe("AI");
    expect(getMusicSourceLabel("netease")).toBe("");
    expect(getMusicSourceLabel(undefined)).toBe("");
  });
});
