/**
 * useCollectionStore — 收集系统状态
 *
 * 管理人物、物品和标志物收集数据
 */
import { create } from "zustand";
import type { CharacterCollectionItem, ItemCollectionItem, LandmarkCollectionItem, CollectionResponse, RecognizedEntity, EntityRecognitionResponse } from "@/lib/types";
import api from "@/lib/api";

type CollectionEntity = CharacterCollectionItem | ItemCollectionItem | LandmarkCollectionItem;

function mergeVisibleEntityData<T extends CollectionEntity>(nextItems: T[], currentItems: T[]): T[] {
  return nextItems.map((next) => {
    const current = currentItems.find((item) => item.name === next.name);
    if (!current) return next;

    return {
      ...next,
      image_url: next.image_url || current.image_url,
      image_generated: next.image_generated || current.image_generated,
      description: next.description || current.description,
      ...("description_generated" in next && "description_generated" in current
        ? { description_generated: next.description_generated || current.description_generated }
        : {}),
    };
  });
}

// Request de-dupe and short-lived cache keep the collection panel responsive.
let _fetchInFlight: { gameId: number; promise: Promise<void> } | null = null;
let _collectionCache: { gameId: number; timestamp: number } | null = null;
const CACHE_TTL_MS = 30000;

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

  // 识别状态
  isRecognizing: boolean;  // 是否正在进行实体识别
  recognizedEntities: EntityRecognitionResponse | null;  // 识别结果

  // 删除状态
  isDeleting: boolean;  // 是否正在删除
  deletingEntity: string | null;  // 正在删除的实体名称

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
  batchGenerateLandmarkImages: (gameId: number) => Promise<void>;
  generateCharacterDescription: (gameId: number, name: string) => Promise<void>;
  generateItemDescription: (gameId: number, itemName: string) => Promise<void>;
  generateLandmarkDescription: (gameId: number, landmarkName: string) => Promise<void>;
  regenerateCharacterImage: (gameId: number, name: string, feedback: string, imageId?: number) => Promise<void>;
  regenerateItemImage: (gameId: number, itemName: string, feedback: string) => Promise<void>;

  // 识别相关 Actions
  recognizeEntities: (gameId: number, minAppearances?: number) => Promise<EntityRecognitionResponse | null>;
  addRecognizedEntities: (gameId: number, entities: { items: RecognizedEntity[]; characters: RecognizedEntity[]; landmarks: RecognizedEntity[] }) => Promise<void>;
  clearRecognizedEntities: () => void;

  // 手动添加 Actions
  createItem: (gameId: number, name: string, generateDescription?: boolean) => Promise<void>;

  // 删除 Actions
  deleteItem: (gameId: number, itemName: string) => Promise<void>;
  deleteCharacter: (gameId: number, characterName: string) => Promise<void>;
  deleteLandmark: (gameId: number, landmarkName: string) => Promise<void>;

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

  // 初始识别状态
  isRecognizing: false,
  recognizedEntities: null,

  // 初始删除状态
  isDeleting: false,
  deletingEntity: null,

  // 初始错误
  error: null,

  // 获取收集数据
  fetchCollection: async (gameId: number, isRefresh: boolean = false) => {
    if (!gameId) {
      set({ error: "游戏ID不存在" });
      return;
    }

    if (!isRefresh && _fetchInFlight?.gameId === gameId) {
      console.log("[fetchCollection] 复用已有请求 gameId=", gameId);
      return _fetchInFlight.promise;
    }

    if (!isRefresh) {
      const now = Date.now();
      const state = get();
      const hasData = state.characters.length > 0 || state.items.length > 0 || state.landmarks.length > 0;
      if (
        _collectionCache?.gameId === gameId &&
        now - _collectionCache.timestamp < CACHE_TTL_MS &&
        hasData
      ) {
        console.log("[fetchCollection] 命中缓存，跳过请求 gameId=", gameId);
        return;
      }
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
      set({ isRefreshing: true, error: null });
    } else {
      // 初始加载模式：显示加载状态
      console.log("[fetchCollection] 初始加载模式 - 显示加载中");
      set({ isLoading: true, error: null });
    }

    try {
      const fetchPromise = api.collection.get(gameId);
      if (!isRefresh) {
        const wrappedPromise = fetchPromise
          .then(() => undefined)
          .catch(() => undefined)
          .finally(() => {
            if (_fetchInFlight?.gameId === gameId) {
              _fetchInFlight = null;
            }
          });
        _fetchInFlight = { gameId, promise: wrappedPromise };
      }

      const result: CollectionResponse = await fetchPromise;
      if (_fetchInFlight?.gameId === gameId) {
        _fetchInFlight = null;
      }

      const newCharacters = result.characters || [];
      const newItems = result.items || [];
      const newLandmarks = result.landmarks || [];

      const mergedCharacters = isRefresh
        ? mergeVisibleEntityData(newCharacters, get().characters)
        : newCharacters;
      const mergedItems = isRefresh
        ? mergeVisibleEntityData(newItems, get().items)
        : newItems;
      const mergedLandmarks = isRefresh
        ? mergeVisibleEntityData(newLandmarks, get().landmarks)
        : newLandmarks;

      // 恢复选中状态（从新数据中找到对应的人物/物品/标志物）
      const newSelectedCharacter = selectedCharacterName
        ? mergedCharacters.find(c => c.name === selectedCharacterName) || null
        : null;
      const newSelectedItem = selectedItemName
        ? mergedItems.find(i => i.name === selectedItemName) || null
        : null;
      const newSelectedLandmark = selectedLandmarkName
        ? mergedLandmarks.find(l => l.name === selectedLandmarkName) || null
        : null;

      console.log("[fetchCollection] 数据更新完成:", {
        charactersCount: newCharacters.length,
        itemsCount: newItems.length,
        landmarksCount: newLandmarks.length,
        isRefresh,
      });

      _collectionCache = { gameId, timestamp: Date.now() };

      set({
        characters: mergedCharacters,
        items: mergedItems,
        landmarks: mergedLandmarks,
        selectedCharacter: newSelectedCharacter,
        selectedItem: newSelectedItem,
        selectedLandmark: newSelectedLandmark,
        isLoading: false,
        isRefreshing: false,
      });
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

  // 批量生成所有待生成标志物图片
  batchGenerateLandmarkImages: async (gameId: number) => {
    if (!gameId) return;

    const pendingLandmarks = get().landmarks.filter((landmark) => !landmark.image_generated);
    if (pendingLandmarks.length === 0) return;

    set({ error: null });

    for (const landmark of pendingLandmarks) {
      set({ generatingImageFor: landmark.name });
      try {
        await api.collection.generateLandmarkImage(gameId, landmark.name);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "批量生成标志物图片失败";
        set({ error: errorMsg, generatingImageFor: null });
        break;
      }
    }

    await get().fetchCollection(gameId, true);
    set({ generatingImageFor: null });
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

  // ==================== 实体识别 Actions ====================

  // 识别实体
  recognizeEntities: async (gameId: number, minAppearances: number = 3) => {
    set({ isRecognizing: true, isLoading: false, error: null });

    try {
      const result = await api.collection.recognizeEntities(gameId, {
        entity_types: ["item", "character", "landmark"],
        min_appearances: minAppearances,
      });

      set({ recognizedEntities: result, isRecognizing: false });
      return result;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "实体识别失败";
      console.error("[recognizeEntities] 错误:", errorMsg);
      set({ error: errorMsg, isRecognizing: false });
      return null;
    }
  },

  // 添加识别出的实体
  addRecognizedEntities: async (gameId: number, entities: { items: RecognizedEntity[]; characters: RecognizedEntity[]; landmarks: RecognizedEntity[] }) => {
    set({ isLoading: true, error: null });

    try {
      await api.collection.addEntities(gameId, entities);

      // 刷新收集数据
      await get().fetchCollection(gameId, true);

      // 清除识别结果
      set({ recognizedEntities: null, isLoading: false });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "添加实体失败";
      console.error("[addRecognizedEntities] 错误:", errorMsg);
      set({ error: errorMsg, isLoading: false });
    }
  },

  // 清除识别结果
  clearRecognizedEntities: () => set({ recognizedEntities: null }),

  // ==================== 手动添加 Actions ====================

  // 手动创建物品
  createItem: async (gameId: number, name: string, generateDescription: boolean = true) => {
    set({ isLoading: true, error: null });

    try {
      await api.collection.createItem(gameId, {
        name,
        generate_description: generateDescription,
      });

      // 刷新收集数据
      await get().fetchCollection(gameId, true);

      set({ isLoading: false });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "创建物品失败";
      console.error("[createItem] 错误:", errorMsg);
      set({ error: errorMsg, isLoading: false });
    }
  },

  // ==================== 删除 Actions ====================

  // 删除物品
  deleteItem: async (gameId: number, itemName: string) => {
    set({ isDeleting: true, deletingEntity: itemName, error: null });

    try {
      await api.collection.deleteItem(gameId, itemName);

      // 如果删除的是当前选中的物品，清除选择
      const currentSelected = get().selectedItem;
      if (currentSelected?.name === itemName) {
        set({ selectedItem: null });
      }

      // 刷新收集数据
      await get().fetchCollection(gameId, true);

      set({ isDeleting: false, deletingEntity: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "删除物品失败";
      console.error("[deleteItem] 错误:", errorMsg);
      set({ error: errorMsg, isDeleting: false, deletingEntity: null });
    }
  },

  // 删除人物
  deleteCharacter: async (gameId: number, characterName: string) => {
    set({ isDeleting: true, deletingEntity: characterName, error: null });

    try {
      await api.collection.deleteCharacter(gameId, characterName);

      // 如果删除的是当前选中的人物，清除选择
      const currentSelected = get().selectedCharacter;
      if (currentSelected?.name === characterName) {
        set({ selectedCharacter: null });
      }

      // 刷新收集数据
      await get().fetchCollection(gameId, true);

      set({ isDeleting: false, deletingEntity: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "删除人物失败";
      console.error("[deleteCharacter] 错误:", errorMsg);
      set({ error: errorMsg, isDeleting: false, deletingEntity: null });
    }
  },

  // 删除标志物
  deleteLandmark: async (gameId: number, landmarkName: string) => {
    set({ isDeleting: true, deletingEntity: landmarkName, error: null });

    try {
      await api.collection.deleteLandmark(gameId, landmarkName);

      // 如果删除的是当前选中的标志物，清除选择
      const currentSelected = get().selectedLandmark;
      if (currentSelected?.name === landmarkName) {
        set({ selectedLandmark: null });
      }

      // 刷新收集数据
      await get().fetchCollection(gameId, true);

      set({ isDeleting: false, deletingEntity: null });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "删除标志物失败";
      console.error("[deleteLandmark] 错误:", errorMsg);
      set({ error: errorMsg, isDeleting: false, deletingEntity: null });
    }
  },
}));
