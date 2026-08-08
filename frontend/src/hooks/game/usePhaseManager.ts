"use client";

import { useState, useCallback, useRef } from "react";
import { useUIStore } from "@/stores/useUIStore";
import type { NarrativeTransportState } from "@/components/narrative-loading/NarrativeLoadingState";

// Phase types for the play page
export type Phase =
  | "loading"       // Initial loading
  | "generating"    // Generating event via SSE
  | "options"       // Showing options
  | "choosing"      // Processing choice via SSE
  | "result"        // Showing round result, waiting for confirmation
  | "summary"       // Showing weekly summary
  | "ending"        // Game over
  | "error";

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "error" | null;

/**
 * Hook for managing game phase state.
 * Handles phase transitions, loading messages, and connection status.
 */
export function usePhaseManager() {
  const { setProcessing } = useUIStore();

  // Phase state with ref for avoiding closure issues
  const [phase, setPhaseState] = useState<Phase>("loading");
  const phaseRef = useRef<Phase>("loading");

  const setPhase = useCallback((newPhase: Phase | ((prev: Phase) => Phase)) => {
    setPhaseState((prev) => {
      const nextPhase = typeof newPhase === "function" ? newPhase(prev) : newPhase;
      phaseRef.current = nextPhase;
      if (prev !== nextPhase) {
        console.log(`[PHASE] ${prev} → ${nextPhase}`, new Error().stack?.split('\n')[2]?.trim());
      }
      return nextPhase;
    });
  }, []);

  // Connection status for SSE
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState<{ current: number; max: number } | null>(null);
  const [transport, setTransport] = useState<NarrativeTransportState>("active");

  return {
    phase,
    setPhase,
    phaseRef,
    connectionStatus,
    setConnectionStatus,
    reconnectAttempt,
    setReconnectAttempt,
    transport,
    setTransport,
    setProcessing,
  };
}
