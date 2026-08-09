"use client";

// Re-export types
export type { Phase, ConnectionStatus } from "./usePhaseManager";

// Re-export hooks
export { usePhaseManager } from "./usePhaseManager";
export { useEventGenerator } from "./useEventGenerator";
export { useChoiceHandler } from "./useChoiceHandler";
export { useGameState } from "./useGameState";
export { useHistoryViewer } from "./useHistoryViewer";

// Re-export choice utilities
export {
  parseSSEError,
  handleChoiceComplete,
  handleChoiceError,
  recoverStoryFromRoundHistory,
  enterResultPhase,
  type ChoiceHandlers,
  type ChoiceErrorContext,
} from "./choiceUtils";

// Re-export event utilities
export {
  handleEventComplete,
  handleStatusUpdate,
  selectFinalStory,
  streamRemainingText,
  type EventData,
  type EventHandlers,
} from "./eventUtils";
