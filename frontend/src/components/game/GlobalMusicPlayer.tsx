"use client";

/**
 * GlobalMusicPlayer — compact mini player wrapper.
 *
 * Mounted in RootLayout so it survives page navigation.
 * Shows a slim bottom bar by default; expands to full MusicPlayer on click.
 *
 * IMPORTANT: MusicPlayer must always stay mounted to keep the Audio element alive.
 * We use opacity-0 + h-0 + overflow-hidden (NOT display:none / hidden) so the
 * browser never pauses the audio.
 */
import { useEffect, useRef, useState } from "react";
import { MusicPlayer } from "./MusicPlayer";
import { StoryVoiceControls } from "./StoryVoiceControls";
import { useMusicStore } from "@/stores/useMusicStore";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";
import { Play, Pause, ChevronUp, ChevronDown, Volume2 } from "lucide-react";

export function GlobalMusicPlayer() {
  const hasInitRef = useRef(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const loadPlaylist = useMusicStore((state) => state.loadPlaylist);
  const playlistGameId = useMusicStore((state) => state.playlistGameId);
  const currentSong = useMusicStore((state) => state.currentSong);
  const queue = useMusicStore((state) => state.queue);
  const recommendation = useMusicStore((state) => state.recommendation);
  const activeStoryText = useMusicStore((state) => state.activeStoryText);
  const activeGameId = useMusicStore((state) => state.activeGameId);
  const isPlaying = useMusicStore((state) => state.isPlaying);
  const togglePlay = useMusicStore((state) => state.togglePlay);
  const currentTime = useMusicStore((state) => state.currentTime);
  const duration = useMusicStore((state) => state.duration);
  const audioElement = useMusicStore((state) => state.audioElement);
  const activeReadingContext = useStoryVoiceStore((state) => state.activeReadingContext);
  const activeAutoReadText = useStoryVoiceStore((state) => state.activeAutoReadText);
  const activeAutoReadReady = useStoryVoiceStore((state) => state.activeAutoReadReady);
  const readingState = useStoryVoiceStore((state) => state.readingState);

  // On mount, try to restore the active game playlist from localStorage
  useEffect(() => {
    if (hasInitRef.current) return;
    hasInitRef.current = true;

    const storedGameId = localStorage.getItem("gameId");
    if (storedGameId) {
      const gameId = parseInt(storedGameId, 10);
      if (!isNaN(gameId)) {
        loadPlaylist(gameId);
      }
    }
  }, [loadPlaylist]);

  // Determine gameId: prefer activeGameId from play page, fallback to playlistGameId
  const effectiveGameId = activeGameId ?? playlistGameId ?? undefined;

  // Determine storyText: use activeStoryText from play page, or "persisted" if music already loaded
  const storyText =
    activeStoryText || (recommendation || currentSong || queue.length > 0 ? "persisted" : "");
  const shouldAutoFetchRecommendation = Boolean(activeStoryText && effectiveGameId);

  useEffect(() => {
    if (!isExpanded) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsExpanded(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isExpanded]);

  // Only render when at least one sound surface has context.
  if (!storyText && !activeReadingContext) return null;

  const songName = currentSong?.name || recommendation?.songs?.[0]?.name || "";
  const artistName = currentSong?.artists?.join(", ") || "";
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
  const soundStatus = artistName || (readingState === "idle" ? "音乐与朗读" : "故事朗读中");

  // Handle play/pause from the mini bar.
  // If audioElement exists, use store.togglePlay (direct control).
  // If no audioElement but we have a recommendation, the MusicPlayer handles auto-play internally.
  const handleMiniPlayPause = () => {
    if (audioElement) {
      togglePlay();
    } else {
      // No audio element — expand the sound panel so user can pick music or read story.
      setIsExpanded(true);
    }
  };

  return (
    <div
      role="region"
      aria-label="声音控制"
      data-testid="global-music-player"
      className="fixed z-50 top-16 left-0 right-0 safe-area-pt mt-2 md:left-auto md:right-4 md:w-80"
    >
      {/* MusicPlayer always mounted to keep audio alive.
          Use opacity-0 + h-0 + overflow-hidden instead of display:none
          so the browser never pauses audio playback. */}
      <div
        className={
          isExpanded
            ? "bg-card border rounded-b-lg md:rounded-lg shadow-lg max-h-[68vh] overflow-y-auto"
            : "opacity-0 h-0 overflow-hidden pointer-events-none absolute top-full left-0 right-0"
        }
        aria-hidden={!isExpanded}
        role={isExpanded ? "region" : undefined}
        aria-label={isExpanded ? "声音面板" : undefined}
      >
        <div className="px-4 pt-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Volume2 className="h-4 w-4 text-primary" />
            声音
          </div>
        </div>
        {storyText ? (
          <MusicPlayer
            storyText={storyText}
            gameId={effectiveGameId}
            className="rounded-none border-0 shadow-none"
            autoFetchRecommendation={shouldAutoFetchRecommendation}
          />
        ) : (
          <div className="px-4 py-3 text-sm text-muted-foreground">
            故事生成完成后会自动推荐音乐。
          </div>
        )}
        {activeReadingContext && (
          <div className="px-4 pb-4">
            <StoryVoiceControls
              currentContext={activeReadingContext}
              autoReadText={activeAutoReadText}
              autoReadReady={activeAutoReadReady}
              compact
              embedded
              enablePlaybackControls
            />
          </div>
        )}
      </div>

      {/* Sound mini bar — always visible */}
      <div
        data-testid="global-music-mini-bar"
        className="relative bg-card/95 backdrop-blur-sm border-b md:border md:rounded-lg flex items-center gap-2 px-3 py-2 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Progress bar - thin line at top */}
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-muted">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Play / Pause */}
        <button
          aria-label={audioElement ? (isPlaying ? "暂停音乐" : "播放音乐") : "打开声音面板"}
          title={audioElement ? (isPlaying ? "暂停音乐" : "播放音乐") : "打开声音面板"}
          onClick={(e) => {
            e.stopPropagation();
            handleMiniPlayPause();
          }}
          className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-primary text-primary-foreground"
        >
          {isPlaying ? (
            <Pause className="w-4 h-4" />
          ) : (
            <Play className="w-4 h-4 ml-0.5" />
          )}
        </button>

        {/* Song info */}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate">
          {songName || "等待音乐..."}
          </div>
          <div className="text-xs text-muted-foreground truncate">
            {soundStatus}
          </div>
        </div>

        {/* Expand / Collapse */}
        <button
          aria-label={isExpanded ? "收起声音面板" : "展开声音面板"}
          title={isExpanded ? "收起声音面板" : "展开声音面板"}
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
          className="flex-shrink-0 w-6 h-6 flex items-center justify-center text-muted-foreground"
        >
          {isExpanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}
