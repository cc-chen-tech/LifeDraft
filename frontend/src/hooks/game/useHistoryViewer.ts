"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { EventOption } from "@/lib/types";
import type { Phase } from "./usePhaseManager";
import type { SceneImageInfo } from "@/components/game/RoundHistoryDrawer";

interface RoundHistoryItem {
  week: number;
  round: number;
  summary?: string;
  event_description?: string;
  story_continuation?: string;
  choice?: string;
  effects?: Record<string, unknown>;
  date_info?: { date_string?: string; year?: number; month?: number };
  scene_image?: SceneImageInfo | null;
}

interface UseHistoryViewerParams {
  playerState: Record<string, unknown> | null;
  storyText: string;
  currentEvent: { story: string; options: EventOption[] } | null;
  phaseRef: React.MutableRefObject<Phase>;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  setOptions: (options: EventOption[]) => void;
  generatingRef: React.MutableRefObject<boolean>;
  gameId: number | null;
  fetchHistorySceneImage?: (week: number, round: number) => Promise<void>;
  generateHistorySceneImage?: (week: number, round: number, storyText: string) => Promise<void>;
  regenerateHistorySceneImage?: (week: number, round: number, storyText: string, userPrompt: string, sceneId: number) => Promise<void>;
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
  gameId,
  fetchHistorySceneImage,
  generateHistorySceneImage,
  regenerateHistorySceneImage,
}: UseHistoryViewerParams) {
  // History state
  const [showHistory, setShowHistory] = useState(false);
  const [historyRoundIndex, setHistoryRoundIndex] = useState<number | null>(null);
  const [historyPhaseBackup, setHistoryPhaseBackup] = useState<Phase | null>(null);
  // ★ 独立的历史显示文本，不受 SSE 回调影响
  const [historyDisplayText, setHistoryDisplayText] = useState<string | null>(null);
  // ★ 历史场景图片状态
  const [historySceneImage, setHistorySceneImage] = useState<SceneImageInfo | null>(null);
  const [isLoadingHistoryImage, setIsLoadingHistoryImage] = useState(false);
  const [isGeneratingHistoryImage, setIsGeneratingHistoryImage] = useState(false);
  const [isRegeneratingHistoryImage, setIsRegeneratingHistoryImage] = useState(false);

  // Get round history from player state
  const roundHistory = (playerState?.round_history || []) as RoundHistoryItem[];

  // Whether viewing history (not current round)
  const isViewingHistory = historyRoundIndex !== null;

  // ★ 实际显示的文本：历史模式下显示历史文本，否则显示当前文本
  const displayText = isViewingHistory ? (historyDisplayText || '') : storyText;

  // ★ 当历史抽屉被关闭（点击外部或按 Escape）时，自动返回当前轮次
  // 避免 isViewingHistory 一直为 true，导致底部操作栏按钮被禁用
  const prevShowHistoryRef = useRef(showHistory);
  useEffect(() => {
    const wasOpen = prevShowHistoryRef.current;
    prevShowHistoryRef.current = showHistory;
    if (wasOpen && !showHistory && historyRoundIndex !== null) {
      // 恢复备份的 phase
      if (historyPhaseBackup) {
        setPhase(historyPhaseBackup);
      }
      // 清除历史状态
      setHistoryRoundIndex(null);
      setHistoryDisplayText(null);
      setHistoryPhaseBackup(null);
      // 清除历史图片状态
      setHistorySceneImage(null);
      setIsLoadingHistoryImage(false);
      setIsGeneratingHistoryImage(false);
      setIsRegeneratingHistoryImage(false);
      // 恢复当前事件的选项
      if (currentEvent?.options?.length) {
        setOptions(currentEvent.options);
      }
    }
  }, [showHistory, historyRoundIndex, historyPhaseBackup, setPhase, currentEvent, setOptions]);

  // Open history drawer
  const handleOpenHistory = useCallback(() => {
    setShowHistory(true);
  }, []);

  // Select a history round to view
  const handleSelectHistoryRound = useCallback(async (index: number) => {
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

    // ★ 加载历史场景图片
    setIsLoadingHistoryImage(true);
    setHistorySceneImage(null);
    
    try {
      // 优先使用 round 中已有的 scene_image
      if (round.scene_image) {
        setHistorySceneImage(round.scene_image);
      } else if (fetchHistorySceneImage && gameId) {
        // 从 API 获取
        await fetchHistorySceneImage(round.week, round.round);
      }
    } catch (err) {
      console.error('[history] Failed to load scene image:', err);
    } finally {
      setIsLoadingHistoryImage(false);
    }

    console.log(`[history] Viewing round ${index}: week=${round.week}, round=${round.round}`);
  }, [roundHistory, historyRoundIndex, phaseRef, setOptions, fetchHistorySceneImage, gameId]);

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
    // ★ 清除历史图片状态
    setHistorySceneImage(null);
    setIsLoadingHistoryImage(false);
    setIsGeneratingHistoryImage(false);
    setIsRegeneratingHistoryImage(false);

    // ★ 恢复当前事件的选项（如果已完成生成）
    if (currentEvent?.options?.length) {
      setOptions(currentEvent.options);
    }

    console.log('[history] Returned to current round, current story length:', storyText.length);
  }, [historyPhaseBackup, setPhase, currentEvent, setOptions, storyText.length]);

  // ★ 为历史轮次生成场景图片
  const handleGenerateHistoryImage = useCallback(async (week: number, round: number, text: string) => {
    if (!generateHistorySceneImage) return;
    
    setIsGeneratingHistoryImage(true);
    try {
      await generateHistorySceneImage(week, round, text);
      // 生成成功后重新获取图片
      if (fetchHistorySceneImage) {
        await fetchHistorySceneImage(week, round);
      }
    } catch (err) {
      console.error('[history] Failed to generate scene image:', err);
    } finally {
      setIsGeneratingHistoryImage(false);
    }
  }, [generateHistorySceneImage, fetchHistorySceneImage]);

  // ★ 重新生成历史轮次场景图片
  const handleRegenerateHistoryImage = useCallback(async (
    week: number, 
    round: number, 
    text: string, 
    userPrompt: string, 
    sceneId: number
  ) => {
    if (!regenerateHistorySceneImage) return;
    
    setIsRegeneratingHistoryImage(true);
    try {
      await regenerateHistorySceneImage(week, round, text, userPrompt, sceneId);
      // 重新生成成功后重新获取图片
      if (fetchHistorySceneImage) {
        await fetchHistorySceneImage(week, round);
      }
    } catch (err) {
      console.error('[history] Failed to regenerate scene image:', err);
    } finally {
      setIsRegeneratingHistoryImage(false);
    }
  }, [regenerateHistorySceneImage, fetchHistorySceneImage]);

  // 获取当前历史轮次的信息
  const currentHistoryRound = historyRoundIndex !== null ? roundHistory[historyRoundIndex] : null;

  return {
    // State
    showHistory,
    setShowHistory,
    roundHistory,
    historyRoundIndex,
    isViewingHistory,
    historyDisplayText,  // ★ 暴露给外部使用
    displayText,  // ★ 实际显示的文本
    // ★ 历史场景图片状态
    historySceneImage,
    isLoadingHistoryImage,
    isGeneratingHistoryImage,
    isRegeneratingHistoryImage,
    currentHistoryRound,
    // Handlers
    handleOpenHistory,
    handleSelectHistoryRound,
    handleBackToCurrent,
    handleGenerateHistoryImage,
    handleRegenerateHistoryImage,
  };
}
