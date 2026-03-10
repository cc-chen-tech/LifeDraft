"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useGameStore } from "@/stores/useGameStore";

/**
 * 从 URL 参数同步 gameId 到 store
 * 必须在 Suspense boundary 内使用
 */
export function useGameIdFromUrl() {
  const searchParams = useSearchParams();
  const urlGameId = searchParams.get("gameId");
  const setGameId = useGameStore((s) => s.setGameId);
  const storeGameId = useGameStore((s) => s.gameId);

  useEffect(() => {
    if (urlGameId) {
      const parsedId = parseInt(urlGameId, 10);
      if (!isNaN(parsedId) && parsedId !== storeGameId) {
        console.log(`[useGameIdFromUrl] URL gameId=${parsedId} takes priority over localStorage gameId=${storeGameId}`);
        setGameId(parsedId);
      }
    }
  }, [urlGameId, storeGameId, setGameId]);

  return { urlGameId: urlGameId ? parseInt(urlGameId, 10) : null };
}
