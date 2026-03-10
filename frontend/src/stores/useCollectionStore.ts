/**
 * useCollectionStore — 收集系统状态
 *
 * 管理人物、物品和标志物收集数据
 */
import { create } from "zustand";
import type { CharacterCollectionItem, ItemCollectionItem, LandmarkCollectionItem, CollectionResponse } from "@/lib/types";
import api from "@/lib/api";

interface CollectionState {
  // 数据
  characters: CharacterCollectionItem[];
  items: ItemCollectionItem[];
  landmarks: LandmarkCollectionItem[];

  // UI状态
  isLoading: boolean;  // 初始加载
  isRefreshing: boolean;  // 刷新数据（不隐藏已有内容）
  activeTab: "characters" | "items" | "landmarks";
  selectedCharacter: CharacterCollectionItem | null;
  selectedItem: ItemCollectionItem | null;
  selectedLandmark: LandmarkCollectionItem | null;

  // 生成状态
  generatingImageFor: string | null;  // 正在生成图片的名称
  generatingDescriptionFor: string | null;  // 正在生成描述的名称
  regeneratingImageFor: string | null;  // 正在重新生成图片的名称

  // 错误
  error: string | null;

  // Actions
  fetchCollection: (gameId: number, isRefresh?: boolean) => Promise<void>;
  setActiveTab: (tab: "characters" | "items" | "landmarks") => void;
  selectCharacter: (character: CharacterCollectionItem | null) => void;
  selectItem: (item: ItemCollectionItem | null) => void;
  selectLandmark: (landmark: LandmarkCollectionItem | null) => void;
  generateCharacterImage: (gameId: number, name: string) => Promise<void>;
  generateItemImage: (gameId: number, itemName: string) => Promise<void>;
  generateLandmarkImage: (gameId: number, landmarkName: string) => Promise<void>;
  generateCharacterDescription: (gameId: number, name: string) => Promise<void>;
  generateItemDescription: (gameId: number, itemName: string) => Promise<void>;
  generateLandmarkDescription: (gameId: number, landmarkName: string) => Promise<void>;
  regenerateCharacterImage: (gameId: number, name: string, feedback: string, imageId?: number) => Promise<void>;
  regenerateItemImage: (gameId: number, itemName: string, feedback: string) => Promise<void>;
  clearSelection: () => void;
  clearError: () => void;
}

export const useCollectionStore = create<CollectionState>((set, get) => ({
  // 初始数据
  characters: [],
  items: [],
  landmarks: [],

  // 初始UI状态
  isLoading: false,
  isRefreshing: false,
  activeTab: "characters",
  selectedCharacter: null,
  selectedItem: null,
  selectedLandmark: null,

  // 初始生成状态
  generatingImageFor: null,
  generatingDescriptionFor: null,
  regeneratingImageFor: null,

  // 初始错误
  error: null,

  // 获取收集数据
  fetchCollection: async (gameId: number, isRefresh: boolean = false) => {
    if (!gameId) {
      set({ error: "游戏ID不存在" });
      return;
    }

    // 保存当前选中的人物/物品/标志物名称，以便刷新后恢复选中状态
    const currentSelected = get();
    const selectedCharacterName = currentSelected.selectedCharacter?.name;
    const selectedItemName = currentSelected.selectedItem?.name;
    const selectedLandmarkName = currentSelected.selectedLandmark?.name;

    // 区分初始加载和刷新：初始加载显示加载状态，刷新不隐藏已有内容
    // 刷新时完全保留现有数据，只更新数据不改变UI状态
    if (isRefresh) {
      // 刷新模式：不改变 isLoading，不隐藏已有内容
      console.log("[fetchCollection] 刷新模式 - 保持列表可见");
    } else {
      // 初始加载模式：显示加载状态
      console.log("[fetchCollection] 初始加载模式 - 显示加载中");
      set({ isLoading: true, error: null });
    }

    try {
      const result: CollectionResponse = await api.collection.get(gameId);

      const newCharacters = result.characters || [];
      const newItems = result.items || [];
      const newLandmarks = result.landmarks || [];

      // 恢复选中状态（从新数据中找到对应的人物/物品/标志物）
      const newSelectedCharacter = selectedCharacterName
        ? newCharacters.find(c => c.name === selectedCharacterName) || null
        : null;
      const newSelectedItem = selectedItemName
        ? newItems.find(i => i.name === selectedItemName) || null
        : null;
      const newSelectedLandmark = selectedLandmarkName
        ? newLandmarks.find(l => l.name === selectedLandmarkName) || null
        : null;

      console.log("[fetchCollection] 数据更新完成:", {
        charactersCount: newCharacters.length,
        itemsCount: newItems.length,
        landmarksCount: newLandmarks.length,
        isRefresh,
      });

      // ★ 修复：刷新模式下合并数据，保留已有图片URL，避免闪烁
      if (isRefresh) {
        const currentCharacters = get().characters;
        const mergedCharacters = newCharacters.map(newChar => {
          const oldChar = currentCharacters.find(c => c.name === newChar.name);
          // 如果新数据没有图片URL但旧数据有，保留旧URL（避免生成过程中的闪烁）
          if (!newChar.image_url && oldChar?.image_url) {
            return { ...newChar, image_url: oldChar.image_url, image_generated: oldChar.image_generated };
          }
          return newChar;
        });

        set({
          characters: mergedCharacters,
          items: newItems,
          landmarks: newLandmarks,
          selectedCharacter: newSelectedCharacter,
          selectedItem: newSelectedItem,
          selectedLandmark: newSelectedLandmark,
          isLoading: false,
          isRefreshing: false,
        });
      } else {
        set({
          characters: newCharacters,
          items: newItems,
          landmarks: newLandmarks,
          selectedCharacter: newSelectedCharacter,
          selectedItem: newSelectedItem,
          selectedLandmark: newSelectedLandmark,
          isLoading: false,
          isRefreshing: false,
        });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "获取收集数据失败";
      console.error("[fetchCollection] 错误:", errorMsg);
      set({ error: errorMsg, isLoading: false, isRefreshing: false });
    }
  },

  // 设置活动标签
  setActiveTab: (tab) => set({ activeTab: tab }),

  // 选择人物
  selectCharacter: (character) => set({ selectedCharacter: character, selectedItem: null, selectedLandmark: null }),

  // 选择物品
  selectItem: (item) => set({ selectedItem: item, selectedCharacter: null, selectedLandmark: null }),

  // 选择标志物
  selectLandmark: (landmark) => set({ selectedLandmark: landmark, selectedCharacter: null, selectedItem: null }),

  // 生成人物图片
  generateCharacterImage: async (gameId: number, name: string) => {
    if (!gameId || !name) return;

    set({ generatingImageFor: name, error: null });

    try {
      await api.collection.generateCharacterImage(gameId, name);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ generatingImageFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "生成人物图片失败";
      set({ error: errorMsg, generatingImageFor: null });
    }
  },

  // 生成物品图片
  generateItemImage: async (gameId: number, itemName: string) => {
    if (!gameId || !itemName) return;

    set({ generatingImageFor: itemName, error: null });

    try {
      await api.collection.generateItemImage(gameId, itemName);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ generatingImageFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "生成物品图片失败";
      set({ error: errorMsg, generatingImageFor: null });
    }
  },

  // 生成人物描述
  generateCharacterDescription: async (gameId: number, name: string) => {
    if (!gameId || !name) return;

    set({ generatingDescriptionFor: name, error: null });

    try {
      await api.collection.generateCharacterDescription(gameId, name);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ generatingDescriptionFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "生成人物描述失败";
      set({ error: errorMsg, generatingDescriptionFor: null });
    }
  },

  // 生成物品描述
  generateItemDescription: async (gameId: number, itemName: string) => {
    if (!gameId || !itemName) return;

    set({ generatingDescriptionFor: itemName, error: null });

    try {
      await api.collection.generateItemDescription(gameId, itemName);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ generatingDescriptionFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "生成物品描述失败";
      set({ error: errorMsg, generatingDescriptionFor: null });
    }
  },

  // 重新生成人物画像
  regenerateCharacterImage: async (gameId: number, name: string, feedback: string, imageId?: number) => {
    if (!gameId || !name || !feedback) return;

    set({ regeneratingImageFor: name, error: null });

    try {
      await api.collection.regenerateCharacterImage(gameId, name, feedback, imageId);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ regeneratingImageFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "修改人物画像失败";
      set({ error: errorMsg, regeneratingImageFor: null });
    }
  },

  // 重新生成物品图片
  regenerateItemImage: async (gameId: number, itemName: string, feedback: string) => {
    if (!gameId || !itemName || !feedback) return;

    set({ regeneratingImageFor: itemName, error: null });

    try {
      await api.collection.regenerateItemImage(gameId, itemName, feedback);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ regeneratingImageFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "修改物品图片失败";
      set({ error: errorMsg, regeneratingImageFor: null });
    }
  },

  // 生成标志物图片
  generateLandmarkImage: async (gameId: number, landmarkName: string) => {
    if (!gameId || !landmarkName) return;

    set({ generatingImageFor: landmarkName, error: null });

    try {
      await api.collection.generateLandmarkImage(gameId, landmarkName);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ generatingImageFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "生成标志物图片失败";
      set({ error: errorMsg, generatingImageFor: null });
    }
  },

  // 生成标志物描述
  generateLandmarkDescription: async (gameId: number, landmarkName: string) => {
    if (!gameId || !landmarkName) return;

    set({ generatingDescriptionFor: landmarkName, error: null });

    try {
      await api.collection.generateLandmarkDescription(gameId, landmarkName);

      // 刷新数据，使用 isRefresh=true 不隐藏已有内容
      await get().fetchCollection(gameId, true);

      set({ generatingDescriptionFor: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "生成标志物描述失败";
      set({ error: errorMsg, generatingDescriptionFor: null });
    }
  },

  // 清除选择
  clearSelection: () => set({ selectedCharacter: null, selectedItem: null, selectedLandmark: null }),

  // 清除错误
  clearError: () => set({ error: null }),
}));