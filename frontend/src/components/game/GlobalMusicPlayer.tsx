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
import { ChevronUp, ChevronDown, Volume2 } from "lucide-react";

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
  const currentTime = useMusicStore((state) => state.currentTime);
  const duration = useMusicStore((state) => state.duration);
  const activeReadingContext = useStoryVoiceStore((state) => state.activeReadingContext);
  const activeAutoReadText = useStoryVoiceStore((state) => state.activeAutoReadText);
  const activeAutoReadReady = useStoryVoiceStore((state) => state.activeAutoReadReady);
  const readingState = useStoryVoiceStore((state) => state.readingState);
  const autoReadEnabled = useStoryVoiceStore((state) => state.autoReadEnabled);

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
  const soundTitle = songName || "声音";
  const soundStatus =
    artistName ||
    (readingState === "loading"
      ? "正在准备朗读"
      : readingState === "playing"
        ? "正在朗读故事"
        : readingState === "paused"
          ? "朗读已暂停"
          : "音乐与朗读");

  const musicStatusLabel =
    isPlaying
      ? "音乐播放中"
      : currentSong || recommendation || queue.length > 0
        ? "音乐待播放"
        : "音乐待推荐";
  const readingStatusLabel =
    readingState === "loading"
      ? "朗读准备中"
      : readingState === "playing"
        ? "朗读中"
        : readingState === "paused"
          ? "朗读暂停"
          : readingState === "ready"
            ? "朗读待播放"
            : readingState === "failed"
              ? "朗读失败"
              : activeReadingContext
                ? "朗读待开始"
                : "朗读待生成";

  return (
    <div
      role="region"
      aria-label="声音"
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
        role={isExpanded ? "group" : undefined}
        aria-label={isExpanded ? "音乐和朗读" : undefined}
      >
        <div data-testid="unified-sound-panel" className="divide-y divide-border/70 p-3">
          <div
            data-testid="sound-mixer-overview"
            className="flex flex-wrap items-center gap-2 pb-3 text-xs text-muted-foreground"
          >
            <div className="mr-auto flex min-w-0 items-center gap-2 text-foreground">
              <Volume2 className="h-4 w-4 shrink-0 text-primary" />
              <span className="text-sm font-medium">声音</span>
            </div>
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-primary">
              {musicStatusLabel}
            </span>
            <span className="rounded-full bg-secondary/60 px-2 py-0.5">
              {readingStatusLabel}
            </span>
            <span className="rounded-full bg-secondary/60 px-2 py-0.5">
              {autoReadEnabled ? "自动朗读" : "手动朗读"}
            </span>
            <button
              type="button"
              aria-label="收起声音"
              title="收起声音"
              onClick={() => setIsExpanded(false)}
              className="ml-auto flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
          <div
            data-testid="sound-music-section"
            className="py-3"
          >
            {storyText ? (
              <MusicPlayer
                storyText={storyText}
                gameId={effectiveGameId}
                className="rounded-none border-0 bg-transparent p-0 shadow-none"
                autoFetchRecommendation={shouldAutoFetchRecommendation}
                embedded
              />
            ) : (
              <div className="text-sm text-muted-foreground">
                故事生成完成后会自动推荐音乐。
              </div>
            )}
          </div>

          {activeReadingContext && (
            <div
              data-testid="sound-reading-section"
              className="py-3"
            >
              <div data-testid="sound-reading-channel" className="space-y-3">
                <StoryVoiceControls
                  currentContext={activeReadingContext}
                  autoReadText={activeAutoReadText}
                  autoReadReady={activeAutoReadReady}
                  compact
                  embedded
                  enablePlaybackControls
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {!isExpanded && (
        <div
          data-testid="global-music-mini-bar"
          className="relative bg-card/95 backdrop-blur-sm border-b md:border md:rounded-lg flex items-center gap-2 px-3 py-2 cursor-pointer"
          onClick={() => setIsExpanded(true)}
        >
          {/* Progress bar - thin line at top */}
          <div className="absolute top-0 left-0 right-0 h-0.5 bg-muted">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Volume2 className="w-4 h-4" />
          </div>

          {/* Song info */}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">
              {soundTitle}
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {soundStatus}
            </div>
          </div>

          <button
            aria-label="展开声音"
            title="展开声音"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(true);
            }}
            className="flex-shrink-0 w-6 h-6 flex items-center justify-center text-muted-foreground"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
