"use client";

import { useGameStore } from "@/stores/useGameStore";
import type { EventOption } from "@/lib/types";

// ==================== Retry Tracking ====================

/**
 * 模块级变量：跟踪是否发生了重试
 * 当收到 retry 状态时设为 true，complete 时检查并重置
 */
let hadRetry = false;

/**
 * 标记发生了重试（由 handleStatusUpdate 调用）
 */
export function markRetry(): void {
  hadRetry = true;
  console.log("[eventUtils] Retry marked, will force use backend story on complete");
}

/**
 * 检查并清除重试标记
 * 返回 true 表示刚才发生了重试
 */
export function checkAndClearRetry(): boolean {
  const result = hadRetry;
  if (result) {
    console.log("[eventUtils] Retry detected, clearing flag");
  }
  hadRetry = false;
  return result;
}

// ==================== Types ====================

export interface EventData {
  event_description?: string;
  story?: string;
  options?: EventOption[];
  game_over?: boolean;
}

export interface EventHandlers {
  setStoryText: (text: string) => void;
  setOptions: (options: EventOption[]) => void;
  setCurrentEvent: (event: { story: string; options: EventOption[] } | null) => void;
  setPhase: (phase: string) => void;
  setGameOver: (gameOver: boolean) => void;
  setRoundSummary: (summary: string | null) => void;
  setProcessing: (processing: boolean, message?: string) => void;
  setConnectionStatus: (status: string | null) => void;
  appendStoryText: (text: string) => void;
  generatingRef: React.MutableRefObject<boolean>;
  isRetryingRef?: React.MutableRefObject<boolean>;
}

function enterRetryableCompleteError(
  handlers: Pick<EventHandlers, "setConnectionStatus" | "setPhase" | "setRoundSummary" | "isRetryingRef">
): void {
  handlers.setConnectionStatus("error");
  handlers.setPhase("error");
  handlers.setRoundSummary(null);
  if (handlers.isRetryingRef) {
    handlers.isRetryingRef.current = false;
  }
}

// ==================== Story Helpers ====================

/**
 * 选择最终要使用的故事文本
 */
export function selectFinalStory(
  backendStory: string,
  frontendStory: string
): { useBackend: boolean; finalStory: string; remainingText?: string } {
  // 如果前端故事为空或极短，才使用后端故事
  // 避免流式生成过程中被后端文本覆盖
  const useBackendStory = frontendStory.length < 10;
  
  if (useBackendStory && backendStory.length > 0) {
    return { useBackend: true, finalStory: backendStory };
  }
  
  // 如果后端故事比前端长，且前端文本是后端文本前缀，则流式补充剩余部分。
  // 若两者已经分叉，继续 slice 会把无关后端片段拼到前端故事后面。
  if (backendStory.length > frontendStory.length && backendStory.startsWith(frontendStory)) {
    return {
      useBackend: false,
      finalStory: frontendStory,
      remainingText: backendStory.slice(frontendStory.length),
    };
  }

  if (backendStory.length > frontendStory.length && frontendStory.length <= 100) {
    return { useBackend: true, finalStory: backendStory };
  }
  
  // 使用前端故事
  return { useBackend: false, finalStory: frontendStory };
}

/**
 * 流式追加文本
 */
export function streamRemainingText(
  text: string,
  appendStoryText: (text: string) => void,
  onComplete: () => void,
  chunkSize = 3,
  interval = 20
): void {
  let charIndex = 0;
  
  const stream = () => {
    if (charIndex < text.length) {
      const chunk = text.slice(charIndex, charIndex + chunkSize);
      appendStoryText(chunk);
      charIndex += chunkSize;
      setTimeout(stream, interval);
    } else {
      onComplete();
    }
  };
  
  stream();
}

// ==================== Event Completion ====================

/**
 * 处理事件生成完成
 */
export function handleEventComplete(
  data: Record<string, unknown>,
  handlers: EventHandlers
): void {
  const {
    setStoryText,
    setOptions,
    setCurrentEvent,
    setPhase,
    setGameOver,
    setRoundSummary,
    setProcessing,
    setConnectionStatus,
    appendStoryText,
    generatingRef,
  } = handlers;

  setProcessing(false);
  setConnectionStatus(null);
  generatingRef.current = false;

  const eventData = data as EventData;
  console.log("[onComplete] Options:", eventData.options?.length ?? "undefined");

  // 游戏结束
  if (eventData.game_over) {
    setPhase("ending");
    setGameOver(true);
    return;
  }

  const receivedOptions = eventData.options || [];
  if (receivedOptions.length === 0) {
    console.error("[onComplete] No options in complete event");
    enterRetryableCompleteError(handlers);
    return;
  }

  const backendStory = eventData.event_description || eventData.story || "";
  const frontendStory = useGameStore.getState().storyText;
  if (!backendStory.trim() && !frontendStory.trim()) {
    console.error("[onComplete] No story text in complete event");
    enterRetryableCompleteError(handlers);
    return;
  }
  
  // ★ 检查是否发生了重试，如果重试后强制使用后端故事
  // 但如果后端返回的是 fallback 故事（很短），且前端有更长的流式故事，仍优先用前端的
  const wasRetry = checkAndClearRetry();
  if (wasRetry && backendStory) {
    // ★ 如果前端有更长的流式故事（来自重试生成），且后端故事明显是 fallback（< 50字）
    // 说明重试后的故事已流式传输到前端，但后续步骤失败返回了 fallback
    if (frontendStory.length > 100 && backendStory.length < 50) {
      console.log(`[onComplete] Retry detected but backend story is fallback (${backendStory.length} chars), using frontend story (${frontendStory.length} chars)`);
      setStoryText(frontendStory);
      setOptions(receivedOptions);
      setCurrentEvent({ story: frontendStory, options: receivedOptions });
      setPhase("options");
      setRoundSummary(null);
      return;
    }
    console.log(`[onComplete] Retry detected, forcing backend story (${backendStory.length} chars)`);
    setStoryText(backendStory);
    setOptions(receivedOptions);
    setCurrentEvent({ story: backendStory, options: receivedOptions });
    setPhase("options");
    setRoundSummary(null);
    return;
  }

  if (backendStory.trim()) {
    console.log(`[onComplete] Replacing streamed story with backend complete story (${backendStory.length} chars)`);
    setStoryText(backendStory);
    setOptions(receivedOptions);
    setCurrentEvent({ story: backendStory, options: receivedOptions });
    setPhase("options");
    setRoundSummary(null);
    return;
  }
  
  const result = selectFinalStory(backendStory, frontendStory);

  if (result.useBackend) {
    // 直接使用后端故事
    console.log(`[onComplete] Using backend story (${backendStory.length} chars)`);
    setStoryText(result.finalStory);
    setOptions(receivedOptions);
    setCurrentEvent({ story: result.finalStory, options: receivedOptions });
    setPhase("options");
    setRoundSummary(null);
    return;
  }

  if (result.remainingText) {
    // 流式补充剩余文本
    setOptions(receivedOptions);
    // 保持 generating 阶段以维持流式显示效果
    streamRemainingText(result.remainingText, appendStoryText, () => {
      setCurrentEvent({ story: backendStory, options: receivedOptions });
      setPhase("options");
    });
    return;
  }

  // 使用前端故事，检查是否需要更新
  const currentOptions = useGameStore.getState().currentEvent?.options || [];
  const optionsChanged = JSON.stringify(receivedOptions) !== JSON.stringify(currentOptions);
  const currentStory = useGameStore.getState().storyText;
  const storyChanged = result.finalStory !== currentStory;

  if (optionsChanged) setOptions(receivedOptions);
  if (storyChanged) setStoryText(result.finalStory);
  if (optionsChanged || storyChanged) {
    setCurrentEvent({ story: result.finalStory, options: receivedOptions });
  }
  // 延迟切换到 options 阶段，让用户看到完整故事后再选择
  setTimeout(() => {
    setPhase("options");
  }, 500);
  setRoundSummary(null);
  
  // ★ 事件插画由后端 SSE 完成后自动触发（_trigger_round_illustration_generation）
  // 前端不再重复触发，避免生成两张相同场景插画
  // 页面刷新后的备用生成由 usePlayGame 的 auto-generate effect 处理
}

// ==================== Status Helpers ====================

/**
 * 处理状态更新
 */
export function handleStatusUpdate(
  status: { phase: string },
  setProcessing: (processing: boolean, message?: string) => void,
  isRetryingRef?: React.MutableRefObject<boolean>
): void {
  if (status.phase === "retrying") {
    console.log("[onStatus] Retrying detected, story will be regenerated");
    if (isRetryingRef) isRetryingRef.current = true;
    setProcessing(true, "retrying");
    return;
  }
  if (status.phase === "retry") {
    console.log("[onStatus] Retry event received, clearing story for new content");
    // ★ 标记发生了重试，complete 时会强制使用后端故事
    markRetry();
    if (isRetryingRef) isRetryingRef.current = true;
    useGameStore.getState().setStoryText?.("");
    useGameStore.setState?.({ storyText: "" });
    setProcessing(true, "retrying");
    return;
  }
  setProcessing(true, status.phase);
}
