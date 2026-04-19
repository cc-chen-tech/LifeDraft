/**
 * useSceneImageStore — 场景插画状态管理
 *
 * 管理游戏中的场景插画，包括当前轮次插画和历史插画
 *
 * ★ 场景插画类型：
 * - event: 事件发生时的插画
 * - result: 选择结果后的插画
 */
import { create } from "zustand";
import api from "@/lib/api";
import { useImageStore, type RoundSceneImage } from "./useImageStore";
import type { CharacterSettings } from "@/lib/types";

// 重导出 RoundSceneImage 类型
export type { RoundSceneImage };

// SSE 事件类型
interface SceneImageSSEEvent {
  type: "scene_image_ready" | "scene_image_failed" | "heartbeat";
  game_id: number;
  round_number: number;
  week: number;
  stage: string;
  image_url?: string;
  scene_description?: string;
  error?: string;
  timestamp: string;
}

interface SceneImageState {
  // ★ 当前轮次场景插画
  roundSceneImages: RoundSceneImage[];
  currentRoundSceneImage: RoundSceneImage | null;
  eventSceneImage: RoundSceneImage | null;
  resultSceneImage: RoundSceneImage | null;
  isLoadingRoundSceneImage: boolean;
  isRegeneratingRoundScene: boolean;
  roundSceneRegenerateError: string | null;

  // ★ 历史场景插画状态
  historySceneImage: RoundSceneImage | null;
  isLoadingHistoryImage: boolean;
  isGeneratingHistoryImage: boolean;
  isRegeneratingHistoryImage: boolean;

  // ★ SSE 连接
  sseConnection: EventSource | null;

  // Actions — Current Round Scene
  setCurrentRoundSceneImage: (image: RoundSceneImage | null) => void;
  setEventSceneImage: (image: RoundSceneImage | null) => void;
  setResultSceneImage: (image: RoundSceneImage | null) => void;
  addRoundSceneImage: (image: RoundSceneImage) => void;
  generateRoundSceneImage: (params: {
    gameId: number;
    roundNumber: number;
    storyText: string;
    characterSettings: CharacterSettings;
    playerName: string;
    enableSceneImage: boolean;
    week: number;
    stage?: string;
  }) => Promise<void>;
  fetchRoundSceneImage: (gameId: number, roundNumber: number, week: number, stage?: string) => Promise<void>;
  fetchAllRoundSceneImages: (gameId: number, currentRound: number, currentWeek: number) => Promise<void>;
  regenerateRoundSceneImage: (params: {
    gameId: number;
    roundNumber: number;
    storyText: string;
    characterSettings: CharacterSettings;
    playerName: string;
    userPrompt: string;
  }) => Promise<void>;

  // Actions — History Scene
  fetchHistorySceneImage: (gameId: number, week: number, round: number, stage?: string) => Promise<void>;
  generateHistorySceneImage: (params: {
    gameId: number;
    week: number;
    round: number;
    storyText: string;
    characterSettings: CharacterSettings;
    playerName: string;
    enableSceneImage: boolean;
    stage?: string;
  }) => Promise<void>;
  regenerateHistorySceneImage: (params: {
    gameId: number;
    week: number;
    round: number;
    storyText: string;
    characterSettings: CharacterSettings;
    playerName: string;
    userPrompt: string;
    sceneId: number;
  }) => Promise<void>;
  setHistorySceneImage: (image: RoundSceneImage | null) => void;

  // Actions — SSE
  subscribeToSceneImageEvents: (gameId: number) => void;
  unsubscribeFromSceneImageEvents: () => void;

  // Actions — Cache
  clearImageCache: () => void;
  clearCurrentRoundImages: () => void;
}

export const useSceneImageStore = create<SceneImageState>()(
  (set, get) => ({
    // Initial State
    roundSceneImages: [],
    currentRoundSceneImage: null,
    eventSceneImage: null,
    resultSceneImage: null,
    isLoadingRoundSceneImage: false,
    isRegeneratingRoundScene: false,
    roundSceneRegenerateError: null,

    // History
    historySceneImage: null,
    isLoadingHistoryImage: false,
    isGeneratingHistoryImage: false,
    isRegeneratingHistoryImage: false,

    // SSE
    sseConnection: null,

    // ==================== Current Round Scene Actions ====================
    setCurrentRoundSceneImage: (image) => set({ currentRoundSceneImage: image }),
    setEventSceneImage: (image) => set({ eventSceneImage: image }),
    setResultSceneImage: (image) => set({ resultSceneImage: image }),
    addRoundSceneImage: (image) => set((state) => ({
      // ★ 如果存在相同 week/round/stage 的图片，更新它；否则添加新条目
      roundSceneImages: state.roundSceneImages.some(
        s => s.week === image.week && s.round_number === image.round_number && s.stage === image.stage
      )
        ? state.roundSceneImages.map(
            s => s.week === image.week && s.round_number === image.round_number && s.stage === image.stage
              ? image
              : s
          )
        : [...state.roundSceneImages, image],
    })),

    generateRoundSceneImage: async ({ gameId, roundNumber, storyText, characterSettings, playerName, enableSceneImage, week, stage = 'result' }) => {
      const { playerImages, selectedImageIndex } = useImageStore.getState();

      if (!gameId || !storyText) {
        console.error("[generateRoundSceneImage] Missing gameId or storyText");
        return;
      }

      if (!enableSceneImage) {
        console.log("[generateRoundSceneImage] Scene image generation disabled");
        return;
      }

      console.log(`[generateRoundSceneImage] Generating scene for week ${week}, round ${roundNumber}, stage=${stage}...`);

      try {
        const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
        const playerImageId = selectedImage?.image_id;

        const result = await api.images.generateRoundSceneImage({
          game_id: gameId,
          round_number: roundNumber,
          story_text: storyText,
          character_settings: characterSettings,
          player_name: playerName,
          player_image_id: playerImageId,
          stage,
          week,
        });

        const newScene: RoundSceneImage = {
          scene_id: result.scene_id,
          week: result.week || week,
          round_number: result.round_number,
          stage: result.stage || stage,
          image_url: result.image_url,
          scene_description: result.scene_description,
          referenced_images: [],
          created_at: result.created_at,
        };

        set((state) => ({
          currentRoundSceneImage: newScene,
          eventSceneImage: newScene.stage === 'event' ? newScene : state.eventSceneImage,
          resultSceneImage: newScene.stage === 'result' ? newScene : state.resultSceneImage,
          roundSceneImages: state.roundSceneImages.some(s => s.week === newScene.week && s.round_number === roundNumber && s.stage === newScene.stage)
            ? state.roundSceneImages.map(s => s.week === newScene.week && s.round_number === roundNumber && s.stage === newScene.stage ? newScene : s)
            : [...state.roundSceneImages, newScene],
        }));

        console.log(`[generateRoundSceneImage] Scene generated: scene_id=${result.scene_id}`);
      } catch (err) {
        console.error(`[generateRoundSceneImage] Failed:`, err);
      }
    },

    fetchRoundSceneImage: async (gameId, roundNumber, week, stage) => {
      if (!gameId) return;

      set({ isLoadingRoundSceneImage: true });

      try {
        const scene = stage
          ? await api.images.getRoundSceneImageByStage(gameId, roundNumber, stage, week)
          : await api.images.getRoundSceneImage(gameId, roundNumber, week);

        if (scene && scene.scene_id) {
          const sceneWithStage: RoundSceneImage = {
            scene_id: scene.scene_id,
            week: scene.week || week,
            round_number: scene.round_number,
            stage: scene.stage || stage || 'result',
            image_url: scene.image_url,
            scene_description: scene.scene_description,
            referenced_images: (scene as { referenced_images?: number[] }).referenced_images || [],
            created_at: scene.created_at,
          };

          set((state) => ({
            // ★ 只更新对应 stage 的图片，不更新 currentRoundSceneImage
            // currentRoundSceneImage 由 fetchAllRoundSceneImages 统一管理
            eventSceneImage: sceneWithStage.stage === 'event' ? sceneWithStage : state.eventSceneImage,
            resultSceneImage: sceneWithStage.stage === 'result' ? sceneWithStage : state.resultSceneImage,
            roundSceneImages: state.roundSceneImages.some(s => s.week === sceneWithStage.week && s.round_number === roundNumber && s.stage === sceneWithStage.stage)
              ? state.roundSceneImages.map(s => s.week === sceneWithStage.week && s.round_number === roundNumber && s.stage === sceneWithStage.stage ? sceneWithStage : s)
              : [...state.roundSceneImages, sceneWithStage],
            isLoadingRoundSceneImage: false,
          }));
        } else {
          set({ isLoadingRoundSceneImage: false });
        }
      } catch (err) {
        const error = err as { status?: number; message?: string };
        if (error.status === 202) {
          // ★ 202 Accepted - 后端已触发生成，保持加载状态
          console.log(`[fetchRoundSceneImage] Generation triggered by backend, waiting...`);
          // 保持 isLoadingRoundSceneImage = true，前端会继续轮询
        } else if (error.status !== 404) {
          console.error(`[fetchRoundSceneImage] Failed:`, err);
          set({ isLoadingRoundSceneImage: false });
        } else {
          // 404 - 未找到且无法生成，停止加载
          set({ isLoadingRoundSceneImage: false });
        }
      }
    },

    fetchAllRoundSceneImages: async (gameId, currentRound, currentWeek) => {
      if (!gameId) return;

      set({ isLoadingRoundSceneImage: true });

      try {
        const result = await api.images.getAllRoundSceneImages(gameId);
        const scenes: RoundSceneImage[] = (result.scenes || []).map(s => ({
          ...s,
          stage: s.stage || 'result',
          referenced_images: s.referenced_images || [],
        }));

        const currentEventScene = scenes.find(
          s => s.week === currentWeek && s.round_number === currentRound && s.stage === 'event'
        ) || null;
        const currentResultScene = scenes.find(
          s => s.week === currentWeek && s.round_number === currentRound && s.stage === 'result'
        ) || null;
        // ★ 只返回当前周次当前轮次的场景，不跨周次查找
        const currentScene = currentEventScene || currentResultScene || null;

        set({
          roundSceneImages: scenes,
          currentRoundSceneImage: currentScene,
          eventSceneImage: currentEventScene,
          resultSceneImage: currentResultScene,
          isLoadingRoundSceneImage: false,
        });
      } catch (err) {
        console.error("[fetchAllRoundSceneImages] Failed:", err);
        set({ isLoadingRoundSceneImage: false });
      }
    },

    regenerateRoundSceneImage: async ({ gameId, roundNumber, storyText, characterSettings, playerName, userPrompt }) => {
      const { currentRoundSceneImage } = get();
      const { playerImages, selectedImageIndex } = useImageStore.getState();

      if (!gameId || !currentRoundSceneImage) {
        console.error("[regenerateRoundSceneImage] Missing required data");
        return;
      }

      set({ isRegeneratingRoundScene: true, roundSceneRegenerateError: null });

      try {
        const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
        const playerImageId = selectedImage?.image_id;

        const result = await api.images.regenerateRoundSceneImage({
          game_id: gameId,
          round_number: roundNumber,
          story_text: storyText,
          character_settings: characterSettings,
          player_name: playerName,
          user_prompt: userPrompt,
          current_scene_id: currentRoundSceneImage.scene_id,
          player_image_id: playerImageId,
        });

        const timestamp = Date.now();
        const updatedScene: RoundSceneImage = {
          scene_id: result.scene_id,
          week: result.week ?? currentRoundSceneImage.week ?? 0,
          round_number: result.round_number,
          stage: result.stage ?? currentRoundSceneImage.stage ?? 'result',
          image_url: result.image_url,
          scene_description: result.scene_description,
          referenced_images: [],
          created_at: result.created_at || new Date(timestamp).toISOString(),
        };

        console.log("[regenerateRoundSceneImage] Success:", {
          new_url: result.image_url,
          old_url: currentRoundSceneImage.image_url,
          created_at: updatedScene.created_at,
        });

        set((state) => ({
          currentRoundSceneImage: updatedScene,
          roundSceneImages: state.roundSceneImages.map(s =>
            s.scene_id === currentRoundSceneImage.scene_id ? updatedScene : s
          ),
          isRegeneratingRoundScene: false,
        }));
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "场景插画重新生成失败";
        console.error("[regenerateRoundSceneImage] Error:", errorMsg);
        set({ isRegeneratingRoundScene: false, roundSceneRegenerateError: errorMsg });
      }
    },

    // ==================== History Scene Actions ====================
    fetchHistorySceneImage: async (gameId, week, round, stage) => {
      if (!gameId) return;

      set({ isLoadingHistoryImage: true });

      try {
        const scene = stage
          ? await api.images.getRoundSceneImageByStage(gameId, round, stage, week)
          : await api.images.getRoundSceneImage(gameId, round, week);

        if (scene && scene.scene_id) {
          const sceneWithStage: RoundSceneImage = {
            scene_id: scene.scene_id,
            week: scene.week ?? week,
            round_number: scene.round_number,
            stage: scene.stage || stage || 'result',
            image_url: scene.image_url,
            scene_description: scene.scene_description,
            referenced_images: (scene as { referenced_images?: number[] }).referenced_images || [],
            created_at: scene.created_at,
          };

          set({ historySceneImage: sceneWithStage, isLoadingHistoryImage: false });
        } else {
          set({ historySceneImage: null, isLoadingHistoryImage: false });
        }
      } catch (err) {
        const error = err as { status?: number };
        if (error.status !== 404) {
          console.error(`[fetchHistorySceneImage] Failed:`, err);
        }
        set({ historySceneImage: null, isLoadingHistoryImage: false });
      }
    },

    generateHistorySceneImage: async ({ gameId, week, round, storyText, characterSettings, playerName, enableSceneImage, stage = 'result' }) => {
      const { playerImages, selectedImageIndex } = useImageStore.getState();

      if (!gameId || !storyText) {
        console.error("[generateHistorySceneImage] Missing gameId or storyText");
        return;
      }

      if (!enableSceneImage) {
        console.log("[generateHistorySceneImage] Scene image generation disabled");
        return;
      }

      set({ isGeneratingHistoryImage: true });

      try {
        const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
        const playerImageId = selectedImage?.image_id;

        const result = await api.images.generateRoundSceneImage({
          game_id: gameId,
          round_number: round,
          story_text: storyText,
          character_settings: characterSettings,
          player_name: playerName,
          player_image_id: playerImageId,
          stage,
          week,
        });

        const newScene: RoundSceneImage = {
          scene_id: result.scene_id,
          week: result.week ?? week,
          round_number: result.round_number,
          stage: result.stage ?? stage,
          image_url: result.image_url,
          scene_description: result.scene_description,
          referenced_images: [],
          created_at: result.created_at,
        };

        set({ historySceneImage: newScene, isGeneratingHistoryImage: false });
        console.log(`[generateHistorySceneImage] Scene generated: scene_id=${result.scene_id}`);
      } catch (err) {
        console.error(`[generateHistorySceneImage] Failed:`, err);
        set({ isGeneratingHistoryImage: false });
      }
    },

    regenerateHistorySceneImage: async ({ gameId, week, round, storyText, characterSettings, playerName, userPrompt, sceneId }) => {
      const { playerImages, selectedImageIndex } = useImageStore.getState();

      if (!gameId) {
        console.error("[regenerateHistorySceneImage] Missing gameId");
        return;
      }

      set({ isRegeneratingHistoryImage: true });

      try {
        const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
        const playerImageId = selectedImage?.image_id;

        const result = await api.images.regenerateRoundSceneImage({
          game_id: gameId,
          round_number: round,
          story_text: storyText,
          character_settings: characterSettings,
          player_name: playerName,
          user_prompt: userPrompt,
          current_scene_id: sceneId,
          player_image_id: playerImageId,
        });

        const updatedScene: RoundSceneImage = {
          scene_id: result.scene_id,
          week: result.week ?? week,
          round_number: result.round_number,
          stage: result.stage ?? 'result',
          image_url: result.image_url,
          scene_description: result.scene_description,
          referenced_images: [],
          created_at: result.created_at,
        };

        set({ historySceneImage: updatedScene, isRegeneratingHistoryImage: false });
        console.log(`[regenerateHistorySceneImage] Scene regenerated: scene_id=${result.scene_id}`);
      } catch (err) {
        console.error(`[regenerateHistorySceneImage] Failed:`, err);
        set({ isRegeneratingHistoryImage: false });
      }
    },

    setHistorySceneImage: (image) => set({ historySceneImage: image }),

    // ==================== Cache Actions ====================
    clearImageCache: () => {
      console.log("[clearImageCache] Clearing image cache...");
      set({
        roundSceneImages: [],
        currentRoundSceneImage: null,
        eventSceneImage: null,
        resultSceneImage: null,
        isLoadingRoundSceneImage: false,
        isRegeneratingRoundScene: false,
        roundSceneRegenerateError: null,
        historySceneImage: null,
        isLoadingHistoryImage: false,
        isGeneratingHistoryImage: false,
        isRegeneratingHistoryImage: false,
      });
      useImageStore.getState().clearCache?.();
      console.log("[clearImageCache] Image cache cleared");
    },

    clearCurrentRoundImages: () => {
      set({
        roundSceneImages: [],
        currentRoundSceneImage: null,
        eventSceneImage: null,
        resultSceneImage: null,
      });
    },

    // ==================== SSE Actions ====================
    subscribeToSceneImageEvents: (gameId) => {
      const { sseConnection } = get();

      // 关闭已有连接
      if (sseConnection) {
        sseConnection.close();
      }

      if (typeof window === "undefined" || typeof EventSource === "undefined") return;

      const url = `/api/images/scene/events/${gameId}`;
      console.log(`[SSE] Connecting to ${url}`);

      const es = new EventSource(url);

      es.onopen = () => {
        console.log(`[SSE] Connected for game ${gameId}`);
      };

      es.onmessage = (event) => {
        try {
          const data: SceneImageSSEEvent = JSON.parse(event.data);
          console.log(`[SSE] Received event: type=${data.type}, game=${data.game_id}, round=${data.round_number}, stage=${data.stage}`);

          if (data.type === "heartbeat") {
            return;
          }

          if (data.type === "scene_image_failed") {
            console.warn(`[SSE] Scene generation failed: ${data.error}`);
            set({ isLoadingRoundSceneImage: false });
            return;
          }

          if (data.type === "scene_image_ready") {
            const newScene: RoundSceneImage = {
              scene_id: 0, // SSE 事件不包含 scene_id，后续 fetch 会补充
              week: data.week,
              round_number: data.round_number,
              stage: data.stage,
              image_url: data.image_url || "",
              scene_description: data.scene_description || "",
              referenced_images: [],
              created_at: data.timestamp,
            };

            set((state) => {
              const updates: Partial<SceneImageState> = {
                isLoadingRoundSceneImage: false,
                roundSceneImages: state.roundSceneImages.some(
                  (s) => s.week === newScene.week && s.round_number === newScene.round_number && s.stage === newScene.stage
                )
                  ? state.roundSceneImages.map((s) =>
                      s.week === newScene.week && s.round_number === newScene.round_number && s.stage === newScene.stage
                        ? newScene
                        : s
                    )
                  : [...state.roundSceneImages, newScene],
              };

              // 更新当前轮次对应 stage 的图片
              if (newScene.stage === "event") {
                updates.eventSceneImage = newScene;
              } else if (newScene.stage === "result") {
                updates.resultSceneImage = newScene;
              }

              // 如果当前轮次没有明确区分 event/result，也更新 currentRoundSceneImage
              updates.currentRoundSceneImage = newScene;

              return updates;
            });

            console.log(`[SSE] Scene image updated: week=${data.week}, round=${data.round_number}, stage=${data.stage}`);
          }
        } catch (err) {
          console.error("[SSE] Failed to parse event:", err);
        }
      };

      es.onerror = (err) => {
        console.warn("[SSE] Connection error:", err);
        // EventSource 会自动重连，无需手动处理
      };

      set({ sseConnection: es });
    },

    unsubscribeFromSceneImageEvents: () => {
      const { sseConnection } = get();
      if (sseConnection) {
        console.log("[SSE] Closing connection");
        sseConnection.close();
        set({ sseConnection: null });
      }
    },
  })
);
