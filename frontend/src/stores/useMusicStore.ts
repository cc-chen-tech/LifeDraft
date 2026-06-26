/**
 * useMusicStore — 音乐播放状态管理
 *
 * 管理故事音乐推荐和播放状态
 */
import { create } from "zustand";
import type { CharacterSettings } from "@/lib/types";

export interface Song {
  id: number | string;
  name: string;
  artists: string[];
  album: string;
  duration: number;
  url?: string;
  source?: "netease" | "ai_generated";
  asset_id?: number;
  provider?: string;
  model?: string;
  brief_hash?: string;
  library_reused?: boolean;
  match_score?: number;
  match_reason?: string;
  fit_score?: number;
  prompt_version?: string;
  scene_fit_diagnostics?: Record<string, unknown>;
}

export interface MusicRecommendation {
  keywords: string[];
  mood: string;
  scene_type: string;
  environment?: string;      // 环境氛围（古风、现代、未来等）
  story_style?: string;      // 故事风格（武侠、仙侠、科幻等）
  music_style?: string;      // 推荐音乐风格
  instruments?: string[];    // 适合的乐器
  pacing?: string;           // 叙事节奏（舒缓、紧凑等）
  time_weather?: string;     // 时间天气（清晨、雨天等）
  description?: string;      // 音乐氛围描述
  music_brief?: Record<string, unknown>;
  songs: Song[];
}

export interface MusicQueueMergeResult {
  currentSong: Song | null;
  queue: Song[];
}

export type AiMusicGenerationStatus =
  | "idle"
  | "queued"
  | "polling"
  | "ready"
  | "delayed"
  | "failed";

interface PlaylistApiState {
  game_id: number;
  current_song: Song | null;
  queue: Song[];
  played_songs: Song[];
  is_playing: boolean;
  volume: number;
  current_position_ms: number;
}

function songKey(song: Song): number | string {
  return song.id;
}

const REPORTED_TITLE_FAMILY_CUES = [
  "小幸运",
  "断了的弦",
  "绅士",
  "红尘客栈",
  "非你莫属",
  "给我一首歌的时间",
  "等你下课",
  "不再联系",
  "说散就散",
  "匆匆那年",
  "告白气球",
  "喜欢你",
  "夜曲",
  "一直很安静",
  "平凡之路",
  "岁月神偷",
  "都选C",
  "她说",
  "童话",
  "丑八怪",
  "可爱女人",
];

function canonicalSongTitle(title: unknown): string {
  return String(title || "")
    .toLowerCase()
    .replace(/[（(][^）)]*[）)]/g, "")
    .replace(
      /(心动版|加速版|降速版|抖音版|翻唱版|古风翻唱|翻唱|cover|伴奏|纯音乐版|剪辑版|完整版|live|remix|remaster|0\.\d+x|\d+(?:\.\d+)?x|版)/gi,
      ""
    )
    .replace(/[\s\-—_·.。…!！?？,，、:：;；'"“”‘’《》[\]【】/\\]+/g, "");
}

function titleFamilyKey(song: Song): string {
  const canonicalTitle = canonicalSongTitle(song.name);
  for (const cue of REPORTED_TITLE_FAMILY_CUES) {
    const canonicalCue = canonicalSongTitle(cue);
    if (canonicalCue && (canonicalTitle === canonicalCue || canonicalTitle.includes(canonicalCue))) {
      return canonicalCue;
    }
  }
  return canonicalTitle;
}

export function mergeSongsPreservingCurrent(
  currentSong: Song | null,
  existingQueue: Song[],
  incomingSongs: Song[]
): MusicQueueMergeResult {
  if (currentSong === null) {
    if (incomingSongs.length === 0) {
      return { currentSong: null, queue: [...existingQueue] };
    }
    return {
      currentSong: incomingSongs[0],
      queue: dedupeSongs(incomingSongs.slice(1), undefined),
    };
  }

  const currentId = songKey(currentSong);
  const currentTitleKey = titleFamilyKey(currentSong);
  const queue: Song[] = [];
  if (existingQueue.length > 0 && songKey(existingQueue[0]) !== currentId) {
    queue.push(existingQueue[0]);
  }

  const seenIds = new Set(queue.map(songKey));
  const seenTitleKeys = new Set(
    [currentTitleKey, ...queue.map(titleFamilyKey)].filter(Boolean)
  );
  for (const song of incomingSongs) {
    const id = songKey(song);
    const familyKey = titleFamilyKey(song);
    if (id === currentId || seenIds.has(id)) {
      continue;
    }
    if (familyKey && seenTitleKeys.has(familyKey)) {
      continue;
    }
    queue.push(song);
    seenIds.add(id);
    if (familyKey) {
      seenTitleKeys.add(familyKey);
    }
  }

  return { currentSong, queue };
}

export function getMusicSourceLabel(source: Song["source"] | undefined): string {
  return source === "ai_generated" ? "AI" : "";
}

function dedupeSongs(songs: Song[], excludedId: number | string | undefined): Song[] {
  const seenIds = new Set<number | string>();
  const seenTitleKeys = new Set<string>();
  const result: Song[] = [];
  for (const song of songs) {
    const id = songKey(song);
    const familyKey = titleFamilyKey(song);
    if (id === excludedId || seenIds.has(id)) {
      continue;
    }
    if (familyKey && seenTitleKeys.has(familyKey)) {
      continue;
    }
    result.push(song);
    seenIds.add(id);
    if (familyKey) {
      seenTitleKeys.add(familyKey);
    }
  }
  return result;
}

function playlistStateToStorePatch(playlist: PlaylistApiState): Partial<MusicState> {
  return {
    playlistGameId: playlist.game_id,
    currentSong: playlist.current_song ?? null,
    queue: playlist.queue || [],
    playedSongs: playlist.played_songs || [],
    isPlaying: playlist.is_playing,
    volume: playlist.volume,
    currentTime: Math.max(0, (playlist.current_position_ms || 0) / 1000),
  };
}

function playlistSongs(playlist: PlaylistApiState): Song[] {
  return [
    playlist.current_song,
    ...(playlist.queue || []),
  ].filter((song): song is Song => Boolean(song));
}

function playlistStateToStorePatchWithRecommendation(
  playlist: PlaylistApiState,
  recommendation: MusicRecommendation | null
): Partial<MusicState> {
  const patch = playlistStateToStorePatch(playlist);
  if (!recommendation) {
    return patch;
  }
  const songs = playlistSongs(playlist);
  if (songs.length === 0) {
    return patch;
  }
  return {
    ...patch,
    recommendation: {
      ...recommendation,
      songs,
    },
  };
}

interface MusicState {
  // 推荐结果
  recommendation: MusicRecommendation | null;
  isLoadingRecommendation: boolean;
  recommendationError: string | null;

  // 播放状态
  currentSong: Song | null;
  isPlaying: boolean;
  volume: number;
  currentTime: number;
  duration: number;

  // 播放器实例（HTMLAudioElement）
  audioElement: HTMLAudioElement | null;

  // fadeVolume interval 引用，防止多个渐变冲突
  fadeInterval: ReturnType<typeof setInterval> | null;
  voiceDuckActive: boolean;
  voiceDuckRestoreVolume: number | null;

  // Playlist queue state
  queue: Song[];
  playedSongs: Song[];
  playlistGameId: number | null;
  isLoadingPlaylist: boolean;
  isGeneratingAiMusic: boolean;
  aiMusicGenerationStatus: AiMusicGenerationStatus;

  // Active story context (set by play page)
  activeStoryText: string | null;
  activeGameId: number | null;

  // Actions
  setRecommendation: (recommendation: MusicRecommendation | null) => void;
  setIsLoadingRecommendation: (loading: boolean) => void;
  setRecommendationError: (error: string | null) => void;

  setCurrentSong: (song: Song | null) => void;
  setIsPlaying: (playing: boolean) => void;
  setVolume: (volume: number) => void;
  setCurrentTime: (time: number) => void;
  setDuration: (duration: number) => void;
  setAudioElement: (audio: HTMLAudioElement | null) => void;
  setFadeInterval: (interval: ReturnType<typeof setInterval> | null) => void;

  // 播放控制
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  seek: (time: number) => void;
  changeVolume: (volume: number) => void;
  fadeVolume: (targetVolume: number, duration?: number) => void;  // 音量渐变
  duckForVoiceReading: (targetVolume?: number, duration?: number) => boolean;
  restoreAfterVoiceReading: (duration?: number) => void;

  // Playlist actions
  setQueue: (queue: Song[]) => void;
  setPlayedSongs: (songs: Song[]) => void;
  setPlaylistGameId: (gameId: number | null) => void;
  loadPlaylist: (gameId: number) => Promise<void>;
  mergePlaylist: (gameId: number, songs: Song[], mood?: string, keywords?: string[]) => Promise<void>;
  insertGeneratedTrack: (track: Song) => void;
  generateAiMusicForStory: (
    storyText: string,
    gameId: number,
    analysis?: Record<string, unknown>
  ) => Promise<void>;
  syncPlaylistState: (gameId: number, positionMs: number, isPlaying: boolean, volume: number) => Promise<void>;
  advanceQueue: () => Promise<void>;

  // Active story context setters
  setActiveStoryText: (text: string | null) => void;
  setActiveGameId: (gameId: number | null) => void;

  // 清理
  reset: () => void;
  cleanup: () => void;
}

// ★ Use the same relative /api path as api.ts to ensure consistency.
// Absolute URLs bypass the Next.js proxy and can cause CORS/timeout issues.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";
const GENERATED_MUSIC_POLL_ATTEMPTS = 30;
const GENERATED_MUSIC_POLL_INTERVAL_MS = 10_000;
const GENERATION_IN_FLIGHT_KEY_PREFIX = "music-generation:";

const inFlightMusicGenerations = new Set<string>();

function stringifyMusicAnalysis(analysis: Record<string, unknown> | undefined): string {
  if (!analysis) return "";
  const keys = Object.keys(analysis).sort();
  const normalized: Record<string, unknown> = {};
  for (const key of keys) {
    normalized[key] = analysis[key];
  }
  return JSON.stringify(normalized);
}

function buildMusicGenerationKey(
  gameId: number,
  storyText: string,
  analysis: Record<string, unknown> | undefined
): string {
  return `${GENERATION_IN_FLIGHT_KEY_PREFIX}${gameId}:${storyText.slice(0, 120)}:${storyText.length}:${stringifyMusicAnalysis(
    analysis
  )}`;
}

function generatedTrackIdsFromSongs(songs: Array<Song | null | undefined>): Set<number | string> {
  return new Set(
    songs
      .filter((song): song is Song => Boolean(song) && song?.source === "ai_generated")
      .map(songKey)
  );
}

function generatedTrackIds(state: MusicState): Set<number | string> {
  return generatedTrackIdsFromSongs([
    state.currentSong,
    ...state.queue,
    ...(state.recommendation?.songs || []),
  ]);
}

function playlistGeneratedTrackIds(playlist: PlaylistApiState): Set<number | string> {
  return generatedTrackIdsFromSongs([
    playlist.current_song,
    ...(playlist.queue || []),
  ]);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchPlaylistState(gameId: number): Promise<PlaylistApiState | null> {
  if (typeof fetch === "undefined") return null;
  const response = await fetch(`${API_BASE}/music/playlist/${gameId}`, {
    credentials: "include",
  });
  if (!response.ok) return null;
  return (await response.json()) as PlaylistApiState;
}

function generatedMusicAnalysisMood(analysis?: Record<string, unknown>): string | undefined {
  return typeof analysis?.mood === "string" ? analysis.mood : undefined;
}

function generatedMusicAnalysisKeywords(analysis?: Record<string, unknown>): string[] | undefined {
  const keywords = analysis?.keywords;
  if (Array.isArray(keywords)) {
    return keywords.filter((item): item is string => typeof item === "string");
  }
  const sceneType = analysis?.scene_type;
  if (typeof sceneType === "string" && sceneType.trim()) {
    return [sceneType];
  }
  return undefined;
}

async function persistPlaylistSnapshotBeforeGeneration(
  gameId: number,
  currentSong: Song | null,
  queue: Song[],
  analysis?: Record<string, unknown>
): Promise<PlaylistApiState | null> {
  if (typeof fetch === "undefined") return null;
  const songs = [currentSong, ...queue].filter((item): item is Song => Boolean(item));
  if (songs.length === 0) return null;

  const response = await fetch(`${API_BASE}/music/playlist/${gameId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      songs,
      mood: generatedMusicAnalysisMood(analysis),
      keywords: generatedMusicAnalysisKeywords(analysis),
    }),
  });
  if (!response.ok) return null;
  return (await response.json()) as PlaylistApiState;
}

async function pollPlaylistForGeneratedTrack(
  gameId: number,
  initialGeneratedIds: Set<number | string>,
  onPlaylist: (playlist: PlaylistApiState) => void,
  attempts: number = GENERATED_MUSIC_POLL_ATTEMPTS,
  intervalMs: number = GENERATED_MUSIC_POLL_INTERVAL_MS
): Promise<boolean> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (attempt > 0) {
      await sleep(intervalMs);
    }
    const playlist = await fetchPlaylistState(gameId);
    if (!playlist) {
      continue;
    }
    onPlaylist(playlist);
    const generatedIds = playlistGeneratedTrackIds(playlist);
    if ([...generatedIds].some((id) => !initialGeneratedIds.has(id))) {
      return true;
    }
  }
  return false;
}

export const useMusicStore = create<MusicState>((set, get) => ({
  // 初始状态
  recommendation: null,
  isLoadingRecommendation: false,
  recommendationError: null,

  currentSong: null,
  isPlaying: false,
  volume: 0.5,
  currentTime: 0,
  duration: 0,
  audioElement: null,
  fadeInterval: null,
  voiceDuckActive: false,
  voiceDuckRestoreVolume: null,
  queue: [],
  playedSongs: [],
  playlistGameId: null,
  isLoadingPlaylist: false,
  isGeneratingAiMusic: false,
  aiMusicGenerationStatus: "idle",
  activeStoryText: null,
  activeGameId: null,

  // Setters
  setRecommendation: (recommendation) => set({ recommendation }),
  setIsLoadingRecommendation: (isLoadingRecommendation) =>
    set({ isLoadingRecommendation }),
  setRecommendationError: (recommendationError) => set({ recommendationError }),

  setCurrentSong: (currentSong) => set({ currentSong }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setVolume: (volume) => {
    set({ volume, voiceDuckActive: false, voiceDuckRestoreVolume: null });
    const { audioElement } = get();
    if (audioElement) {
      audioElement.volume = volume;
      console.log(`[MusicStore] Volume set to ${volume}, audioElement.volume = ${audioElement.volume}`);
    } else {
      console.log(`[MusicStore] Volume set to ${volume}, but no audioElement`);
    }
  },
  setCurrentTime: (currentTime) => set({ currentTime }),
  setDuration: (duration) => set({ duration }),
  setAudioElement: (audioElement) => set({ audioElement }),
  setFadeInterval: (fadeInterval) => set({ fadeInterval }),

  setQueue: (queue) => set({ queue }),
  setPlayedSongs: (playedSongs) => set({ playedSongs }),
  setPlaylistGameId: (playlistGameId) => set({ playlistGameId }),
  setActiveStoryText: (activeStoryText) => set({ activeStoryText }),
  setActiveGameId: (activeGameId) => set({ activeGameId }),

  // 播放控制
  play: () => {
    const { audioElement } = get();
    if (audioElement) {
      audioElement.play().catch((e) => {
        console.error("[MusicStore] Play failed:", e);
      });
      set({ isPlaying: true });
    }
  },

  pause: () => {
    const { audioElement } = get();
    if (audioElement) {
      audioElement.pause();
      set({ isPlaying: false });
    }
  },

  togglePlay: () => {
    const { isPlaying, play, pause } = get();
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  },

  seek: (time: number) => {
    const { audioElement } = get();
    if (audioElement) {
      audioElement.currentTime = time;
      set({ currentTime: time });
    }
  },

  changeVolume: (volume: number) => {
    const clampedVolume = Math.max(0, Math.min(1, volume));
    set({ volume: clampedVolume, voiceDuckActive: false, voiceDuckRestoreVolume: null });
    const { audioElement } = get();
    if (audioElement) {
      audioElement.volume = clampedVolume;
    }
  },

  fadeVolume: (targetVolume: number, duration: number = 1000) => {
    const { audioElement, fadeInterval } = get();
    if (!audioElement) return;

    // 清除已有的 fade interval，防止多个渐变同时运行
    if (fadeInterval) {
      clearInterval(fadeInterval);
    }

    // 直接从 audioElement 读取当前音量，避免 store 中的 volume 滞后
    const startVolume = audioElement.volume;
    const startTime = Date.now();
    const volumeDiff = targetVolume - startVolume;

    const newFadeInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const newVolume = startVolume + volumeDiff * progress;

      // 仅更新 DOM audio 音量，不更新 store
      // 避免 50ms/次 的 set() 调用导致 20 次重渲染/秒
      audioElement.volume = newVolume;

      if (progress >= 1) {
        clearInterval(newFadeInterval);
        // 渐变结束后一次性同步回 store
        set({ volume: targetVolume, fadeInterval: null });
      }
    }, 50);

    set({ fadeInterval: newFadeInterval });
  },

  duckForVoiceReading: (targetVolume: number = 0.2, duration: number = 250) => {
    const {
      audioElement,
      fadeVolume,
      isPlaying,
      volume,
      voiceDuckActive,
      voiceDuckRestoreVolume,
    } = get();
    if (!audioElement || !isPlaying) {
      return false;
    }
    if (voiceDuckActive) {
      return true;
    }

    const restoreVolume = voiceDuckRestoreVolume ?? volume;
    const duckedVolume = Math.min(restoreVolume, targetVolume);
    set({
      voiceDuckActive: true,
      voiceDuckRestoreVolume: restoreVolume,
    });
    fadeVolume(duckedVolume, duration);
    return true;
  },

  restoreAfterVoiceReading: (duration: number = 250) => {
    const { audioElement, fadeVolume, voiceDuckActive, voiceDuckRestoreVolume } = get();
    if (!voiceDuckActive || voiceDuckRestoreVolume === null) {
      return;
    }

    const restoreVolume = voiceDuckRestoreVolume;
    set({
      voiceDuckActive: false,
      voiceDuckRestoreVolume: null,
    });
    if (audioElement) {
      fadeVolume(restoreVolume, duration);
    } else {
      set({ volume: restoreVolume });
    }
  },

  // Playlist actions
  loadPlaylist: async (gameId: number) => {
    set({ isLoadingPlaylist: true });
    try {
      if (typeof fetch !== "undefined") {
        const response = await fetch(`${API_BASE}/music/playlist/${gameId}`, {
          credentials: "include",
        });
        if (response.ok) {
          const playlist = (await response.json()) as PlaylistApiState;
          set((state) =>
            playlistStateToStorePatchWithRecommendation(playlist, state.recommendation)
          );
          return;
        }
      }
      set({ playlistGameId: gameId });
    } catch (error) {
      console.error('[MusicStore] Failed to load playlist:', error);
      set({ playlistGameId: gameId });
    } finally {
      set({ isLoadingPlaylist: false });
    }
  },

  mergePlaylist: async (gameId: number, songs: Song[], mood?: string, keywords?: string[]) => {
    const { currentSong, queue } = get();
    const safeCurrentSong = currentSong ?? null;
    const safeQueue = queue || [];
    const safeSongs = songs || [];
    const merged = mergeSongsPreservingCurrent(safeCurrentSong, safeQueue, safeSongs);
    if (typeof fetch !== "undefined") {
      try {
        const response = await fetch(`${API_BASE}/music/playlist/${gameId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            songs: safeSongs,
            mood,
            keywords,
          }),
        });
        if (response.ok) {
          const playlist = (await response.json()) as PlaylistApiState;
          set((state) =>
            playlistStateToStorePatchWithRecommendation(playlist, state.recommendation)
          );
          return;
        }
      } catch (error) {
        console.warn("[MusicStore] Failed to persist playlist, using local queue:", error);
      }
    }
    set({
      currentSong: merged.currentSong,
      queue: merged.queue,
      playedSongs: [],
      playlistGameId: gameId,
    });
  },

  insertGeneratedTrack: (track: Song) => {
    const { currentSong, queue, recommendation } = get();
    const generatedId = songKey(track);
    const nextQueue = queue.filter((item) => songKey(item) !== generatedId);
    const nextCurrentSong = currentSong ?? track;
    if (currentSong) {
      nextQueue.unshift(track);
    }

    let nextRecommendation = recommendation;
    if (recommendation) {
      const songs = recommendation.songs.filter((item) => songKey(item) !== generatedId);
      const recommendationInsertAt = songs.length > 0 ? 1 : 0;
      songs.splice(recommendationInsertAt, 0, track);
      nextRecommendation = { ...recommendation, songs };
    }

    set({ currentSong: nextCurrentSong, queue: nextQueue, recommendation: nextRecommendation });
  },

  generateAiMusicForStory: async (storyText, gameId, analysis) => {
    if (!storyText.trim()) return;
    if (typeof window !== "undefined") {
      const disabled = window.localStorage.getItem("story_music_ai_generation_disabled");
      if (disabled === "1" || disabled === "true") return;
    }

    const inFlightKey = buildMusicGenerationKey(gameId, storyText, analysis);
    if (inFlightMusicGenerations.has(inFlightKey)) {
      return;
    }
    inFlightMusicGenerations.add(inFlightKey);

    set({ isGeneratingAiMusic: true, aiMusicGenerationStatus: "queued" });
    try {
      const initialGeneratedIds = generatedTrackIds(get());
      const snapshot = await persistPlaylistSnapshotBeforeGeneration(
        gameId,
        get().currentSong,
        get().queue,
        analysis
      );
      if (snapshot) {
        set((state) =>
          playlistStateToStorePatchWithRecommendation(snapshot, state.recommendation)
        );
      }
      await enqueueGeneratedMusic(storyText, gameId, analysis);
      set({ aiMusicGenerationStatus: "polling" });
      const generatedTrackReady = await pollPlaylistForGeneratedTrack(gameId, initialGeneratedIds, (playlist) => {
        set((state) =>
          playlistStateToStorePatchWithRecommendation(playlist, state.recommendation)
        );
      });
      set({
        aiMusicGenerationStatus: generatedTrackReady ? "ready" : "delayed",
      });
    } catch (error) {
      console.warn("[MusicStore] AI music generation unavailable:", error);
      set({ aiMusicGenerationStatus: "failed" });
    } finally {
      set({ isGeneratingAiMusic: false });
      inFlightMusicGenerations.delete(inFlightKey);
    }
  },

  syncPlaylistState: async (_gameId: number, _positionMs: number, _isPlaying: boolean, _volume: number) => {
    // Local-only: state is managed client-side
  },

  advanceQueue: async () => {
    const { queue, currentSong, playedSongs, playlistGameId } = get();
    if (playlistGameId && typeof fetch !== "undefined") {
      try {
        const response = await fetch(`${API_BASE}/music/playlist/${playlistGameId}/advance`, {
          method: "POST",
          credentials: "include",
        });
        if (response.ok) {
          const playlist = (await response.json()) as PlaylistApiState;
          set((state) =>
            playlistStateToStorePatchWithRecommendation(playlist, state.recommendation)
          );
          return;
        }
      } catch (error) {
        console.warn("[MusicStore] Failed to advance persisted playlist, using local queue:", error);
      }
    }

    if (queue.length === 0) {
      if (playedSongs.length === 0) return;
      const wrappedCurrent = playedSongs[0];
      const wrappedQueue = [
        ...playedSongs.slice(1),
        ...(currentSong ? [{ ...currentSong }] : []),
      ];
      set({
        currentSong: wrappedCurrent,
        queue: wrappedQueue,
        playedSongs: [],
      });
      return;
    }

    const nextSong = queue[0];
    const newQueue = queue.slice(1);
    set({
      currentSong: nextSong,
      queue: newQueue,
      playedSongs: currentSong ? [...playedSongs, { ...currentSong }] : playedSongs,
    });
  },

  // 清理
  reset: () => {
    const { audioElement, fadeInterval } = get();
    if (fadeInterval) {
      clearInterval(fadeInterval);
    }
    if (audioElement) {
      audioElement.pause();
      audioElement.src = "";
    }
    set({
      recommendation: null,
      isLoadingRecommendation: false,
      recommendationError: null,
      currentSong: null,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      audioElement: null,
      fadeInterval: null,
      voiceDuckActive: false,
      voiceDuckRestoreVolume: null,
      queue: [],
      playedSongs: [],
      playlistGameId: null,
      isLoadingPlaylist: false,
      isGeneratingAiMusic: false,
      aiMusicGenerationStatus: "idle",
    });
  },

  cleanup: () => {
    const { audioElement, fadeInterval } = get();
    if (fadeInterval) {
      clearInterval(fadeInterval);
    }
    if (audioElement) {
      audioElement.pause();
      audioElement.src = "";
      // 清理事件监听
      audioElement.onplay = null;
      audioElement.onpause = null;
      audioElement.ontimeupdate = null;
      audioElement.onended = null;
      audioElement.onloadedmetadata = null;
      audioElement.onerror = null;
    }
    set({
      audioElement: null,
      isPlaying: false,
      fadeInterval: null,
      voiceDuckActive: false,
      voiceDuckRestoreVolume: null,
    });
  },
}));

// API 函数
export async function fetchMusicRecommendation(
  storyText: string,
  gameId?: number,
  refresh: boolean = false,
  characterSettings?: CharacterSettings
): Promise<MusicRecommendation> {
  const response = await fetch(`${API_BASE}/music/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({
      story_text: storyText,
      game_id: gameId,
      refresh,
      character_settings: characterSettings,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(error.detail || "获取音乐推荐失败");
  }

  return response.json();
}

export async function fetchGeneratedMusic(
  storyText: string,
  gameId: number,
  analysis?: Record<string, unknown>
): Promise<
  | { track: Song; insert_policy: "future_queue" }
  | { status: "queued"; game_id: number; insert_policy: "future_queue" }
> {
  const response = await fetch(`${API_BASE}/music/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({
      story_text: storyText,
      game_id: gameId,
      analysis: analysis ?? {},
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(error.detail || "生成音乐失败");
  }

  return response.json();
}

export async function enqueueGeneratedMusic(
  storyText: string,
  gameId: number,
  analysis?: Record<string, unknown>
): Promise<{ status: "queued"; game_id: number; insert_policy: "future_queue" }> {
  const response = await fetch(`${API_BASE}/music/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({
      story_text: storyText,
      game_id: gameId,
      analysis: analysis ?? {},
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(error.detail || "生成音乐失败");
  }

  return response.json();
}

export async function fetchSongUrl(songId: number): Promise<string> {
  const response = await fetch(
    `${API_BASE}/music/song-url?song_id=${songId}`,
    {
      credentials: "include",
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(error.detail || "获取歌曲地址失败");
  }

  const data = await response.json();
  return data.url;
}

/**
 * 批量预加载所有歌曲的 URL
 * 使用 Promise.allSettled 确保即使部分失败也能继续
 */
export async function preloadAllSongUrls(
  songs: Song[],
  onProgress?: (loaded: number, total: number) => void
): Promise<Map<number | string, string>> {
  const urlMap = new Map<number | string, string>();
  const total = songs.length;
  let loaded = 0;

  // 并行加载所有歌曲 URL（限制并发数为 3，避免请求过多）
  const batchSize = 3;
  for (let i = 0; i < songs.length; i += batchSize) {
    const batch = songs.slice(i, i + batchSize);
    
    const results = await Promise.allSettled(
      batch.map(async (song) => {
        try {
          if (typeof song.id !== "number") {
            return { id: song.id, url: song.url ?? null };
          }
          const url = await fetchSongUrl(song.id);
          return { id: song.id, url };
        } catch (error) {
          console.warn(`[MusicStore] Failed to preload song ${song.id}:`, error);
          return { id: song.id, url: null };
        }
      })
    );

    results.forEach((result) => {
      if (result.status === 'fulfilled' && result.value.url) {
        urlMap.set(result.value.id, result.value.url);
      }
      loaded++;
    });

    onProgress?.(loaded, total);
  }

  console.log(`[MusicStore] Preloaded ${urlMap.size}/${total} song URLs`);
  return urlMap;
}

export async function searchMusic(
  keyword: string,
  limit: number = 10
): Promise<{ songs: Song[] }> {
  const response = await fetch(
    `${API_BASE}/music/search?keyword=${encodeURIComponent(
      keyword
    )}&limit=${limit}`,
    {
      credentials: "include",
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(error.detail || "搜索音乐失败");
  }

  return response.json();
}
