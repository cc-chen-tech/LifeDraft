"use client";

import { useState, useCallback } from "react";
import type { EventOption } from "@/lib/types";
import type { Phase } from "./usePhaseManager";

interface RoundHistoryItem {
  week: number;
  round: number;
  summary?: string;
  event_description?: string;
  story_continuation?: string;
  choice?: string;
  effects?: Record<string, unknown>;
  date_info?: { date_string?: string; year?: number; month?: number };
}

interface UseHistoryViewerParams {
  playerState: Record<string, unknown> | null;
  storyText: string;
  currentEvent: { story: string; options: EventOption[] } | null;
  phaseRef: React.MutableRefObject<Phase>;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  setOptions: (options: EventOption[]) => void;
  generatingRef: React.MutableRefObject<boolean>;
}

/**
 * Hook for managing history viewing functionality.
 * Allows players to review past rounds without affecting current game state.
 * 
 * ★ 支持在生成中查看历史：
 * - 使用独立的 historyDisplayText 存储历史内容
 * - SSE 回调继续更新 storyText
 * - 用户返回时显示最新的 storyText
 */
export function useHistoryViewer({
  playerState,
  storyText,
  currentEvent,
  phaseRef,
  setPhase,
  setOptions,
  generatingRef,
}: UseHistoryViewerParams) {
  // History state
  const [showHistory, setShowHistory] = useState(false);
  const [historyRoundIndex, setHistoryRoundIndex] = useState<number | null>(null);
  const [historyPhaseBackup, setHistoryPhaseBackup] = useState<Phase | null>(null);
  // ★ 独立的历史显示文本，不受 SSE 回调影响
  const [historyDisplayText, setHistoryDisplayText] = useState<string | null>(null);

  // Get round history from player state
  const roundHistory = (playerState?.round_history || []) as RoundHistoryItem[];

  // Whether viewing history (not current round)
  const isViewingHistory = historyRoundIndex !== null;
  
  // ★ 实际显示的文本：历史模式下显示历史文本，否则显示当前文本
  const displayText = isViewingHistory ? (historyDisplayText || '') : storyText;

  // Open history drawer
  const handleOpenHistory = useCallback(() => {
    setShowHistory(true);
  }, []);

  // Select a history round to view
  const handleSelectHistoryRound = useCallback((index: number) => {
    const round = roundHistory[index];
    if (!round) return;

    // ★ 备份当前 phase（仅首次进入时）
    if (historyRoundIndex === null) {
      setHistoryPhaseBackup(phaseRef.current);
    }

    // Build full story text
    const eventDesc = round.event_description || '';
    const continuation = round.story_continuation || '';
    const fullStory = eventDesc + (continuation ? '\n\n--- 选择后的故事发展 ---\n\n' + continuation : '');

    setHistoryRoundIndex(index);
    setHistoryDisplayText(fullStory || '(此轮次暂无故事内容)');
    setOptions([]);  // No options in history mode
    // ★ 不再改变 phase，让 SSE 继续正常工作

    console.log(`[history] Viewing round ${index}: week=${round.week}, round=${round.round}`);
  }, [roundHistory, historyRoundIndex, phaseRef, setOptions]);

  // Return to current round
  const handleBackToCurrent = useCallback(() => {
    // ★ 恢复备份的 phase
    if (historyPhaseBackup) {
      setPhase(historyPhaseBackup);
    }

    // Clear history state
    setHistoryRoundIndex(null);
    setHistoryDisplayText(null);
    setHistoryPhaseBackup(null);

    // ★ 恢复当前事件的选项（如果已完成生成）
    if (currentEvent?.options?.length) {
      setOptions(currentEvent.options);
    }

    console.log('[history] Returned to current round, current story length:', storyText.length);
  }, [historyPhaseBackup, setPhase, currentEvent, setOptions, storyText.length]);

  return {
    // State
    showHistory,
    setShowHistory,
    roundHistory,
    historyRoundIndex,
    isViewingHistory,
    historyDisplayText,  // ★ 暴露给外部使用
    displayText,  // ★ 实际显示的文本
    // Handlers
    handleOpenHistory,
    handleSelectHistoryRound,
    handleBackToCurrent,
  };
}
