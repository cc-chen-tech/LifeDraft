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
import { useShallow } from "zustand/react/shallow";
import {
  useMusicStore,
  fetchMusicRecommendation,
  fetchSongUrl,
  Song,
} from "@/stores/useMusicStore";
import { useGameStore } from "@/stores/useGameStore";

interface MusicPlayerProps {
  storyText: string;
  gameId?: number;
  className?: string;
}

export function MusicPlayer({ storyText, gameId, className = "" }: MusicPlayerProps) {
  // ★ 使用 selector 分组订阅，避免全量重渲染
  // 以前：useMusicStore() 订阅全部状态，任何变更都触发整组件重渲染
  // 现在：按变更频率分组，currentTime(500ms) 的更新不会触发 recommendation 相关重渲染

  const { recommendation, isLoadingRecommendation, recommendationError } = useMusicStore(
    useShallow((state) => ({
      recommendation: state.recommendation,
      isLoadingRecommendation: state.isLoadingRecommendation,
      recommendationError: state.recommendationError,
    }))
  );

  const { currentSong, isPlaying, audioElement } = useMusicStore(
    useShallow((state) => ({
      currentSong: state.currentSong,
      isPlaying: state.isPlaying,
      audioElement: state.audioElement,
    }))
  );

  const { currentTime, duration } = useMusicStore(
    useShallow((state) => ({
      currentTime: state.currentTime,
      duration: state.duration,
    }))
  );

  const volume = useMusicStore((state) => state.volume);

  const { queue, playedSongs, playlistGameId } = useMusicStore(
    useShallow((state) => ({
      queue: state.queue,
      playedSongs: state.playedSongs,
      playlistGameId: state.playlistGameId,
    }))
  );

  // Actions 是稳定引用，单独 selector 不会导致额外重渲染
  const setRecommendation = useMusicStore((state) => state.setRecommendation);
  const setIsLoadingRecommendation = useMusicStore((state) => state.setIsLoadingRecommendation);
  const setRecommendationError = useMusicStore((state) => state.setRecommendationError);
  const setCurrentSong = useMusicStore((state) => state.setCurrentSong);
  const setIsPlaying = useMusicStore((state) => state.setIsPlaying);
  const setVolume = useMusicStore((state) => state.setVolume);
  const setCurrentTime = useMusicStore((state) => state.setCurrentTime);
  const setDuration = useMusicStore((state) => state.setDuration);
  const setAudioElement = useMusicStore((state) => state.setAudioElement);
  const play = useMusicStore((state) => state.play);
  const pause = useMusicStore((state) => state.pause);
  const cleanup = useMusicStore((state) => state.cleanup);
  const fadeVolume = useMusicStore((state) => state.fadeVolume);
  const advanceQueue = useMusicStore((state) => state.advanceQueue);

  const hasFetchedRef = useRef(false);
  const isLoadingSongRef = useRef(false);
  const [playError, setPlayError] = useState<string | null>(null);
  const [skippedSongs, setSkippedSongs] = useState<Set<number>>(new Set());
  const skippedSongsRef = useRef<Set<number>>(new Set()); // 同步跟踪跳过的歌曲
  const preloadedAudioRef = useRef<HTMLAudioElement | null>(null);
  const preloadedSongRef = useRef<Song | null>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null); // 当前正在播放的音频
  const [isSwitchingSong, setIsSwitchingSong] = useState(false); // 切换歌曲时的加载状态
  const [preloadProgress, setPreloadProgress] = useState(0); // 预加载进度
  const songUrlMapRef = useRef<Map<number, string>>(new Map()); // 预加载的歌曲 URL 映射
  const retryCountRef = useRef<Map<number, number>>(new Map()); // 每首歌的重试计数
  const timeUpdateThrottleRef = useRef<number>(0); // timeupdate 节流，减少 React re-render
  const lastLoadedSongRef = useRef<number | null>(null); // 追踪已加载的歌曲，防止重复加载

  // 播放列表模式：从 DB 恢复的持久化播放列表
  const isPlaylistMode = storyText === "persisted" && playlistGameId !== null;

  // 获取音乐推荐
  const fetchRecommendation = useCallback(async (isRefresh = false) => {
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

      const characterSettings = useGameStore.getState().characterSettings;
      const result = await fetchMusicRecommendation(storyText, gameId, isRefresh, characterSettings);
      setRecommendation(result);
      
      // URL 已由后端批量返回，无需前端预加载
      // 将 URL 存入映射表供备用
      const urlMap = new Map<number, string>();
      result.songs.forEach((song: Song) => {
        if (song.url) {
          urlMap.set(song.id, song.url);
        }
      });
      songUrlMapRef.current = urlMap;
      setPreloadProgress(100);
      console.log(`[MusicPlayer] Received ${urlMap.size}/${result.songs.length} song URLs from backend`);
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
  const loadAndPlaySong = useCallback(async (song: Song, isPreload: boolean = false) => {
    // 防止同时加载多个歌曲
    if (isLoadingSongRef.current && !isPreload) {
      console.log(`[MusicPlayer] Already loading a song, skipping: ${song.name}`);
      return;
    }
    if (!isPreload) {
      // 如果同一首歌已经在播放且未结束，仅恢复播放
      if (currentSong?.id === song.id && audioElement && !audioElement.ended && audioElement.src) {
        if (audioElement.paused) {
          try { await audioElement.play(); } catch { /* 播放被中断，忽略 */ }
        }
        return;
      }
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
      if (!url && !isPreload) {
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

      // 创建新的音频元素 — 使用后端流式代理绕过 CDN Referer 限制
      const streamUrl = `/api/music/stream/${song.id}`;
      const audio = new Audio(streamUrl);
      audio.preload = "auto";
      audio.volume = volume;

      // 绑定事件
      audio.onplay = () => setIsPlaying(true);
      audio.onpause = () => setIsPlaying(false);
      audio.ontimeupdate = () => {
        // 500ms 节流，减少 timeupdate 触发的 React re-render 频率
        // 250ms → 500ms：进一步降低重渲染开销，改善播放卡顿
        const now = Date.now();
        if (now - timeUpdateThrottleRef.current >= 500) {
          timeUpdateThrottleRef.current = now;
          setCurrentTime(audio.currentTime);
        }
      };
      audio.onloadedmetadata = () => setDuration(audio.duration || 0);
      audio.onended = () => {
        setIsPlaying(false);
        setCurrentTime(0);
        activeAudioRef.current = null; // 清理活动音频引用
        setAudioElement(null); // 清理 store 中的音频引用，让播放列表效果触发
        // 自动播放下一首 - 使用传入的 song 参数而不是 currentSong
        if (isPlaylistMode && playlistGameId) {
          advanceQueue();
        } else if (recommendation?.songs.length) {
          const currentIndex = recommendation.songs.findIndex(
            (s) => s.id === song.id
          );
          const nextIndex = (currentIndex + 1) % recommendation.songs.length;
          console.log(`[MusicPlayer] Song ended, playing next: ${recommendation.songs[nextIndex].name}`);
          loadAndPlaySong(recommendation.songs[nextIndex]);
        }
      };
      // 缓冲事件处理（解决播放中突然停止）
      audio.onstalled = () => {
        console.log(`[MusicPlayer] Audio stalled for "${song.name}" — buffering...`);
        setPlayError(`"${song.name}" 缓冲中...`);
      };
      audio.onwaiting = () => {
        console.log(`[MusicPlayer] Audio waiting for data: "${song.name}"`);
        setPlayError(`"${song.name}" 缓冲中...`);
        // 5秒后如果还在 waiting 状态，尝试重新加载当前位置
        setTimeout(() => {
          if (audio.readyState < 3 && !audio.paused) {
            const currentPos = audio.currentTime;
            audio.load();
            audio.currentTime = currentPos;
            audio.play().catch(() => {});
          }
        }, 5000);
      };
      audio.oncanplay = () => {
        // 清除缓冲相关的错误提示
        setPlayError((prev) =>
          prev && (prev.includes("缓冲中") || prev.includes("等待数据")) ? null : prev
        );
      };

      audio.onerror = async (e) => {
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
          attempt: (retryCountRef.current.get(song.id) || 0) + 1,
          maxRetries: 3,
          networkOnline: navigator.onLine,
          src: audio.src ? '(has src)' : '(no src)',
          timestamp: new Date().toISOString(),
        });
        
        setIsPlaying(false);
        
        // 检查是否可以重试：每首歌最多重试 3 次
        const currentRetries = retryCountRef.current.get(song.id) || 0;
        if (currentRetries < 3) {
          retryCountRef.current.set(song.id, currentRetries + 1);
          const retryDelay = Math.min(1000 * Math.pow(2, currentRetries), 4000);
          console.log(`[MusicPlayer] Retrying "${song.name}" via stream proxy (attempt ${currentRetries + 1}/3, delay ${retryDelay}ms)`);
          setPlayError(`"${song.name}" 加载失败，正在重试 (${currentRetries + 1}/3)...`);
          
          // 清理当前失败的音频
          audio.pause();
          audio.src = "";
          activeAudioRef.current = null;
          
          // 指数退避重试，流式代理会重新获取 CDN URL（给后端更多恢复时间）
          setTimeout(() => loadAndPlaySong(song), retryDelay);
          return;
        }
        
        // 3 次重试全部失败，自动切换下一首
        setPlayError(`"${song.name}" 暂时无法播放，正在切换下一首...`);
        
        // 同步更新 ref 和 state
        skippedSongsRef.current.add(song.id);
        setSkippedSongs(new Set(skippedSongsRef.current));
        
        // 清理当前音频
        activeAudioRef.current = null;
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
              setTimeout(() => loadAndPlaySong(nextSong), 1500);
              return;
            }
            nextIndex = (nextIndex + 1) % recommendation.songs.length;
            attempts++;
          }
          
          // 所有歌曲都跳过了，清空列表重试
          console.log('[MusicPlayer] All songs skipped, resetting skip list');
          skippedSongsRef.current = new Set();
          setSkippedSongs(new Set());
          retryCountRef.current = new Map(); // 重置重试计数
        }
      };

      // 先设置当前歌曲（不播放），等待音频准备好
      setCurrentSong({ ...song, url });
      setAudioElement(audio);
      activeAudioRef.current = audio; // 记录当前活动的音频
      
      // 播放（等待缓冲后再播放，减少卡顿）
      try {
        audio.volume = volume;
        const playWhenReady = () => {
          audio.play().then(() => {
            console.log(`[MusicPlayer] Playback started for "${song.name}"`);
          }).catch((err) => {
            console.warn(`[MusicPlayer] Play interrupted for "${song.name}":`, err);
          });
        };
        // 如果已有足够缓冲（HAVE_FUTURE_DATA），直接播放；否则等待 canplay 事件
        if (audio.readyState >= 3) {
          playWhenReady();
        } else {
          audio.addEventListener('canplay', playWhenReady, { once: true });
          // 安全超时：10秒后如果还没触发 canplay，强制尝试播放
          setTimeout(() => {
            if (audio.paused && activeAudioRef.current === audio) {
              console.log(`[MusicPlayer] canplay timeout, forcing play for "${song.name}"`);
              playWhenReady();
            }
          }, 10000);
        }
      } catch (playError) {
        console.warn(`[MusicPlayer] Play setup error for "${song.name}":`, playError);
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
      // 使用后端流式代理 URL 进行预加载
      const streamUrl = `/api/music/stream/${nextSong.id}`;
      const audio = new Audio(streamUrl);
      audio.preload = "auto";
      audio.volume = 0; // 静音预加载
      
      // 等待音频足够加载
      audio.oncanplaythrough = () => {
        preloadedAudioRef.current = audio;
        preloadedSongRef.current = { ...nextSong };
        console.log(`[MusicPlayer] Preloaded next song: ${nextSong.name}`);
      };
    } catch (error) {
      console.warn(`[MusicPlayer] Failed to preload next song: ${nextSong.name}`, error);
    }
  }, [recommendation, currentSong]);

  // 自动播放第一首歌（单独处理，避免循环依赖）
  // 播放列表模式下 currentSong 已从 DB 恢复，无需自动播放
  useEffect(() => {
    if (recommendation && recommendation.songs.length > 0 && !currentSong && !audioElement && !isPlaylistMode) {
      loadAndPlaySong(recommendation.songs[0]);
    }
  }, [recommendation, currentSong, audioElement, loadAndPlaySong, isPlaylistMode]);

  // 播放列表模式：当 currentSong 变化且尚未加载时，自动加载播放
  useEffect(() => {
    if (isPlaylistMode && currentSong && currentSong.id !== lastLoadedSongRef.current) {
      lastLoadedSongRef.current = currentSong.id;
      if (!audioElement || audioElement.ended) {
        loadAndPlaySong(currentSong);
      }
    }
  }, [isPlaylistMode, currentSong, audioElement, loadAndPlaySong]);

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
        console.log(`[MusicPlayer] Audio may be stuck (${stuckCount}/8)`);
        
        // 连续4次检测都卡住（共12秒），开始恢复策略
        if (stuckCount >= 4 && stuckCount <= 5) {
          // 第一层：仅尝试 play()
          console.log('[MusicPlayer] Recovery layer 1: trying play()...');
          audioElement.play().then(() => {
            console.log('[MusicPlayer] Recovery: play() succeeded');
            stuckCount = 0;
          }).catch(() => {
            console.log('[MusicPlayer] Recovery: play() failed, will retry next interval');
          });
        } else if (stuckCount >= 6 && stuckCount <= 7) {
          // 第二层：尝试 seek + play()
          console.log('[MusicPlayer] Recovery layer 2: trying seek + play()...');
          try {
            const seekTarget = Math.max(0, audioElement.currentTime - 0.5);
            audioElement.currentTime = seekTarget;
            audioElement.play().then(() => {
              console.log('[MusicPlayer] Recovery: seek + play() succeeded');
              stuckCount = 0;
            }).catch(() => {
              console.log('[MusicPlayer] Recovery: seek + play() failed, will retry next interval');
            });
          } catch {
            console.log('[MusicPlayer] Recovery: seek threw error');
          }
        } else if (stuckCount >= 8) {
          // 第三层：24秒完全无进度，切歌
          console.log('[MusicPlayer] Recovery layer 3: switching to next song (stuck for 24s)');
          stuckCount = 0;
          if (isPlaylistMode && playlistGameId) {
            advanceQueue();
          } else if (recommendation?.songs.length) {
            const currentIndex = recommendation.songs.findIndex((s) => s.id === currentSong.id);
            const nextIndex = (currentIndex + 1) % recommendation.songs.length;
            loadAndPlaySong(recommendation.songs[nextIndex]);
          }
        }
      } else {
        stuckCount = 0;
      }
      
      lastTime = audioElement.currentTime;
    }, 3000); // 每3秒检查一次

    return () => clearInterval(checkInterval);
  }, [audioElement, isPlaying, currentSong, recommendation, loadAndPlaySong, playlistGameId]);

  // 播放控制
  const togglePlay = () => {
    if (audioElement) {
      if (isPlaying) {
        pause();
      } else {
        play();
      }
    } else if (isPlaylistMode && currentSong) {
      loadAndPlaySong(currentSong);
    } else if (recommendation?.songs.length) {
      loadAndPlaySong(recommendation.songs[0]);
    }
  };

  const playNext = () => {
    if (isPlaylistMode && playlistGameId) {
      // 播放列表模式：通过后端推进队列
      if (audioElement) {
        audioElement.pause();
        audioElement.src = "";
        audioElement.onplay = null;
        audioElement.onpause = null;
        audioElement.ontimeupdate = null;
        audioElement.onloadedmetadata = null;
        audioElement.onended = null;
        audioElement.onerror = null;
        setAudioElement(null);
      }
      activeAudioRef.current = null;
      advanceQueue();
      return;
    }

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
    if (storyText && !hasFetchedRef.current && !recommendation && !isPlaylistMode) {
      hasFetchedRef.current = true;
      fetchRecommendation();
    }
  }, [storyText, recommendation, fetchRecommendation, isPlaylistMode]);

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
      className={`bg-card border rounded-lg p-4 shadow-sm ${className}`}
    >
      {/* 头部：标题和刷新按钮 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Music className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">{isPlaylistMode ? "播放列表" : "场景音乐"}</span>
          {!isPlaylistMode && recommendation && (
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
        {!isPlaylistMode && <Button
          variant="ghost"
          size="sm"
          onClick={() => fetchRecommendation(true)}
          disabled={isLoadingRecommendation}
          aria-label="刷新音乐推荐"
          title="刷新音乐推荐"
        >
          {isLoadingRecommendation ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
        </Button>}
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

      {/* 切换歌曲加载状态 */}
      {isSwitchingSong && (
        <div className="flex items-center justify-center py-2 text-muted-foreground">
          <Loader2 className="w-3 h-3 animate-spin mr-2" />
          <span className="text-xs">切换歌曲中...</span>
        </div>
      )}

      {/* 播放器 */}
      {((recommendation && recommendation.songs.length > 0) || (isPlaylistMode && currentSong)) && (
        <div className="space-y-3">
          {/* 当前歌曲信息 */}
          <div className="text-sm">
            <div className="font-medium truncate">
              {currentSong?.name || recommendation?.songs[0]?.name || "未知歌曲"}
            </div>
            <div className="text-muted-foreground text-xs truncate">
              {currentSong
                ? `${currentSong.artists.join(" / ")} · ${currentSong.album}`
                : recommendation?.songs[0]
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
                disabled={!(recommendation?.songs.length || isPlaylistMode)}
                aria-label="上一首"
                title="上一首"
              >
                <SkipBack className="w-4 h-4" />
              </Button>
              <Button
                variant="default"
                size="icon"
                className="h-10 w-10"
                onClick={togglePlay}
                disabled={!(recommendation?.songs.length || isPlaylistMode || currentSong)}
                aria-label={isPlaying ? "暂停" : "播放"}
                title={isPlaying ? "暂停" : "播放"}
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
                disabled={!(recommendation?.songs.length || isPlaylistMode)}
                aria-label="下一首"
                title="下一首"
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
                aria-label={volume === 0 ? "取消静音" : "静音"}
                title={volume === 0 ? "取消静音" : "静音"}
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
          {((recommendation?.songs?.length ?? 0) > 1 || (isPlaylistMode && queue.length > 0)) && (
            <div className="mt-3 pt-3 border-t">
              <div className="text-xs text-muted-foreground mb-2 flex items-center justify-between">
                <span>
                  {isPlaylistMode
                    ? `播放队列 (${queue.length}首)`
                    : `推荐歌曲 (${recommendation!.songs.length}首)`}
                </span>
                {!isPlaylistMode && recommendation!.songs.length < 5 && (
                  <span className="text-amber-500">匹配歌曲较少</span>
                )}
              </div>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {(isPlaylistMode ? queue : recommendation!.songs).map((song) => (
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
