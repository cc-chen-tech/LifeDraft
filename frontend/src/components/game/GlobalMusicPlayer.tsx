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
  const audioElement = useMusicStore((state) => state.audioElement);

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

  // Handle play/pause from the mini bar.
  // If audioElement exists, use store.togglePlay (direct control).
  // If no audioElement but we have a recommendation, the MusicPlayer handles auto-play internally.
  const handleMiniPlayPause = () => {
    if (audioElement) {
      togglePlay();
    } else {
      // No audio element — expand the player so user can pick a song
      setIsExpanded(true);
    }
  };

  return (
    <div
      data-testid="global-music-player"
      className="fixed z-50 top-0 left-0 right-0 safe-area-pt mt-2 md:top-auto md:mt-0 md:bottom-4 md:left-auto md:right-4 md:w-80"
    >
      {/* MusicPlayer always mounted to keep audio alive.
          Use opacity-0 + h-0 + overflow-hidden instead of display:none
          so the browser never pauses audio playback. */}
      <div
        className={
          isExpanded
            ? "bg-card border rounded-b-lg md:rounded-lg shadow-lg max-h-[60vh] overflow-y-auto"
            : "opacity-0 h-0 overflow-hidden pointer-events-none absolute top-full left-0 right-0"
        }
        aria-hidden={!isExpanded}
      >
        <MusicPlayer
          storyText={storyText}
          gameId={effectiveGameId}
          className="rounded-none border-0 shadow-none"
        />
      </div>

      {/* Mini player bar — always visible */}
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
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}
