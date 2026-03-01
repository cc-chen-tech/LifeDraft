/**
 * Stores 统一导出
 * 
 * 提供向后兼容的导入方式
 */

// 主 store（向后兼容）
export { useGameStore } from "./useGameStore";

// 子 stores（细粒度使用）
export { useEventStore } from "./useEventStore";
export { useImageStore, type RoundSceneImage } from "./useImageStore";
export { 
  useCharacterStore, 
  CREATION_STEPS, 
  MANUAL_STEPS, 
  AUTO_ADVANCE_STEPS, 
  type CreationStep 
} from "./useCharacterStore";
export { useGameListStore } from "./useGameListStore";

// UI store
export { useUIStore } from "./useUIStore";

// User store
export { useUserStore } from "./useUserStore";
