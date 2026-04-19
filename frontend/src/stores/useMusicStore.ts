/**
 * useMusicStore — 音乐播放状态管理
 *
 * 管理故事音乐推荐和播放状态
 */
import { create } from "zustand";

export interface Song {
  id: number;
  name: string;
  artists: string[];
  album: string;
  duration: number;
  url?: string;
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
  songs: Song[];
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

  // 播放控制
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  seek: (time: number) => void;
  changeVolume: (volume: number) => void;
  fadeVolume: (targetVolume: number, duration?: number) => void;  // 音量渐变

  // 清理
  reset: () => void;
  cleanup: () => void;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.host}`
    : "http://localhost:8000");

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

  // Setters
  setRecommendation: (recommendation) => set({ recommendation }),
  setIsLoadingRecommendation: (isLoadingRecommendation) =>
    set({ isLoadingRecommendation }),
  setRecommendationError: (recommendationError) => set({ recommendationError }),

  setCurrentSong: (currentSong) => set({ currentSong }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setVolume: (volume) => {
    set({ volume });
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
    set({ volume: clampedVolume });
    const { audioElement } = get();
    if (audioElement) {
      audioElement.volume = clampedVolume;
    }
  },

  fadeVolume: (targetVolume: number, duration: number = 1000) => {
    const { audioElement, volume } = get();
    if (!audioElement) return;

    const startVolume = volume;
    const startTime = Date.now();
    const volumeDiff = targetVolume - startVolume;

    const fadeInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const newVolume = startVolume + volumeDiff * progress;

      audioElement.volume = newVolume;
      set({ volume: newVolume });

      if (progress >= 1) {
        clearInterval(fadeInterval);
      }
    }, 50);
  },

  // 清理
  reset: () => {
    const { audioElement } = get();
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
    });
  },

  cleanup: () => {
    const { audioElement } = get();
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
    set({ audioElement: null, isPlaying: false });
  },
}));

// API 函数
export async function fetchMusicRecommendation(
  storyText: string,
  gameId?: number,
  refresh: boolean = false
): Promise<MusicRecommendation> {
  const response = await fetch(`${API_BASE_URL}/api/music/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ story_text: storyText, game_id: gameId, refresh }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(error.detail || "获取音乐推荐失败");
  }

  return response.json();
}

export async function fetchSongUrl(songId: number): Promise<string> {
  const response = await fetch(
    `${API_BASE_URL}/api/music/song-url?song_id=${songId}`,
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
): Promise<Map<number, string>> {
  const urlMap = new Map<number, string>();
  const total = songs.length;
  let loaded = 0;

  // 并行加载所有歌曲 URL（限制并发数为 3，避免请求过多）
  const batchSize = 3;
  for (let i = 0; i < songs.length; i += batchSize) {
    const batch = songs.slice(i, i + batchSize);
    
    const results = await Promise.allSettled(
      batch.map(async (song) => {
        try {
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
    `${API_BASE_URL}/api/music/search?keyword=${encodeURIComponent(
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
