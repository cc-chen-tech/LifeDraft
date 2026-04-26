"use client";

/**
 * GlobalMusicPlayer — application-level music player wrapper.
 *
 * Mounted in RootLayout so it survives page navigation.
 * Reads the active gameId from localStorage and loads the persisted playlist.
 */
import { useEffect, useRef } from "react";
import { MusicPlayer } from "./MusicPlayer";
import { useMusicStore } from "@/stores/useMusicStore";

export function GlobalMusicPlayer() {
  const hasInitRef = useRef(false);

  const loadPlaylist = useMusicStore((state) => state.loadPlaylist);
  const playlistGameId = useMusicStore((state) => state.playlistGameId);
  const currentSong = useMusicStore((state) => state.currentSong);
  const queue = useMusicStore((state) => state.queue);
  const recommendation = useMusicStore((state) => state.recommendation);
  const activeStoryText = useMusicStore((state) => state.activeStoryText);
  const activeGameId = useMusicStore((state) => state.activeGameId);

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

  // Always render as a fixed compact bottom bar on all pages
  return (
    <div
      className="fixed z-50 transition-all duration-300 bottom-0 left-0 right-0 md:bottom-4 md:left-auto md:right-4 md:w-80"
    >
      <MusicPlayer
        storyText={storyText}
        gameId={effectiveGameId}
        className="rounded-none md:rounded-lg"
      />
    </div>
  );
}
