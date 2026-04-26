"use client";

/**
 * GlobalMusicPlayer — compact mini player wrapper.
 *
 * Mounted in RootLayout so it survives page navigation.
 * Shows a slim bottom bar by default; expands to full MusicPlayer on click.
 */
import { useEffect, useRef, useState } from "react";
import { MusicPlayer } from "./MusicPlayer";
import { useMusicStore } from "@/stores/useMusicStore";
import { Play, Pause, ChevronUp, ChevronDown } from "lucide-react";

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

  // Determine storyText: use activeStoryText from play page, or "persisted" if music already loaded
  const storyText =
    activeStoryText || (recommendation || currentSong || queue.length > 0 ? "persisted" : "");

  // Only render if we have storyText (either from play page or persisted state)
  if (!storyText) return null;

  // Determine gameId: prefer activeGameId from play page, fallback to playlistGameId
  const effectiveGameId = activeGameId ?? playlistGameId ?? undefined;
  const songName = currentSong?.name || recommendation?.songs?.[0]?.name || "";
  const artistName = currentSong?.artists?.join(", ") || "";
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="fixed z-50 bottom-0 left-0 right-0 md:bottom-4 md:left-auto md:right-4 md:w-80">
      {/* Expanded: full MusicPlayer panel */}
      {isExpanded && (
        <div className="bg-card border rounded-t-lg md:rounded-lg shadow-lg max-h-[60vh] overflow-y-auto">
          <MusicPlayer
            storyText={storyText}
            gameId={effectiveGameId}
            className="rounded-none border-0 shadow-none"
          />
        </div>
      )}

      {/* Mini player bar — always visible */}
      <div
        className="relative bg-card/95 backdrop-blur-sm border-t md:border md:rounded-b-lg flex items-center gap-2 px-3 py-2 cursor-pointer"
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
          onClick={(e) => {
            e.stopPropagation();
            togglePlay();
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
          {artistName && (
            <div className="text-xs text-muted-foreground truncate">
              {artistName}
            </div>
          )}
        </div>

        {/* Expand / Collapse */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
          className="flex-shrink-0 w-6 h-6 flex items-center justify-center text-muted-foreground"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronUp className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}
