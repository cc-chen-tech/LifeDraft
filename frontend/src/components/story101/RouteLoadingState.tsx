"use client";

import { NarrativeLoadingState } from "@/components/narrative-loading/NarrativeLoadingState";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";

export function RouteLoadingState() {
  const isNarrativeLoadingVisible = useDelayedLoading({
    isLoading: true,
    delay: 250,
    loadingIdentity: "route-loading",
  });

  return (
    <div className="min-h-[100dvh] bg-[var(--surface-canvas)]" data-slot="route-loading-state">
      {isNarrativeLoadingVisible && <NarrativeLoadingState context="hydrate" layout="screen" />}
    </div>
  );
}
