"use client";

/**
 * MusicPlayer — 故事音乐播放器组件
 *
 * 根据故事内容推荐并播放匹配的音乐
 */
import { useEffect, useRef, useCallback, useState } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Music,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  useMusicStore,
  fetchMusicRecommendation,
  fetchSongUrl,
  getMusicSourceLabel,
  Song,
} from "@/stores/useMusicStore";
import { storyTextToHash } from "@/lib/storyTextHash";

interface MusicPlayerProps {
  storyText: string;
  gameId?: number;
  className?: string;
  autoFetchRecommendation?: boolean;
  embedded?: boolean;
}

function hasMusicBrief(brief: Record<string, unknown> | undefined): brief is Record<string, unknown> {
  return brief !== undefined && Object.keys(brief).length > 0;
}

export function MusicPlayer({
  storyText,
  gameId,
  className = "",
  autoFetchRecommendation = true,
  embedded = false,
}: MusicPlayerProps) {
  const {
    recommendation,
    isLoadingRecommendation,
    recommendationError,
    currentSong,
    isPlaying,
    volume,
    currentTime,
    duration,
    audioElement,
    isGeneratingAiMusic,
    setRecommendation,
    setIsLoadingRecommendation,
    setRecommendationError,
    setCurrentSong,
    setIsPlaying,
    setVolume,
    setCurrentTime,
    setDuration,
    setAudioElement,
    mergePlaylist,
    advanceQueue,
    generateAiMusicForStory,
    play,
    pause,
    cleanup,
    fadeVolume,
  } = useMusicStore();

  const fetchedRecommendationKeyRef = useRef<string | null>(null);
  const generatedMusicStoryKeyRef = useRef<string | null>(null);
  const isLoadingSongRef = useRef(false);
  const [playError, setPlayError] = useState<string | null>(null);
  const [skippedSongs, setSkippedSongs] = useState<Set<number | string>>(new Set());
  const skippedSongsRef = useRef<Set<number | string>>(new Set()); // 同步跟踪跳过的歌曲
  const preloadedAudioRef = useRef<HTMLAudioElement | null>(null);
  const preloadedSongRef = useRef<Song | null>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null); // 当前正在播放的音频
  const [isSwitchingSong, setIsSwitchingSong] = useState(false); // 切换歌曲时的加载状态
  const [preloadProgress, setPreloadProgress] = useState(0); // 预加载进度
  const songUrlMapRef = useRef<Map<number | string, string>>(new Map()); // 预加载的歌曲 URL 映射

  const getFallbackNextSong = useCallback((song: Song) => {
    const songs = useMusicStore.getState().recommendation?.songs || recommendation?.songs || [];
    if (songs.length === 0) {
      return null;
    }
    const currentIndex = songs.findIndex((candidate) => candidate.id === song.id);
    const safeIndex = currentIndex >= 0 ? currentIndex : 0;
    return songs[(safeIndex + 1) % songs.length] || null;
  }, [recommendation]);

  // 获取音乐推荐
  const fetchRecommendation = useCallback(async (refresh: boolean = false) => {
    if (!storyText || isLoadingRecommendation) return;

    setIsLoadingRecommendation(true);
    setRecommendationError(null);
    setPreloadProgress(0);

    try {
      // 检查 fetch 是否可用（某些测试环境可能不支持）
      if (typeof fetch === 'undefined') {
        console.warn('[MusicPlayer] fetch API not available, skipping music recommendation');
        setRecommendationError('音乐服务暂不可用');
        return;
      }

      const result = await fetchMusicRecommendation(storyText, gameId, refresh);
      setRecommendation(result);
      if (gameId) {
        await mergePlaylist(gameId, result.songs, result.mood, result.keywords);
      }
      
      // URL 已由后端批量返回，无需前端预加载
      // 将 URL 存入映射表供备用
      const urlMap = new Map<number | string, string>();
      result.songs.forEach((song: Song) => {
        if (song.url) {
          urlMap.set(song.id, song.url);
        }
      });
      songUrlMapRef.current = urlMap;
      setPreloadProgress(100);
      console.log(`[MusicPlayer] Received ${urlMap.size}/${result.songs.length} song URLs from backend`);

      const storyHash = storyTextToHash(storyText);
      const generationKey = gameId ? `${gameId}:${storyHash}` : null;
      if (
        gameId &&
        generationKey &&
        hasMusicBrief(result.music_brief) &&
        generatedMusicStoryKeyRef.current !== generationKey
      ) {
        generatedMusicStoryKeyRef.current = generationKey;
        void generateAiMusicForStory(storyText, gameId, result.music_brief);
      }
    } catch (error) {
      console.error("[MusicPlayer] Failed to fetch recommendation:", error);
      setRecommendationError("音乐服务暂不可用");
    } finally {
      setIsLoadingRecommendation(false);
    }
  }, [
    storyText,
    gameId,
    isLoadingRecommendation,
    setRecommendation,
    setIsLoadingRecommendation,
    setRecommendationError,
    mergePlaylist,
    generateAiMusicForStory,
  ]);
  
  // 加载并播放歌曲
  const loadAndPlaySong = useCallback(async (song: Song, isPreload: boolean = false) => {
    // 防止同时加载多个歌曲
    if (isLoadingSongRef.current && !isPreload) {
      console.log(`[MusicPlayer] Already loading a song, skipping: ${song.name}`);
      return;
    }
    if (!isPreload) {
      isLoadingSongRef.current = true;
      setIsSwitchingSong(true); // 显示切换加载状态
    }
    
    try {
      // 如果是预加载，不清理当前播放的音频
      if (!isPreload) {
        // 停止所有正在播放的音频（包括预加载的）
        if (activeAudioRef.current) {
          console.log('[MusicPlayer] Stopping active audio from ref');
          activeAudioRef.current.pause();
          activeAudioRef.current.src = "";
          activeAudioRef.current = null;
        }
        
        // 清理旧的音频 - 完全清理避免多个音频同时播放
        if (audioElement) {
          audioElement.pause();
          audioElement.src = "";
          // 移除所有事件监听器
          audioElement.onplay = null;
          audioElement.onpause = null;
          audioElement.ontimeupdate = null;
          audioElement.onloadedmetadata = null;
          audioElement.onended = null;
          audioElement.onerror = null;
        }
        
        // 清理预加载的音频
        if (preloadedAudioRef.current) {
          preloadedAudioRef.current.pause();
          preloadedAudioRef.current.src = "";
          preloadedAudioRef.current = null;
          preloadedSongRef.current = null;
        }
        
        // 重置音频元素状态
        setAudioElement(null);
        
        // 清除之前的播放错误
        setPlayError(null);
      }

      // 获取播放地址（优先使用歌曲自带的 URL，后端已批量返回）
      let url = song.url || songUrlMapRef.current.get(song.id);
      
      // 如果没有 URL，尝试实时获取（降级方案）
      if (!url && !isPreload && typeof song.id === "number") {
        console.log(`[MusicPlayer] Song ${song.id} has no URL, fetching realtime...`);
        try {
          url = await fetchSongUrl(song.id);
          if (url) {
            songUrlMapRef.current.set(song.id, url);
          }
        } catch (error) {
          console.warn(`[MusicPlayer] Failed to fetch URL for song ${song.id}:`, error);
        }
      }
      
      if (!url) {
        console.warn(`[MusicPlayer] 无法获取歌曲播放地址: ${song.name}`);
        setPlayError(`"${song.name}" 因版权限制无法播放`);
        
        // 同步更新 ref 和 state
        skippedSongsRef.current.add(song.id);
        setSkippedSongs(new Set(skippedSongsRef.current));
        
        // 自动尝试下一首 - 使用 ref 确保同步
        if (recommendation?.songs.length) {
          const currentIndex = recommendation.songs.findIndex((s) => s.id === song.id);
          // 找到下一首未跳过的歌曲
          let nextIndex = (currentIndex + 1) % recommendation.songs.length;
          let attempts = 0;
          const maxAttempts = recommendation.songs.length;
          
          while (attempts < maxAttempts) {
            const nextSong = recommendation.songs[nextIndex];
            if (!skippedSongsRef.current.has(nextSong.id)) {
              console.log(`[MusicPlayer] 尝试播放下一首: ${nextSong.name}`);
              setTimeout(() => loadAndPlaySong(nextSong), 800);
              return;
            }
            nextIndex = (nextIndex + 1) % recommendation.songs.length;
            attempts++;
          }
          
          // 所有歌曲都跳过了，清空列表重试
          console.log('[MusicPlayer] All songs failed, resetting skip list');
          skippedSongsRef.current = new Set();
          setSkippedSongs(new Set());
        }
        return;
      }

      // 创建新的音频元素
      const audio = new Audio(url);
      audio.volume = volume;

      // 绑定事件
      audio.onplay = () => setIsPlaying(true);
      audio.onpause = () => setIsPlaying(false);
      audio.ontimeupdate = () => setCurrentTime(audio.currentTime);
      audio.onloadedmetadata = () => setDuration(audio.duration || 0);
      audio.onended = () => {
        setIsPlaying(false);
        setCurrentTime(0);
        activeAudioRef.current = null; // 清理活动音频引用
        void (async () => {
          await advanceQueue();
          const nextSong = useMusicStore.getState().currentSong;
          if (nextSong && nextSong.id !== song.id) {
            console.log(`[MusicPlayer] Song ended, advancing playlist: ${nextSong.name}`);
            await loadAndPlaySong(nextSong);
            return;
          }
          const fallbackSong = getFallbackNextSong(song);
          if (fallbackSong) {
            console.log(`[MusicPlayer] Song ended, playing fallback next: ${fallbackSong.name}`);
            await loadAndPlaySong(fallbackSong);
          }
        })();
      };
      audio.onerror = (e) => {
        const errorCode = audio.error?.code;
        const errorMessage = audio.error?.message;
        const errorTypes: { [key: number]: string } = {
          1: '下载被中断',
          2: '网络错误',
          3: '解码错误',
          4: '格式不支持/资源不可用'
        };
        const errorType = errorCode ? errorTypes[errorCode] || `未知错误(${errorCode})` : '未知错误';
        
        console.error(`[MusicPlayer] Audio error for "${song.name}": ${errorType}`, {
          code: errorCode,
          message: errorMessage,
          url: url?.substring(0, 50) + '...',
          event: e
        });
        
        setIsPlaying(false);
        setPlayError(`"${song.name}" ${errorType}，尝试下一首...`);
        
        // 同步更新 ref 和 state
        skippedSongsRef.current.add(song.id);
        setSkippedSongs(new Set(skippedSongsRef.current));
        
        // 清理当前音频
        activeAudioRef.current = null; // 清理活动音频引用
        audio.pause();
        audio.src = "";
        
        // 播放出错时尝试下一首
        if (recommendation?.songs.length) {
          const currentIndex = recommendation.songs.findIndex((s) => s.id === song.id);
          // 找到下一首未跳过的歌曲
          let nextIndex = (currentIndex + 1) % recommendation.songs.length;
          let attempts = 0;
          const maxAttempts = recommendation.songs.length;
          
          while (attempts < maxAttempts) {
            const nextSong = recommendation.songs[nextIndex];
            if (!skippedSongsRef.current.has(nextSong.id)) {
              console.log(`[MusicPlayer] Error occurred, trying next song: ${nextSong.name}`);
              setTimeout(() => loadAndPlaySong(nextSong), 800);
              return;
            }
            nextIndex = (nextIndex + 1) % recommendation.songs.length;
            attempts++;
          }
          
          // 所有歌曲都跳过了，清空列表重试
          console.log('[MusicPlayer] All songs skipped, resetting skip list');
          skippedSongsRef.current = new Set();
          setSkippedSongs(new Set());
        }
      };

      // 先设置当前歌曲（不播放），等待音频准备好
      setCurrentSong({ ...song, url });
      setAudioElement(audio);
      activeAudioRef.current = audio; // 记录当前活动的音频
      
      // 播放（使用 try-catch 捕获播放错误）
      try {
        audio.volume = volume;
        await audio.play();
      } catch (playError) {
        console.warn(`[MusicPlayer] Play interrupted for "${song.name}":`, playError);
        // 播放被中断（可能是用户切换了歌曲），不显示错误
      }
    } catch (error) {
      console.error("[MusicPlayer] Failed to load song:", error);
    } finally {
      // 重置加载标志
      if (!isPreload) {
        isLoadingSongRef.current = false;
        setIsSwitchingSong(false); // 隐藏切换加载状态
      }
    }
  }, [audioElement, volume, recommendation, currentSong, setAudioElement, setCurrentSong, setIsPlaying, setCurrentTime, setDuration, advanceQueue, getFallbackNextSong]);

  // 预加载下一首歌曲
  const preloadNextSong = useCallback(async () => {
    if (!recommendation?.songs.length || !currentSong) return;
    
    const currentIndex = recommendation.songs.findIndex((s) => s.id === currentSong.id);
    const nextIndex = (currentIndex + 1) % recommendation.songs.length;
    const nextSong = recommendation.songs[nextIndex];
    
    // 如果下一首已经预加载过了，跳过
    if (preloadedSongRef.current?.id === nextSong.id) return;
    
    try {
      const url = nextSong.url || (
        typeof nextSong.id === "number" ? await fetchSongUrl(nextSong.id) : null
      );
      if (url) {
        // 创建并预加载音频
        const audio = new Audio(url);
        audio.preload = "auto";
        audio.volume = 0; // 静音预加载
        
        // 等待音频足够加载
        audio.oncanplaythrough = () => {
          preloadedAudioRef.current = audio;
          preloadedSongRef.current = { ...nextSong, url };
          console.log(`[MusicPlayer] Preloaded next song: ${nextSong.name}`);
        };
      }
    } catch (error) {
      console.warn(`[MusicPlayer] Failed to preload next song: ${nextSong.name}`, error);
    }
  }, [recommendation, currentSong]);

  // 自动播放第一首歌（单独处理，避免循环依赖）
  useEffect(() => {
    if (recommendation && recommendation.songs.length > 0 && !currentSong && !audioElement) {
      loadAndPlaySong(recommendation.songs[0]);
    }
  }, [recommendation, currentSong, audioElement, loadAndPlaySong]);

  // 当前歌曲播放后预加载下一首
  useEffect(() => {
    if (isPlaying && currentSong) {
      // 延迟5秒后开始预加载（给用户一些时间听当前歌曲）
      const timer = setTimeout(() => {
        preloadNextSong();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [isPlaying, currentSong, preloadNextSong]);

  // 监控音乐是否意外停止（缓冲不足、网络问题等）
  useEffect(() => {
    if (!audioElement || !isPlaying || !currentSong) return;

    let lastTime = audioElement.currentTime;
    let stuckCount = 0;

    const checkInterval = setInterval(() => {
      if (!audioElement) return;
      
      // 如果音乐正在播放但时间没有前进，可能是卡住了
      if (audioElement.currentTime === lastTime && !audioElement.paused) {
        stuckCount++;
        console.log(`[MusicPlayer] Audio may be stuck (${stuckCount}/3)`);
        
        // 连续3次检测都卡住，尝试恢复播放
        if (stuckCount >= 3) {
          console.log('[MusicPlayer] Attempting to resume playback...');
          audioElement.play().catch(() => {
            // 如果恢复失败，跳到下一首
            console.log('[MusicPlayer] Resume failed, switching to next song');
            void (async () => {
              await advanceQueue();
              const nextSong = useMusicStore.getState().currentSong;
              if (nextSong && nextSong.id !== currentSong.id) {
                await loadAndPlaySong(nextSong);
                return;
              }
              const fallbackSong = getFallbackNextSong(currentSong);
              if (fallbackSong) {
                await loadAndPlaySong(fallbackSong);
              }
            })();
          });
          stuckCount = 0;
        }
      } else {
        stuckCount = 0;
      }
      
      lastTime = audioElement.currentTime;
    }, 3000); // 每3秒检查一次

    return () => clearInterval(checkInterval);
  }, [audioElement, isPlaying, currentSong, recommendation, loadAndPlaySong, advanceQueue, getFallbackNextSong]);

  // 播放控制
  const togglePlay = () => {
    if (audioElement) {
      if (isPlaying) {
        pause();
      } else {
        play();
      }
    } else if (recommendation?.songs.length) {
      loadAndPlaySong(recommendation.songs[0]);
    }
  };

  const playNext = () => {
    if (!currentSong) return;

    void (async () => {
      await advanceQueue();
      const nextSong = useMusicStore.getState().currentSong;
      if (nextSong && nextSong.id !== currentSong.id) {
        await loadAndPlaySong(nextSong);
        return;
      }
      const fallbackSong = getFallbackNextSong(currentSong);
      if (fallbackSong) {
        await loadAndPlaySong(fallbackSong);
      }
    })();
  };

  const playPrev = () => {
    if (!recommendation?.songs.length || !currentSong) return;

    const currentIndex = recommendation.songs.findIndex(
      (s) => s.id === currentSong.id
    );
    const prevIndex =
      (currentIndex - 1 + recommendation.songs.length) %
      recommendation.songs.length;
    loadAndPlaySong(recommendation.songs[prevIndex]);
  };

  const handleSeek = (value: number[]) => {
    const time = value[0];
    if (audioElement) {
      audioElement.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleVolumeChange = (value: number[]) => {
    const vol = value[0];
    setVolume(vol);
    // 注意：store 中的 setVolume 会自动同步 audioElement.volume
  };

  const displaySong = currentSong || recommendation?.songs[0] || null;
  const sourceLabel = getMusicSourceLabel(displaySong?.source);
  const hasRecommendationSongs = Boolean(recommendation?.songs.length);

  // 格式化时间
  const formatTime = (seconds: number) => {
    if (!seconds || isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // 初始加载推荐
  useEffect(() => {
    const storyHash = storyTextToHash(storyText);
    const recommendationKey = gameId ? `${gameId}:${storyHash}` : `story:${storyHash}`;
    if (
      autoFetchRecommendation &&
      storyText &&
      fetchedRecommendationKeyRef.current !== recommendationKey
    ) {
      fetchedRecommendationKeyRef.current = recommendationKey;
      fetchRecommendation();
    }
  }, [autoFetchRecommendation, storyText, gameId, fetchRecommendation]);

  // 清理
  useEffect(() => {
    return () => {
      // 停止所有音频
      if (activeAudioRef.current) {
        activeAudioRef.current.pause();
        activeAudioRef.current.src = "";
        activeAudioRef.current = null;
      }
      if (preloadedAudioRef.current) {
        preloadedAudioRef.current.pause();
        preloadedAudioRef.current.src = "";
        preloadedAudioRef.current = null;
      }
      cleanup();
    };
  }, [cleanup]);

  // 如果没有故事文本，不显示
  if (!storyText) {
    return null;
  }

  return (
    <div
      data-testid={embedded ? "sound-music-channel" : undefined}
      className={`${embedded ? "space-y-3" : "bg-card border rounded-lg p-4 shadow-sm"} ${className}`}
    >
      {/* 头部：标题和刷新按钮 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Music className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-medium">{embedded ? "音乐" : "场景音乐"}</h3>
          {recommendation && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded">
                {recommendation.mood}
              </span>
              {recommendation.environment && (
                <span className="text-xs px-1.5 py-0.5 bg-secondary/50 rounded">
                  {recommendation.environment}
                </span>
              )}
              {recommendation.story_style && (
                <span className="text-xs px-1.5 py-0.5 bg-secondary/50 rounded">
                  {recommendation.story_style}
                </span>
              )}
            </div>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => fetchRecommendation(true)}
          disabled={isLoadingRecommendation}
          title="换一批"
          aria-label="换一批"
        >
          {isLoadingRecommendation ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
        </Button>
      </div>

      {/* 加载状态 */}
      {isLoadingRecommendation && !recommendation && (
        <div className="flex items-center justify-center py-4 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />
          <span className="text-sm">正在分析故事氛围...</span>
        </div>
      )}

      {/* 预加载进度 */}
      {!isLoadingRecommendation && recommendation && preloadProgress < 100 && preloadProgress > 0 && (
        <div className="flex items-center justify-center py-2 text-muted-foreground">
          <Loader2 className="w-3 h-3 animate-spin mr-2" />
          <span className="text-xs">预加载歌曲 {preloadProgress}%</span>
        </div>
      )}

      {/* 错误状态 */}
      {recommendationError && (
        <div className="text-sm text-destructive text-center py-2">
          音乐服务暂不可用
        </div>
      )}

      {/* 播放错误提示 */}
      {playError && (
        <div className="text-xs text-amber-500 text-center py-1 bg-amber-500/10 rounded">
          {playError}
          {skippedSongs.size > 0 && (
            <span className="ml-1 text-muted-foreground">
              (已跳过 {skippedSongs.size} 首)
            </span>
          )}
        </div>
      )}

      {/* 切换歌曲加载状态 */}
      {isSwitchingSong && (
        <div className="flex items-center justify-center py-2 text-muted-foreground">
          <Loader2 className="w-3 h-3 animate-spin mr-2" />
          <span className="text-xs">切换歌曲中...</span>
        </div>
      )}

      {recommendation && recommendation.songs.length > 0 && isGeneratingAiMusic && (
        <div className="flex items-center justify-center rounded bg-primary/5 px-2 py-2 text-primary">
          <Loader2 className="w-3 h-3 animate-spin mr-2" />
          <span className="text-xs">正在生成原创场景音乐，完成后加入下一首</span>
        </div>
      )}

      {/* 播放器 */}
      {displaySong && (
        <div className="space-y-3">
          {/* 当前歌曲信息 */}
          <div className="text-sm">
            <div className="flex min-w-0 items-center gap-2">
              <span className="font-medium truncate">
                {displaySong?.name || "未知歌曲"}
              </span>
              {sourceLabel && (
                <span className="shrink-0 rounded border border-primary/30 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                  {sourceLabel}
                </span>
              )}
            </div>
            <div className="text-muted-foreground text-xs truncate">
              {displaySong
                ? `${displaySong.artists.join(" / ")} · ${displaySong.album}`
                : ""}
            </div>
          </div>

          {/* 进度条 */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-10 text-right">
              {formatTime(currentTime)}
            </span>
            <Slider
              value={[currentTime]}
              max={duration || 100}
              step={1}
              onValueChange={handleSeek}
              className="flex-1"
            />
            <span className="text-xs text-muted-foreground w-10">
              {formatTime(duration)}
            </span>
          </div>

          {/* 控制按钮 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={playPrev}
                disabled={!hasRecommendationSongs}
                title="上一首"
                aria-label="上一首"
              >
                <SkipBack className="w-4 h-4" />
              </Button>
              <Button
                variant="default"
                size="icon"
                className="h-10 w-10"
                onClick={togglePlay}
                disabled={!audioElement && !hasRecommendationSongs}
                title={isPlaying ? "暂停" : "播放"}
                aria-label={isPlaying ? "暂停" : "播放"}
              >
                {isPlaying ? (
                  <Pause className="w-5 h-5" />
                ) : (
                  <Play className="w-5 h-5" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={playNext}
                disabled={!hasRecommendationSongs}
                title="下一首"
                aria-label="下一首"
              >
                <SkipForward className="w-4 h-4" />
              </Button>
            </div>

            {/* 音量控制 */}
            <div className="flex items-center gap-2 w-24">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => handleVolumeChange([volume === 0 ? 0.5 : 0])}
                title={volume === 0 ? "取消静音" : "静音"}
                aria-label={volume === 0 ? "取消静音" : "静音"}
              >
                {volume === 0 ? (
                  <VolumeX className="w-3 h-3" />
                ) : (
                  <Volume2 className="w-3 h-3" />
                )}
              </Button>
              <Slider
                value={[volume]}
                max={1}
                step={0.1}
                onValueChange={handleVolumeChange}
              />
            </div>
          </div>

          {/* 歌曲列表 */}
          {recommendation && recommendation.songs.length > 1 && (
            <div className="mt-3 pt-3 border-t">
              <div className="text-xs text-muted-foreground mb-2 flex items-center justify-between">
                <span>推荐歌曲 ({recommendation.songs.length}首)</span>
                {recommendation.songs.length < 5 && (
                  <span className="text-amber-500">匹配歌曲较少</span>
                )}
              </div>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {recommendation.songs.map((song) => (
                  <button
                    key={song.id}
                    onClick={() => loadAndPlaySong(song)}
                    className={`w-full text-left px-2 py-1.5 rounded text-xs truncate transition-colors ${
                      currentSong?.id === song.id
                        ? "bg-primary/10 text-primary"
                        : "hover:bg-muted"
                    }`}
                  >
                    <span className="font-medium">{song.name}</span>
                    <span className="text-muted-foreground ml-1">
                      - {song.artists.join(" / ")}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 无结果 */}
      {recommendation && recommendation.songs.length === 0 && isGeneratingAiMusic && (
        <div className="flex items-center justify-center py-4 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />
          <span className="text-sm">正在生成原创场景音乐...</span>
        </div>
      )}

      {recommendation && recommendation.songs.length === 0 && !isGeneratingAiMusic && (
        <div className="text-sm text-muted-foreground text-center py-4">
          音乐服务暂不可用，故事可继续进行
        </div>
      )}
    </div>
  );
}
