"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useUIStore } from "@/stores/useUIStore";

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

// Status code to Chinese message mapping
export const STATUS_MESSAGES: Record<string, string> = {
  preparing: "正在准备...",
  initializing: "正在初始化...",
  loading_context: "正在加载上下文...",
  building_world: "正在构建世界...",
  generating_story: "正在生成故事...",
  generating_options: "正在生成选项...",
  compressing: "正在整理剧情...",
  weekly_summary: "正在生成周总结...",
  processing: "正在处理中...",
  connecting: "正在连接服务器...",
  fallback: "正在使用备用模式...",
  replaying: "正在恢复进度...",
  waiting: "等待服务器响应...",
  retrying: "故事逻辑校验中，正在优化...",
};

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "error" | null;

/**
 * Hook for managing game phase state.
 * Handles phase transitions, loading messages, and connection status.
 */
export function usePhaseManager() {
  const { setProcessing, processingMessage } = useUIStore();

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

  // Timer for elapsed time display
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (phase === "generating" || phase === "choosing") {
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setElapsedSeconds(0);
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [phase]);

  // Get loading message based on current state
  const getLoadingMessage = useCallback(() => {
    if (connectionStatus === "reconnecting") {
      if (phase === "generating") {
        return "故事正在生成，请稍候...";
      }
      if (phase === "choosing") {
        return "结果正在生成，请稍候...";
      }
      return "正在连接服务器...";
    }
    if (connectionStatus === "connecting") {
      return STATUS_MESSAGES.connecting;
    }
    if (phase === "generating") {
      return STATUS_MESSAGES[processingMessage] || "正在构思剧情...";
    } else if (phase === "choosing") {
      return STATUS_MESSAGES[processingMessage] || "正在推演结果...";
    }
    return "正在加载...";
  }, [phase, processingMessage, connectionStatus]);

  return {
    phase,
    setPhase,
    phaseRef,
    connectionStatus,
    setConnectionStatus,
    reconnectAttempt,
    setReconnectAttempt,
    elapsedSeconds,
    getLoadingMessage,
    setProcessing,
  };
}
