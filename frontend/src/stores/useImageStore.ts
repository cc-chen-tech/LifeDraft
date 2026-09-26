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
import type { ImageResponse, OpeningIllustrationResponse, CharacterSettings, EraSetting } from "@/lib/types";
import api, { type PortraitCandidateState, type PortraitImageGenerationJob } from "@/lib/api";

const PORTRAIT_JOB_POLL_INTERVAL_MS = 3_000;
let portraitJobPollTimer: ReturnType<typeof setTimeout> | null = null;
let activePortraitJobGameId: number | null = null;

function clearPortraitJobPollTimer(): void {
  if (portraitJobPollTimer !== null) {
    clearTimeout(portraitJobPollTimer);
    portraitJobPollTimer = null;
  }
}

function getPlayerImageErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const message = error.message.trim();
    if (/failed to fetch|networkerror|load failed/i.test(message)) {
      return "人物形象服务暂时无法连接，请检查网络后重试。";
    }
    if (/abort|timeout|timed out/i.test(message)) {
      return "人物形象生成超时，请稍后重试。";
    }
    if (message) {
      return message;
    }
  }
  return fallback;
}

// 场景插画类型（导出供 useGameStore 使用）
export interface RoundSceneImage {
  scene_id: number;
  week: number;
  round_number: number;
  story_date?: string;
  day_index?: number;
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
  selectedImageId: number | null;
  portraitCandidates: PortraitCandidateState | null;
  isGeneratingImage: boolean;
  imageGenerationError: string | null;
  portraitImageJob: PortraitImageGenerationJob | null;
  isLoadingPlayerImages: boolean;  // ★ 加载玩家图片中
  imageFeedback: string;

  // 开场插画
  openingIllustration: OpeningIllustrationResponse | null;
  isGeneratingIllustration: boolean;
  illustrationError: string | null;

  enqueuePortraitCandidates: (gameId: number, mode: 'initial' | 'fresh') => Promise<void>;
  refreshPortraitCandidates: (gameId: number) => Promise<void>;
  retryMissingPortraitSlots: (batchId: number) => Promise<void>;
  selectPlayerImage: (imageId: number) => Promise<void>;

  // Actions — Player Image
  setPlayerImage: (image: ImageResponse | null) => void;
  setPlayerImages: (images: ImageResponse[]) => void;
  setSelectedImageIndex: (index: number) => void;
  setIsGeneratingImage: (isGenerating: boolean) => void;
  setImageFeedback: (feedback: string) => void;
  generatePlayerImage: (gameId: number, playerName: string, characterSettings: CharacterSettings, feedback?: string) => Promise<void>;
  refreshPortraitImageJob: (gameId: number) => Promise<void>;
  stopPortraitImagePolling: () => void;
  regeneratePlayerImage: (feedback: string) => Promise<void>;
  regenerateFreshPlayerImage: () => Promise<void>;
  // ★ 从服务器重新加载玩家形象
  loadPlayerImages: (gameId: number) => Promise<void>;

  // Actions — Opening Illustration
  setOpeningIllustration: (illustration: OpeningIllustrationResponse | null) => void;
  setIsGeneratingIllustration: (isGenerating: boolean) => void;
  setIllustrationError: (error: string | null) => void;
  generateOpeningIllustration: (gameId: number, openingStory: string, characterSettings: CharacterSettings, playerName: string) => Promise<void>;
  regenerateOpeningIllustration: (gameId: number, openingStory: string, characterSettings: CharacterSettings, playerName: string, userPrompt: string) => Promise<void>;

  // Actions — Cache
  clearCache: () => void;
}

export const useImageStore = create<ImageState>()(
  (set, get) => ({
    // 玩家形象初始状态
    playerImage: null,
    playerImages: [],
    selectedImageIndex: 0,
    selectedImageId: null,
    portraitCandidates: null,
    isGeneratingImage: false,
    imageGenerationError: null,
    portraitImageJob: null,
    isLoadingPlayerImages: false,  // ★ 初始不处于加载状态
    imageFeedback: "",

    // 开场插画初始状态
    openingIllustration: null,
    isGeneratingIllustration: false,
    illustrationError: null,

    // Player Image Actions
    setPlayerImage: (image) => set({
      playerImage: image,
      playerImages: image ? [image] : [],
      selectedImageIndex: 0,
      selectedImageId: image?.image_id ?? null,
      imageGenerationError: image ? null : get().imageGenerationError,
    }),
    setPlayerImages: (images) => set((state) => {
      const selected = images.find(image => image.image_id === state.selectedImageId) ??
        (state.selectedImageId === null ? images[0] : state.playerImage);
      return {
        playerImages: images,
        selectedImageId: selected?.image_id ?? state.selectedImageId,
        selectedImageIndex: Math.max(0, images.findIndex(image => image.image_id === selected?.image_id)),
        playerImage: selected ?? null,
      };
    }),
    // Compatibility for consumers that already have a server-confirmed index.
    setSelectedImageIndex: (index) => set((state) => ({ selectedImageIndex: index,
      selectedImageId: state.playerImages[index]?.image_id ?? null, playerImage: state.playerImages[index] || null })),
    selectPlayerImage: async (imageId) => {
      const image = get().playerImages.find(image => image.image_id === imageId);
      if (!image?.game_id) throw new Error("图片不属于当前游戏");
      const result = await api.images.selectPortrait(image.game_id, imageId);
      if (!get().playerImages.some(current => current.game_id === image.game_id)) return;
      set((state) => ({ selectedImageId: result.image_id,
        selectedImageIndex: state.playerImages.findIndex(current => current.image_id === result.image_id),
        playerImage: state.playerImages.find(current => current.image_id === result.image_id) ?? null,
        portraitCandidates: state.portraitCandidates ? { ...state.portraitCandidates, selected_image_id: result.image_id } : null,
      }));
    },
    enqueuePortraitCandidates: async (gameId, mode) => {
      if (!gameId) throw new Error("游戏ID不存在，请先完成角色创建");
      const previousBatch = get().portraitCandidates?.batch_id;
      activePortraitJobGameId = gameId;
      clearPortraitJobPollTimer();
      set({ isGeneratingImage: true, imageGenerationError: null, portraitImageJob: null });
      let batch: PortraitCandidateState;
      try {
        batch = await api.images.enqueuePortraitCandidates(gameId, mode);
      } catch (error) {
        const recovered = await api.images.getPortraitCandidates(gameId).catch(() => null);
        if (activePortraitJobGameId !== gameId) return;
        if (!recovered || (mode === 'fresh' && recovered.batch_id === previousBatch &&
            recovered.status !== 'queued' && recovered.status !== 'running')) {
          set({ isGeneratingImage: false, imageGenerationError: getPlayerImageErrorMessage(error, "人物形象生成失败") });
          throw error;
        }
        batch = recovered;
      }
      if (activePortraitJobGameId !== gameId) return;
      set({ portraitCandidates: batch, isGeneratingImage: batch.status === 'queued' || batch.status === 'running' });
      if (batch.status === 'queued' || batch.status === 'running') {
        portraitJobPollTimer = setTimeout(() => { void get().refreshPortraitCandidates(gameId); }, PORTRAIT_JOB_POLL_INTERVAL_MS);
      } else {
        await get().loadPlayerImages(gameId);
      }
    },
    refreshPortraitCandidates: async (gameId) => {
      activePortraitJobGameId = gameId;
      clearPortraitJobPollTimer();
      await get().loadPlayerImages(gameId);
      if (activePortraitJobGameId !== gameId) return;
      const batch = get().portraitCandidates;
      const awaitingImages = batch?.slots.some(slot => slot.status === 'ready' && !get().playerImages.some(image => image.image_id === slot.image_id));
      if (batch?.status === 'queued' || batch?.status === 'running' || awaitingImages) {
        set({ isGeneratingImage: batch?.status === 'queued' || batch?.status === 'running' });
        portraitJobPollTimer = setTimeout(() => { void get().refreshPortraitCandidates(gameId); }, PORTRAIT_JOB_POLL_INTERVAL_MS);
      } else {
        set({ isGeneratingImage: false });
      }
    },
    retryMissingPortraitSlots: async (batchId) => {
      const current = get().portraitCandidates;
      if (!current || current.batch_id !== batchId) throw new Error("候选批次不存在，请刷新状态");
      activePortraitJobGameId = current.game_id;
      clearPortraitJobPollTimer();
      try {
        const batch = await api.images.retryMissingPortraitSlots(batchId);
        if (activePortraitJobGameId !== current.game_id) return;
        set({ portraitCandidates: batch, portraitImageJob: null, isGeneratingImage: true, imageGenerationError: null });
        portraitJobPollTimer = setTimeout(() => { void get().refreshPortraitCandidates(current.game_id); }, PORTRAIT_JOB_POLL_INTERVAL_MS);
      } catch (error) {
        await get().refreshPortraitCandidates(current.game_id);
        if (get().portraitCandidates?.status !== 'queued' && get().portraitCandidates?.status !== 'running') throw error;
      }
    },
    setIsGeneratingImage: (isGenerating) => set({ isGeneratingImage: isGenerating }),
    setImageFeedback: (feedback) => set({ imageFeedback: feedback }),

    generatePlayerImage: async (gameId, playerName, characterSettings, feedback) => {
      if (!gameId) {
        throw new Error("游戏ID不存在，请先完成角色创建");
      }
      if (!playerName) {
        throw new Error("请先输入角色姓名");
      }

      activePortraitJobGameId = gameId;
      clearPortraitJobPollTimer();
      set({
        isGeneratingImage: true,
        imageGenerationError: null,
        imageFeedback: feedback || "",
      });

      try {
        const era = characterSettings.era as EraSetting | undefined;
        const gender = characterSettings.gender as { gender?: string } | undefined;
        const age = characterSettings.age as { age?: number; age_range?: string } | undefined;
        const world = characterSettings.world as { cultural_context?: string; special_features?: string } | undefined;

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
          origin_revision: characterSettings.story_origin?.revision,
          playerName,
          feedback,
        };

        const job = await api.images.enqueueCharacterPortrait({
          game_id: gameId,
          image_type: "character",
          entity_name: playerName,
          description,
          entity_key: "player_main",
          era: String(eraName),
          extra_context: extraContext,
          feedback,
        });

        if (activePortraitJobGameId !== gameId) return;

        set({
          portraitImageJob: job,
          isGeneratingImage: job.status === "queued" || job.status === "running",
          imageGenerationError: null,
        });
        if (job.status === "succeeded") {
          await get().loadPlayerImages(gameId);
          set({ isGeneratingImage: false, imageFeedback: "" });
        } else if (job.status === "failed") {
          set({ isGeneratingImage: false, imageGenerationError: job.error_message || "人物形象生成失败" });
        } else {
          clearPortraitJobPollTimer();
          portraitJobPollTimer = setTimeout(() => {
            portraitJobPollTimer = null;
            void get().refreshPortraitImageJob(gameId);
          }, PORTRAIT_JOB_POLL_INTERVAL_MS);
        }
      } catch (err) {
        console.error("[generatePlayerImage] Failed:", err);
        if (activePortraitJobGameId !== gameId) return;
        await get().refreshPortraitImageJob(gameId);
        const recoveredJob = get().portraitImageJob;
        if (recoveredJob && (recoveredJob.status === "queued" || recoveredJob.status === "running" || recoveredJob.status === "succeeded")) {
          return;
        }
        set({
          isGeneratingImage: false,
          imageGenerationError: getPlayerImageErrorMessage(err, "人物形象生成失败"),
        });
        throw err;
      }
    },

    refreshPortraitImageJob: async (gameId) => {
      if (!gameId) return;

      if (get().portraitCandidates?.game_id === gameId && (!get().portraitImageJob || get().portraitImageJob?.job_id === get().portraitCandidates?.job_id)) {
        await get().refreshPortraitCandidates(gameId);
        return;
      }
      activePortraitJobGameId = gameId;
      clearPortraitJobPollTimer();
      try {
        const job = await api.images.getLatestCharacterPortraitJob(gameId);
        if (activePortraitJobGameId !== gameId) return;
        if (!job) {
          clearPortraitJobPollTimer();
          set({ portraitImageJob: null, isGeneratingImage: false });
          return;
        }

        set({ portraitImageJob: job });
        if (job.status === "succeeded") {
          clearPortraitJobPollTimer();
          await get().loadPlayerImages(gameId);
          if (activePortraitJobGameId !== gameId) return;
          if (!get().playerImages.some((image) => image.image_id === job.image_id)) {
            set({ isGeneratingImage: true, imageGenerationError: null });
            portraitJobPollTimer = setTimeout(() => {
              portraitJobPollTimer = null;
              if (activePortraitJobGameId === gameId) {
                void get().refreshPortraitImageJob(gameId);
              }
            }, PORTRAIT_JOB_POLL_INTERVAL_MS);
            return;
          }
          set({ isGeneratingImage: false, imageGenerationError: null, imageFeedback: "" });
          return;
        }
        if (job.status === "failed") {
          clearPortraitJobPollTimer();
          set({
            isGeneratingImage: false,
            imageGenerationError: job.error_message || "人物形象生成失败，请稍后重试",
          });
          return;
        }

        if (get().portraitCandidates) await get().loadPlayerImages(gameId);
        set({ isGeneratingImage: true, imageGenerationError: null });
        clearPortraitJobPollTimer();
        portraitJobPollTimer = setTimeout(() => {
          portraitJobPollTimer = null;
          if (activePortraitJobGameId === gameId) {
            void get().refreshPortraitImageJob(gameId);
          }
        }, PORTRAIT_JOB_POLL_INTERVAL_MS);
      } catch (err) {
        if (activePortraitJobGameId !== gameId) return;
        console.warn("[refreshPortraitImageJob] Unable to refresh durable job", err);
        if (get().portraitImageJob?.status === "queued" || get().portraitImageJob?.status === "running") {
          clearPortraitJobPollTimer();
          portraitJobPollTimer = setTimeout(() => {
            portraitJobPollTimer = null;
            if (activePortraitJobGameId === gameId) {
              void get().refreshPortraitImageJob(gameId);
            }
          }, PORTRAIT_JOB_POLL_INTERVAL_MS);
        }
      }
    },

    stopPortraitImagePolling: () => {
      activePortraitJobGameId = null;
      clearPortraitJobPollTimer();
    },

    regeneratePlayerImage: async (feedback) => {
      const { playerImages, selectedImageIndex } = get();
      const selectedImage = playerImages[selectedImageIndex] || playerImages[0];

      if (!selectedImage) {
        throw new Error("没有可重新生成的图片");
      }

      const gameId = selectedImage.game_id;
      if (!gameId) throw new Error("图片所属游戏不存在");
      activePortraitJobGameId = gameId;
      clearPortraitJobPollTimer();

      set({ isGeneratingImage: true, imageGenerationError: null, imageFeedback: feedback });

      try {
        const job = await api.images.enqueueCharacterRegeneration(selectedImage.image_id, feedback);
        if (activePortraitJobGameId !== gameId) return;
        set({
          portraitImageJob: job,
          isGeneratingImage: job.status === "queued" || job.status === "running",
        });
        if (job.status === "queued" || job.status === "running") {
          portraitJobPollTimer = setTimeout(() => {
            portraitJobPollTimer = null;
            void get().refreshPortraitImageJob(gameId);
          }, PORTRAIT_JOB_POLL_INTERVAL_MS);
        } else {
          await get().refreshPortraitImageJob(gameId);
        }
      } catch (err) {
        console.error("[regeneratePlayerImage] Failed:", err);
        if (activePortraitJobGameId !== gameId) return;
        const recovered = await api.images.getLatestCharacterPortraitJob(gameId).catch(() => null);
        if (recovered && (
          recovered.status === "queued" || recovered.status === "running" ||
          (recovered.status === "succeeded" && recovered.image_id !== selectedImage.image_id)
        )) {
          set({ portraitImageJob: recovered });
          await get().refreshPortraitImageJob(gameId);
          return;
        }
        set({
          isGeneratingImage: false,
          imageGenerationError: getPlayerImageErrorMessage(err, "人物形象重新生成失败"),
        });
        throw err;
      }
    },

    regenerateFreshPlayerImage: async () => {
      const selectedImage = get().playerImage ?? get().playerImages.find(image => image.image_id === get().selectedImageId) ?? get().playerImages[0];
      if (!selectedImage) throw new Error("没有可重新生成的图片");
      if (!selectedImage.game_id) throw new Error("图片所属游戏不存在");
      await get().enqueuePortraitCandidates(selectedImage.game_id, 'fresh');
    },

    loadPlayerImages: async (gameId) => {
      if (!gameId) return;
      activePortraitJobGameId = gameId;
      const selectedBefore = get().selectedImageId;
      set({ isLoadingPlayerImages: true });
      try {
        const result = await api.images.listByGame(gameId, "character");
        // A failed state request must not erase a known batch or a confirmed selection.
        const [candidateResult, selection] = await Promise.all([
          api.images.getPortraitCandidates(gameId).catch(() => undefined),
          api.images.getSelectedPortrait(gameId).catch(() => undefined),
        ]);
        if (activePortraitJobGameId !== gameId) return;
        const batch = candidateResult?.batch_id ? candidateResult : candidateResult === null ? null : get().portraitCandidates;
        const images = (result.images ?? []).filter(image => image.entity_key === "player_main" || (!image.entity_key && image.entity_name))
          .map(image => ({ ...image, game_id: gameId }));
        // A selection confirmed while these reads were in flight takes precedence.
        const selectedId = get().selectedImageId !== selectedBefore ? get().selectedImageId : selection?.image_id ?? batch?.selected_image_id ?? get().selectedImageId;
        const selected = images.find(image => image.image_id === selectedId) ??
          (selectedId == null ? images[0] : get().playerImage?.game_id === gameId ? get().playerImage : null);
        set({ playerImages: images, playerImage: selected ?? null,
          selectedImageId: selected?.image_id ?? selectedId,
          selectedImageIndex: Math.max(0, images.findIndex(image => image.image_id === selected?.image_id)),
          portraitCandidates: batch ?? null, isLoadingPlayerImages: false,
          imageGenerationError: batch?.error_message ?? null,
        });
      } catch (error) {
        if (activePortraitJobGameId !== gameId) return;
        set({ isLoadingPlayerImages: false, imageGenerationError: "暂时无法刷新人物形象，请刷新状态继续查看。" });
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
      get().stopPortraitImagePolling();
      set({
        playerImage: null,
        playerImages: [],
        selectedImageIndex: 0,
        selectedImageId: null,
        portraitCandidates: null,
        portraitImageJob: null,
        isLoadingPlayerImages: false,
        isGeneratingImage: false,
        imageGenerationError: null,
        imageFeedback: "",
        openingIllustration: null,
        isGeneratingIllustration: false,
        illustrationError: null,
      });
    },
  })
);
