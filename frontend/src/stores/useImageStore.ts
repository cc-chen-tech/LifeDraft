/**
 * useImageStore — 图片相关状态
 *
 * 管理玩家形象、开场插画等图片状态
 *
 * ★ 注意：此 store 不再持久化到 localStorage
 * - 玩家形象在页面加载时从服务器重新获取
 * - 场景插画相关状态由 useGameStore 管理
 */
import { create } from "zustand";
import type { ImageResponse, OpeningIllustrationResponse } from "@/lib/types";
import api from "@/lib/api";

// 场景插画类型（导出供 useGameStore 使用）
export interface RoundSceneImage {
  scene_id: number;
  week: number;
  round_number: number;
  stage: string;
  image_url: string;
  scene_description: string;
  referenced_images: number[];
  created_at: string;
}

interface ImageState {
  // 玩家形象
  playerImage: ImageResponse | null;
  playerImages: ImageResponse[];
  selectedImageIndex: number;
  isGeneratingImage: boolean;
  isLoadingPlayerImages: boolean;  // ★ 加载玩家图片中
  imageFeedback: string;

  // 开场插画
  openingIllustration: OpeningIllustrationResponse | null;
  isGeneratingIllustration: boolean;
  illustrationError: string | null;

  // Actions — Player Image
  setPlayerImage: (image: ImageResponse | null) => void;
  setPlayerImages: (images: ImageResponse[]) => void;
  setSelectedImageIndex: (index: number) => void;
  setIsGeneratingImage: (isGenerating: boolean) => void;
  setImageFeedback: (feedback: string) => void;
  generatePlayerImage: (gameId: number, playerName: string, characterSettings: Record<string, unknown>, feedback?: string) => Promise<void>;
  regeneratePlayerImage: (feedback: string) => Promise<void>;
  regenerateFreshPlayerImage: () => Promise<void>;
  // ★ 从服务器重新加载玩家形象
  loadPlayerImages: (gameId: number) => Promise<void>;

  // Actions — Opening Illustration
  setOpeningIllustration: (illustration: OpeningIllustrationResponse | null) => void;
  setIsGeneratingIllustration: (isGenerating: boolean) => void;
  setIllustrationError: (error: string | null) => void;
  generateOpeningIllustration: (gameId: number, openingStory: string, characterSettings: Record<string, unknown>, playerName: string) => Promise<void>;
  regenerateOpeningIllustration: (gameId: number, openingStory: string, characterSettings: Record<string, unknown>, playerName: string, userPrompt: string) => Promise<void>;

  // Actions — Cache
  clearCache: () => void;
}

export const useImageStore = create<ImageState>()(
  (set, get) => ({
    // 玩家形象初始状态
    playerImage: null,
    playerImages: [],
    selectedImageIndex: 0,
    isGeneratingImage: false,
    isLoadingPlayerImages: false,  // ★ 初始不处于加载状态
    imageFeedback: "",

    // 开场插画初始状态
    openingIllustration: null,
    isGeneratingIllustration: false,
    illustrationError: null,

    // Player Image Actions
    setPlayerImage: (image) => set({ playerImage: image, playerImages: image ? [image] : [], selectedImageIndex: 0 }),
    setPlayerImages: (images) => set({ playerImages: images, selectedImageIndex: 0, playerImage: images[0] || null }),
    setSelectedImageIndex: (index) => set((state) => ({ selectedImageIndex: index, playerImage: state.playerImages[index] || null })),
    setIsGeneratingImage: (isGenerating) => set({ isGeneratingImage: isGenerating }),
    setImageFeedback: (feedback) => set({ imageFeedback: feedback }),

    generatePlayerImage: async (gameId, playerName, characterSettings, feedback) => {
      if (!gameId) {
        throw new Error("游戏ID不存在，请先完成角色创建");
      }
      if (!playerName) {
        throw new Error("请先输入角色姓名");
      }

      set({ isGeneratingImage: true, imageFeedback: feedback || "" });

      try {
        const era = characterSettings.era as Record<string, unknown> | null;
        const gender = characterSettings.gender as Record<string, unknown> | null;
        const age = characterSettings.age as Record<string, unknown> | null;
        const world = characterSettings.world as Record<string, unknown> | null;

        const parts: string[] = [];
        if (age) {
          if (typeof age.age === "number") {
            parts.push(`${age.age}岁`);
          } else if (age.age_range) {
            parts.push(String(age.age_range));
          }
        }
        if (gender && gender.gender) {
          parts.push(String(gender.gender));
        }
        if (world) {
          if (world.cultural_context) parts.push(String(world.cultural_context));
          if (world.special_features) parts.push(String(world.special_features));
        }

        const description = parts.join("，") || "一个普通人";
        const eraName = era?.era_name || era?.era_description || "现代";

        const extraContext = {
          characterSettings: { era: characterSettings.era, age: characterSettings.age, gender: characterSettings.gender, world: characterSettings.world },
          playerName,
          feedback,
        };

        const result = await api.images.generate({
          game_id: gameId,
          image_type: "character",
          entity_name: playerName,
          description,
          entity_key: "player_main",
          era: String(eraName),
          extra_context: extraContext,
          feedback,
        });

        const images = result.images || [];
        set({
          playerImages: images,
          playerImage: images[0] || null,
          selectedImageIndex: 0,
          isGeneratingImage: false,
          imageFeedback: "",
        });
      } catch (err) {
        console.error("[generatePlayerImage] Failed:", err);
        set({ isGeneratingImage: false });
        throw err;
      }
    },

    regeneratePlayerImage: async (feedback) => {
      const { playerImages, selectedImageIndex } = get();
      const selectedImage = playerImages[selectedImageIndex] || playerImages[0];

      if (!selectedImage) {
        throw new Error("没有可重新生成的图片");
      }

      set({ isGeneratingImage: true, imageFeedback: feedback });

      try {
        const result = await api.images.regenerate({
          image_id: selectedImage.image_id,
          feedback,
        });

        const newImages = result.images || [];
        set({
          playerImages: newImages,
          playerImage: newImages[0] || null,
          selectedImageIndex: 0,
          isGeneratingImage: false,
          imageFeedback: "",
        });
      } catch (err) {
        console.error("[regeneratePlayerImage] Failed:", err);
        set({ isGeneratingImage: false });
        throw err;
      }
    },

    regenerateFreshPlayerImage: async () => {
      const { playerImages, selectedImageIndex } = get();
      const selectedImage = playerImages[selectedImageIndex] || playerImages[0];

      if (!selectedImage) {
        throw new Error("没有可重新生成的图片");
      }

      set({ isGeneratingImage: true });

      try {
        const result = await api.images.regenerateFresh(selectedImage.image_id, true);
        const newImages = result.images || [];
        set({
          playerImages: newImages,
          playerImage: newImages[0] || null,
          selectedImageIndex: 0,
          isGeneratingImage: false,
          imageFeedback: "",
        });
      } catch (err) {
        console.error("[regenerateFreshPlayerImage] Failed:", err);
        set({ isGeneratingImage: false });
        throw err;
      }
    },

    // ★ 从服务器重新加载玩家形象
    loadPlayerImages: async (gameId: number) => {
      if (!gameId) return;

      set({ isLoadingPlayerImages: true });

      try {
        console.log("[loadPlayerImages] Loading player images for game:", gameId);
        const result = await api.images.listByGame(gameId, "character");

        if (result.images && result.images.length > 0) {
          // 过滤出主角图片（entity_key = "player_main" 或未设置时默认是主角）
          const playerImages = result.images.filter(
            (img) => img.entity_key === "player_main" || (!img.entity_key && img.entity_name)
          );

          if (playerImages.length > 0) {
            set({
              playerImages,
              playerImage: playerImages[0],
              selectedImageIndex: 0,
              isLoadingPlayerImages: false,
            });
            console.log("[loadPlayerImages] Loaded", playerImages.length, "player images");
          } else {
            set({ isLoadingPlayerImages: false });
          }
        } else {
          set({ isLoadingPlayerImages: false });
        }
      } catch (err) {
        console.error("[loadPlayerImages] Failed:", err);
        // 加载失败不抛出错误，保持空状态
        set({ isLoadingPlayerImages: false });
      }
    },

    // Opening Illustration Actions
    setOpeningIllustration: (illustration) => set({ openingIllustration: illustration }),
    setIsGeneratingIllustration: (isGenerating) => set({ isGeneratingIllustration: isGenerating }),
    setIllustrationError: (error) => set({ illustrationError: error }),

    generateOpeningIllustration: async (gameId, openingStory, characterSettings, playerName) => {
      if (!gameId || !openingStory) {
        console.error("[generateOpeningIllustration] Missing gameId or openingStory");
        return;
      }

      set({ isGeneratingIllustration: true, illustrationError: null });

      try {
        const { playerImages, selectedImageIndex } = get();
        const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
        const playerImageId = selectedImage?.image_id;

        const result = await api.images.generateOpeningIllustration({
          game_id: gameId,
          story_text: openingStory,
          character_settings: characterSettings,
          player_name: playerName,
          player_image_id: playerImageId,
        });

        set({ openingIllustration: result, isGeneratingIllustration: false });
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "插画生成失败";
        set({ isGeneratingIllustration: false, illustrationError: errorMsg });
      }
    },

    regenerateOpeningIllustration: async (gameId, openingStory, characterSettings, playerName, userPrompt) => {
      const { openingIllustration, playerImages, selectedImageIndex } = get();

      if (!gameId || !openingStory || !openingIllustration) {
        console.error("[regenerateOpeningIllustration] Missing required data");
        return;
      }

      set({ isGeneratingIllustration: true, illustrationError: null });

      try {
        const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
        const playerImageId = selectedImage?.image_id;

        const result = await api.images.regenerateOpeningIllustration({
          game_id: gameId,
          story_text: openingStory,
          character_settings: characterSettings,
          player_name: playerName,
          player_image_id: playerImageId,
          user_prompt: userPrompt,
          current_illustration_id: openingIllustration.image_id,
        });

        set({ openingIllustration: result, isGeneratingIllustration: false });
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "插画重新生成失败";
        set({ isGeneratingIllustration: false, illustrationError: errorMsg });
      }
    },

    // ★ 清理缓存
    clearCache: () => {
      console.log("[useImageStore] Clearing cache...");
      set({
        playerImage: null,
        playerImages: [],
        selectedImageIndex: 0,
        isGeneratingImage: false,
        imageFeedback: "",
        openingIllustration: null,
        isGeneratingIllustration: false,
        illustrationError: null,
      });
    },
  })
);
