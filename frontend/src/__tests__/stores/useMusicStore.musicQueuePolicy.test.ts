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

  it("pure merge helper dedupes upcoming NetEase songs by title family", () => {
    const current = song(1, "办公室 轻电子 氛围");

    const result = mergeSongsPreservingCurrent(current, [], [
      song(20, "绅士"),
      song(21, "绅士 (Live)"),
      song(22, "红尘客栈"),
      song(23, "红尘客栈 - 古风翻唱"),
      song(24, "用户数据冷光"),
    ]);

    expect(result.queue.map((item) => item.name)).toEqual([
      "绅士",
      "红尘客栈",
      "用户数据冷光",
    ]);
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

  it("store mergePlaylist tolerates empty recommendations after malformed playlist restore", async () => {
    useMusicStore.setState({
      currentSong: undefined,
      queue: undefined,
    } as Partial<ReturnType<typeof useMusicStore.getState>>);

    await expect(useMusicStore.getState().mergePlaylist(101, [])).resolves.toBeUndefined();

    const state = useMusicStore.getState();
    expect(state.currentSong).toBeNull();
    expect(state.queue).toEqual([]);
    expect(state.playlistGameId).toBe(101);
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

  it("store loadPlaylist preserves local library reuse metadata on generated tracks", async () => {
    const reusedTrack: Song = {
      id: "ai-generated-88",
      name: "AI MiniMax 现代职场危机",
      artists: ["MiniMax"],
      album: "AI Generated",
      duration: 1000,
      source: "ai_generated",
      url: "/api/music/generated/reused-88.mp3",
      asset_id: 88,
      provider: "minimax",
      model: "music-2.6",
      brief_hash: "brief-88",
      library_reused: true,
      match_score: 94,
      match_reason: "scene_fit",
    };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        game_id: 202,
        current_song: song(1, "网易云 当前曲"),
        queue: [reusedTrack],
        played_songs: [],
        is_playing: false,
        volume: 0.5,
        current_position_ms: 0,
      }),
    }) as jest.Mock;

    await useMusicStore.getState().loadPlaylist(202);

    const generated = useMusicStore.getState().queue[0];
    expect(generated.source).toBe("ai_generated");
    expect(generated.library_reused).toBe(true);
    expect(generated.match_score).toBe(94);
    expect(generated.match_reason).toBe("scene_fit");
  });

  it("store loadPlaylist preserves scene-fit diagnostic metadata on generated tracks", async () => {
    const diagnosticTrack: Song & {
      fit_score: number;
      prompt_version: string;
      scene_fit_diagnostics: { selected_strategy: string };
    } = {
      id: "ai-generated-89",
      name: "AI MiniMax 安静康复",
      artists: ["MiniMax"],
      album: "AI Generated",
      duration: 1000,
      source: "ai_generated",
      url: "/api/music/generated/reused-89.mp3",
      asset_id: 89,
      provider: "minimax",
      model: "music-2.6",
      brief_hash: "brief-89",
      fit_score: 91,
      prompt_version: "music-scene-v1",
      scene_fit_diagnostics: { selected_strategy: "quiet_recovery" },
    };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        game_id: 203,
        current_song: song(1, "网易云 当前曲"),
        queue: [diagnosticTrack],
        played_songs: [],
        is_playing: false,
        volume: 0.5,
        current_position_ms: 0,
      }),
    }) as jest.Mock;

    await useMusicStore.getState().loadPlaylist(203);

    const generated = useMusicStore.getState().queue[0] as typeof diagnosticTrack;
    expect(generated.fit_score).toBe(91);
    expect(generated.prompt_version).toBe("music-scene-v1");
    expect(generated.scene_fit_diagnostics.selected_strategy).toBe("quiet_recovery");
  });

  it("store syncPlaylistState persists playback position and volume without mutating playback", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    }) as jest.Mock;
    useMusicStore.setState({
      currentSong: song(1, "网易云 当前曲"),
      isPlaying: true,
      currentTime: 12,
      volume: 0.7,
    });

    await useMusicStore.getState().syncPlaylistState(101, 12345, true, 0.7);

    expect(global.fetch).toHaveBeenCalledWith("/api/music/playlist/101/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        current_position_ms: 12345,
        is_playing: true,
        volume: 0.7,
      }),
    });
    expect(useMusicStore.getState().isPlaying).toBe(true);
    expect(useMusicStore.getState().currentTime).toBe(12);
  });

  it("store syncPlaylistState tolerates backend sync failures", async () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    global.fetch = jest.fn().mockRejectedValue(new Error("network unavailable")) as jest.Mock;

    await expect(
      useMusicStore.getState().syncPlaylistState(101, 5000, false, 0.4)
    ).resolves.toBeUndefined();

    expect(warnSpy).toHaveBeenCalledWith(
      "[MusicStore] Failed to sync playlist state:",
      expect.any(Error)
    );
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
      if (url.endsWith("/api/music/generate")) {
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
      "/api/music/generate",
      expect.objectContaining({ method: "POST" })
    );
    const state = useMusicStore.getState();
    expect(state.currentSong?.id).toBe(1);
    expect(state.queue.map((item) => item.id)).toEqual(["ai-generated-77", 2, 3]);
  });

  it("store generateAiMusicForStory deduplicates concurrent duplicate generation requests", async () => {
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
      if (url.endsWith("/api/music/generate")) {
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

    const generation = useMusicStore.getState().generateAiMusicForStory("雨夜码头的旧账册被风吹开。", 101, {
      mood: "紧张",
    });
    const duplicate = useMusicStore.getState().generateAiMusicForStory("雨夜码头的旧账册被风吹开。", 101, {
      mood: "紧张",
    });

    await Promise.all([generation, duplicate]);

    const generateCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
      String(url).endsWith("/api/music/generate")
    );
    expect(generateCalls).toHaveLength(1);
  });

  it("store keeps async AI music visibly queued when polling has not seen the generated track yet", async () => {
    jest.useFakeTimers();
    try {
      global.fetch = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/music/playlist/101") && init?.method === "PUT") {
          return {
            ok: true,
            json: async () => ({
              game_id: 101,
              current_song: song(1, "网易云 当前曲"),
              queue: [],
              played_songs: [],
              is_playing: false,
              volume: 0.5,
              current_position_ms: 0,
            }),
          } as Response;
        }
        if (url.endsWith("/api/music/generate")) {
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
              queue: [],
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
        queue: [],
      });

      const generation = useMusicStore.getState().generateAiMusicForStory("雨夜码头故事", 101, {
        mood: "紧张",
      });

      await jest.runAllTimersAsync();
      await generation;

      expect(useMusicStore.getState().isGeneratingAiMusic).toBe(false);
      expect(useMusicStore.getState().aiMusicGenerationStatus).toBe("delayed");
    } finally {
      jest.useRealTimers();
    }
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
