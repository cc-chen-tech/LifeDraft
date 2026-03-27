/**
 * Stores 统一导出
 *
 * 提供向后兼容的导入方式
 *
 * useGameStore 现在是一个组合 store，委托给各专门的子 store：
 * - useSessionStore: 会话状态（gameId, sessionId, playerState, progress, roundInfo）
 * - useEventStore: 事件和故事状态
 * - useImageStore: 玩家形象和开场插画
 * - useCharacterStore: 角色创建状态
 * - useGameListStore: 存档和预设列表
 * - useSceneImageStore: 场景插画状态
 */

// 主 store（向后兼容的组合 store）
export { useGameStore } from "./useGameStore";

// Session store（会话管理）
export { useSessionStore, type SessionState } from "./useSessionStore";

// Event store（事件和故事）
export { useEventStore } from "./useEventStore";

// Image stores
export { useImageStore, type RoundSceneImage } from "./useImageStore";
export { useSceneImageStore } from "./useSceneImageStore";

// Character store（角色创建）
export {
  useCharacterStore,
  CREATION_STEPS,
  MANUAL_STEPS,
  AUTO_ADVANCE_STEPS,
  type CreationStep
} from "./useCharacterStore";

// Game list store（存档和预设）
export { useGameListStore } from "./useGameListStore";

// Collection store
export { useCollectionStore } from "./useCollectionStore";

// UI store
export { useUIStore } from "./useUIStore";

// User store
export { useUserStore } from "./useUserStore";
