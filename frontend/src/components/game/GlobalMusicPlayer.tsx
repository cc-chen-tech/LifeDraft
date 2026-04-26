"use client";

/**
 * GlobalMusicPlayer — application-level music player wrapper.
 *
 * Mounted in RootLayout so it survives page navigation.
 * Reads the active gameId from localStorage and loads the persisted playlist.
 */
import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { MusicPlayer } from "./MusicPlayer";
import { useMusicStore } from "@/stores/useMusicStore";

export function GlobalMusicPlayer() {
  const pathname = usePathname();
  const hasInitRef = useRef(false);

  const loadPlaylist = useMusicStore((state) => state.loadPlaylist);
  const playlistGameId = useMusicStore((state) => state.playlistGameId);
  const currentSong = useMusicStore((state) => state.currentSong);
  const queue = useMusicStore((state) => state.queue);
  const recommendation = useMusicStore((state) => state.recommendation);

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

  // Build a synthetic storyText for MusicPlayer so it renders.
  // When playlist is loaded from DB, we don't need fresh recommendation.
  // The MusicPlayer component uses storyText to trigger fetchRecommendation.
  // We pass a non-empty placeholder to ensure the player UI renders,
  // but we suppress automatic recommendation fetching when a playlist exists.
  const syntheticStoryText =
    recommendation || currentSong || queue.length > 0 ? "persisted" : "";

  // Only render if we have any music state (prevents empty player on non-game pages)
  if (!syntheticStoryText) return null;

  // Collapse into a compact bottom bar when not on /play
  const isCompact = pathname !== "/play";

  return (
    <div
      className={`fixed z-50 transition-all duration-300 ${
        isCompact
          ? "bottom-0 left-0 right-0 md:bottom-4 md:left-auto md:right-4 md:w-80"
          : "bottom-0 left-0 right-0 md:static md:w-full"
      }`}
    >
      <MusicPlayer
        storyText={syntheticStoryText}
        gameId={playlistGameId ?? undefined}
        className={isCompact ? "rounded-none md:rounded-lg" : ""}
      />
    </div>
  );
}
