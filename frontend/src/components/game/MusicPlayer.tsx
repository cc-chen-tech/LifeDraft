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
  Song,
} from "@/stores/useMusicStore";

interface MusicPlayerProps {
  storyText: string;
  gameId?: number;
  className?: string;
}

export function MusicPlayer({ storyText, gameId, className = "" }: MusicPlayerProps) {
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
    setRecommendation,
    setIsLoadingRecommendation,
    setRecommendationError,
    setCurrentSong,
    setIsPlaying,
    setVolume,
    setCurrentTime,
    setDuration,
    setAudioElement,
    play,
    pause,
    cleanup,
    fadeVolume,
  } = useMusicStore();

  const hasFetchedRef = useRef(false);
  const isLoadingSongRef = useRef(false);
  const [playError, setPlayError] = useState<string | null>(null);
  const [skippedSongs, setSkippedSongs] = useState<Set<number>>(new Set());
  const preloadedAudioRef = useRef<HTMLAudioElement | null>(null);
  const preloadedSongRef = useRef<Song | null>(null);

  // 获取音乐推荐
  const fetchRecommendation = useCallback(async () => {
    if (!storyText || isLoadingRecommendation) return;

    setIsLoadingRecommendation(true);
    setRecommendationError(null);

    try {
      const result = await fetchMusicRecommendation(storyText, gameId);
      setRecommendation(result);
    } catch (error) {
      console.error("[MusicPlayer] Failed to fetch recommendation:", error);
      setRecommendationError(
        error instanceof Error ? error.message : "获取推荐失败"
      );
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
  ]);
  
  // 加载并播放歌曲
  const loadAndPlaySong = useCallback(async (song: Song) => {
    // 防止同时加载多个歌曲
    if (isLoadingSongRef.current) {
      console.log(`[MusicPlayer] Already loading a song, skipping: ${song.name}`);
      return;
    }
    isLoadingSongRef.current = true;
    
    try {
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
        // 触发垃圾回收
        setAudioElement(null);
      }
      
      // 清除之前的播放错误
      setPlayError(null);

      // 获取播放地址
      const url = await fetchSongUrl(song.id);
      if (!url) {
        console.warn(`[MusicPlayer] 无法获取歌曲播放地址: ${song.name}`);
        setPlayError(`"${song.name}" 因版权限制无法播放`);
        setSkippedSongs(prev => new Set(prev).add(song.id));
        // 自动尝试下一首
        if (recommendation?.songs.length) {
          const currentIndex = recommendation.songs.findIndex((s) => s.id === song.id);
          const nextIndex = (currentIndex + 1) % recommendation.songs.length;
          if (nextIndex !== currentIndex && !skippedSongs.has(recommendation.songs[nextIndex].id)) {
            console.log(`[MusicPlayer] 尝试播放下一首: ${recommendation.songs[nextIndex].name}`);
            setTimeout(() => loadAndPlaySong(recommendation.songs[nextIndex]), 500);
          }
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
        // 自动播放下一首 - 使用传入的 song 参数而不是 currentSong
        if (recommendation?.songs.length) {
          const currentIndex = recommendation.songs.findIndex(
            (s) => s.id === song.id
          );
          const nextIndex = (currentIndex + 1) % recommendation.songs.length;
          console.log(`[MusicPlayer] Song ended, playing next: ${recommendation.songs[nextIndex].name}`);
          loadAndPlaySong(recommendation.songs[nextIndex]);
        }
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
        setSkippedSongs(prev => new Set(prev).add(song.id));
        
        // 清理当前音频
        audio.pause();
        audio.src = "";
        
        // 播放出错时尝试下一首
        if (recommendation?.songs.length) {
          const currentIndex = recommendation.songs.findIndex((s) => s.id === song.id);
          const nextIndex = (currentIndex + 1) % recommendation.songs.length;
          // 确保不会无限循环 - 如果所有歌曲都跳过了，重置跳过列表
          const allSkipped = recommendation.songs.every(s => 
            s.id === song.id || skippedSongs.has(s.id)
          );
          if (allSkipped) {
            setSkippedSongs(new Set());
            console.log('[MusicPlayer] All songs skipped, resetting skip list');
          }
          if (nextIndex !== currentIndex) {
            console.log(`[MusicPlayer] Error occurred, trying next song: ${recommendation.songs[nextIndex].name}`);
            setTimeout(() => loadAndPlaySong(recommendation.songs[nextIndex]), 800);
          }
        }
      };

      // 先设置当前歌曲（不播放），等待音频准备好
      setCurrentSong({ ...song, url });
      setAudioElement(audio);
      
      // 播放（使用 try-catch 捕获播放错误）
      try {
        // 先静音，然后淡入
        audio.volume = 0;
        await audio.play();
        // 淡入效果（1.5秒从0到目标音量）
        const targetVolume = volume;
        const fadeDuration = 1500;
        const startTime = Date.now();
        
        const fadeIn = setInterval(() => {
          const elapsed = Date.now() - startTime;
          const progress = Math.min(elapsed / fadeDuration, 1);
          const newVolume = targetVolume * progress;
          
          if (audio) {
            audio.volume = newVolume;
          }
          
          if (progress >= 1) {
            clearInterval(fadeIn);
          }
        }, 50);
      } catch (playError) {
        console.warn(`[MusicPlayer] Play interrupted for "${song.name}":`, playError);
        // 播放被中断（可能是用户切换了歌曲），不显示错误
      }
    } catch (error) {
      console.error("[MusicPlayer] Failed to load song:", error);
    } finally {
      // 重置加载标志
      isLoadingSongRef.current = false;
    }
  }, [audioElement, volume, recommendation, currentSong, setAudioElement, setCurrentSong, setIsPlaying, setCurrentTime, setDuration]);

  // 预加载下一首歌曲
  const preloadNextSong = useCallback(async () => {
    if (!recommendation?.songs.length || !currentSong) return;
    
    const currentIndex = recommendation.songs.findIndex((s) => s.id === currentSong.id);
    const nextIndex = (currentIndex + 1) % recommendation.songs.length;
    const nextSong = recommendation.songs[nextIndex];
    
    // 如果下一首已经预加载过了，跳过
    if (preloadedSongRef.current?.id === nextSong.id) return;
    
    try {
      const url = await fetchSongUrl(nextSong.id);
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
            if (recommendation?.songs.length) {
              const currentIndex = recommendation.songs.findIndex((s) => s.id === currentSong.id);
              const nextIndex = (currentIndex + 1) % recommendation.songs.length;
              loadAndPlaySong(recommendation.songs[nextIndex]);
            }
          });
          stuckCount = 0;
        }
      } else {
        stuckCount = 0;
      }
      
      lastTime = audioElement.currentTime;
    }, 3000); // 每3秒检查一次

    return () => clearInterval(checkInterval);
  }, [audioElement, isPlaying, currentSong, recommendation, loadAndPlaySong]);

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
    if (!recommendation?.songs.length || !currentSong) return;

    const currentIndex = recommendation.songs.findIndex(
      (s) => s.id === currentSong.id
    );
    const nextIndex = (currentIndex + 1) % recommendation.songs.length;
    loadAndPlaySong(recommendation.songs[nextIndex]);
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

  // 格式化时间
  const formatTime = (seconds: number) => {
    if (!seconds || isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // 初始加载推荐
  useEffect(() => {
    if (storyText && !hasFetchedRef.current && !recommendation) {
      hasFetchedRef.current = true;
      fetchRecommendation();
    }
  }, [storyText, recommendation, fetchRecommendation]);

  // 清理
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  // 如果没有故事文本，不显示
  if (!storyText) {
    return null;
  }

  return (
    <div
      className={`bg-card border rounded-lg p-4 shadow-sm ${className}`}
    >
      {/* 头部：标题和刷新按钮 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Music className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">场景音乐</span>
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
          onClick={fetchRecommendation}
          disabled={isLoadingRecommendation}
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

      {/* 错误状态 */}
      {recommendationError && (
        <div className="text-sm text-destructive text-center py-2">
          {recommendationError}
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

      {/* 播放器 */}
      {recommendation && recommendation.songs.length > 0 && (
        <div className="space-y-3">
          {/* 当前歌曲信息 */}
          <div className="text-sm">
            <div className="font-medium truncate">
              {currentSong?.name || recommendation.songs[0]?.name || "未知歌曲"}
            </div>
            <div className="text-muted-foreground text-xs truncate">
              {currentSong 
                ? `${currentSong.artists.join(" / ")} · ${currentSong.album}`
                : recommendation.songs[0] 
                  ? `${recommendation.songs[0].artists.join(" / ")} · ${recommendation.songs[0].album}`
                  : ""
              }
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
                disabled={!recommendation.songs.length}
              >
                <SkipBack className="w-4 h-4" />
              </Button>
              <Button
                variant="default"
                size="icon"
                className="h-10 w-10"
                onClick={togglePlay}
                disabled={!recommendation.songs.length}
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
                disabled={!recommendation.songs.length}
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
          {recommendation.songs.length > 1 && (
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
      {recommendation && recommendation.songs.length === 0 && (
        <div className="text-sm text-muted-foreground text-center py-4">
          未找到匹配的音乐
        </div>
      )}
    </div>
  );
}
