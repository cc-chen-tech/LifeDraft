"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useGameStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS } from "@/stores/useGameStore";
import { useUIStore } from "@/stores/useUIStore";
import { useImageStore } from "@/stores/useImageStore";
import api from "@/lib/api";

const STEP_LABELS: Record<string, string> = {
  era: "时代背景",
  age: "年龄阶段",
  gender: "性别",
  world: "世界观",
  portrait: "人物形象",
  family: "家庭背景",
  relationships: "人际关系",
  traits: "性格特征",
  wealth: "财富状况",
};

const STEP_DESCRIPTIONS: Record<string, string> = {
  era: "选择你的人生将发生在哪个时代",
  age: "确定你人生故事开始的年龄",
  gender: "选择你的角色性别",
  world: "AI将为你构建独特的世界观",
  portrait: "AI将为你生成人物形象",
  family: "AI将为你生成家庭背景",
  relationships: "AI将为你创造关键人物关系",
  traits: "AI将基于你的设定生成性格特征",
  wealth: "AI将确定你的初始财富水平",
};

export type ToastType = { type: "success" | "error"; message: string } | null;

export interface UseCharacterCreationReturn {
  // Router
  router: ReturnType<typeof useRouter>;
  
  // Game store values
  creationStep: number;
  characterSettings: Record<string, unknown>;
  playerName: string;
  lifeVision: string;
  isPresetLoaded: boolean;
  gameId: number | null;
  
  // Game store actions
  setCreationStep: (step: number) => void;
  nextCreationStep: () => void;
  prevCreationStep: () => void;
  updateCharacterSetting: (key: string, value: unknown) => void;
  setPlayerName: (name: string) => void;
  setLifeVision: (vision: string) => void;
  resetCreation: () => void;
  setGameSession: (gameId: number, sessionId: string) => void;
  
  // Image store values
  playerImages: Array<{ image_id: number; image_url: string }>;
  selectedImageIndex: number;
  isGeneratingImage: boolean;
  imageFeedback: string;
  playerImage: { image_id: number; image_url: string } | null;
  
  // Image store actions
  setSelectedImageIndex: (index: number) => void;
  setImageFeedback: (feedback: string) => void;
  regeneratePlayerImage: (feedback: string) => Promise<void>;
  regenerateFreshPlayerImage: () => Promise<void>;
  
  // UI store
  language: string;
  
  // Local state
  isGenerating: boolean;
  feedback: string;
  setFeedback: (feedback: string) => void;
  showPresetSheet: boolean;
  setShowPresetSheet: (show: boolean) => void;
  presetName: string;
  setPresetName: (name: string) => void;
  isSavingPreset: boolean;
  generatedContent: Record<string, unknown> | null;
  toast: ToastType;
  showToast: (type: "success" | "error", message: string) => void;
  
  // Auto-gen state
  autoGenPhase: "idle" | "generating" | "done";
  setAutoGenPhase: (phase: "idle" | "generating" | "done") => void;
  autoGenLabel: string;
  autoGenProgress: string;
  showDetails: boolean;
  setShowDetails: (show: boolean) => void;
  isBackgroundGenerating: boolean;
  
  // Computed values
  currentStepKey: string;
  isManualStep: boolean;
  isFirstStep: boolean;
  isLastStep: boolean;
  isPortraitStep: boolean;
  hasBasicInfo: boolean;
  
  // Handlers
  handleGenerate: (fb?: string) => Promise<void>;
  handleRegenerate: () => void;
  regenerateSetting: (stepKey: string, feedback: string) => Promise<void>;
  handleAcceptAndNext: () => Promise<void>;
  handleSavePreset: () => Promise<void>;
  handleStartGame: () => Promise<void>;
  runAutoGeneration: () => Promise<void>;
  
  // Constants
  STEP_LABELS: Record<string, string>;
  STEP_DESCRIPTIONS: Record<string, string>;
  CREATION_STEPS: string[];
  AUTO_ADVANCE_STEPS: string[];
}

export function useCharacterCreation(): UseCharacterCreationReturn {
  const router = useRouter();
  
  const {
    creationStep,
    characterSettings,
    playerName,
    lifeVision,
    isPresetLoaded,
    setCreationStep,
    nextCreationStep,
    prevCreationStep,
    updateCharacterSetting,
    setPlayerName,
    setLifeVision,
    resetCreation,
    gameId,
    setGameSession,
  } = useGameStore();

  const {
    playerImages,
    selectedImageIndex,
    isGeneratingImage,
    imageFeedback,
    setSelectedImageIndex,
    generatePlayerImage,
    regeneratePlayerImage,
    regenerateFreshPlayerImage,
    setImageFeedback,
  } = useImageStore();

  const playerImage = playerImages[selectedImageIndex] || playerImages[0] || null;

  const { language } = useUIStore();

  const [isGenerating, setIsGenerating] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [showPresetSheet, setShowPresetSheet] = useState(false);
  const [presetName, setPresetName] = useState("");
  const [isSavingPreset, setIsSavingPreset] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<Record<string, unknown> | null>(null);
  const [toast, setToast] = useState<ToastType>(null);

  const showToast = useCallback((type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
  }, []);

  // Auto-generation batch state
  const allAutoSettingsPresent = AUTO_ADVANCE_STEPS.every(
    (step) => characterSettings[step] != null
  );
  const [autoGenPhase, setAutoGenPhase] = useState<"idle" | "generating" | "done">(
    allAutoSettingsPresent ? "done" : "idle"
  );
  const [autoGenLabel, setAutoGenLabel] = useState("");
  const [autoGenProgress, setAutoGenProgress] = useState("");
  const [showDetails, setShowDetails] = useState(false);

  const autoGenTriggeredRef = useRef<Record<string, boolean>>({});
  const backgroundGenStartedRef = useRef(false);
  const [isBackgroundGenerating, setIsBackgroundGenerating] = useState(false);

  const currentStepKey = CREATION_STEPS[creationStep];
  const isManualStep = MANUAL_STEPS.includes(currentStepKey);
  const isFirstStep = creationStep === 0;
  const isLastStep = creationStep === CREATION_STEPS.length - 1;
  const isPortraitStep = currentStepKey === "portrait";
  const hasBasicInfo = playerName.trim().length > 0;

  // Retry wrapper
  const withRetry = async <T,>(
    fn: () => Promise<T>,
    maxRetries: number = 3,
    delayMs: number = 1000
  ): Promise<T> => {
    let lastError: unknown;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;
        console.warn(`Attempt ${attempt}/${maxRetries} failed:`, err);
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, delayMs * attempt));
        }
      }
    }
    throw lastError;
  };

  const handleGenerate = useCallback(
    async (fb?: string) => {
      if (!hasBasicInfo) return;
      setIsGenerating(true);
      setGeneratedContent(null);

      try {
        const result = await withRetry(() =>
          api.character.generateSetting({
            setting_type: currentStepKey,
            player_name: playerName,
            life_vision: lifeVision,
            previous_settings: characterSettings,
            feedback: fb || null,
            language,
          })
        );
        setGeneratedContent(result);
      } catch (err) {
        console.error("Generation failed after retries:", err);
        showToast("error", "生成失败，请重试");
      } finally {
        setIsGenerating(false);
      }
    },
    [currentStepKey, playerName, lifeVision, characterSettings, language, hasBasicInfo, showToast]
  );

  // Reset autoGenTriggeredRef when navigating back to allow re-generation
  useEffect(() => {
    // When user navigates to a different step, reset the trigger for subsequent steps
    // This allows re-generation when user goes back, modifies, and then forward again
    CREATION_STEPS.forEach((step, index) => {
      if (index > creationStep) {
        autoGenTriggeredRef.current[step] = false;
      }
    });
  }, [creationStep]);

  // Auto-generate on step enter
  useEffect(() => {
    const shouldAutoGenerate = 
      !isPortraitStep &&
      hasBasicInfo && 
      !isGenerating && 
      !generatedContent && 
      characterSettings[currentStepKey] == null &&
      !autoGenTriggeredRef.current[currentStepKey];
    
    if (shouldAutoGenerate) {
      autoGenTriggeredRef.current[currentStepKey] = true;
      handleGenerate();
    }
  }, [currentStepKey, hasBasicInfo, isGenerating, generatedContent, characterSettings, isPortraitStep, handleGenerate]);

  // Portrait step auto-generate
  const hasGeneratedImage = useRef(false);
  
  useEffect(() => {
    hasGeneratedImage.current = false;
    // ★ 不再重置 backgroundGenStartedRef，因为后台生成可能在 world 步骤已提前启动
    // backgroundGenStartedRef.current = false;
    // setIsBackgroundGenerating(false);
  }, [gameId]);
  
  useEffect(() => {
    if (isPortraitStep && gameId && playerImages.length === 0 && !isGeneratingImage && !hasGeneratedImage.current) {
      console.log("[portrait] Auto-generating player image...");
      hasGeneratedImage.current = true;
      generatePlayerImage(gameId, playerName, characterSettings).catch((err) => {
        console.error("[portrait] Auto-generate failed:", err);
        hasGeneratedImage.current = false;
      });
    }
  }, [isPortraitStep, gameId, playerImages.length, isGeneratingImage, generatePlayerImage, playerName, characterSettings]);

  // Background generation for auto-advance steps
  const runAutoGeneration = useCallback(async () => {
    console.log("[runAutoGeneration] Starting background generation...");
    
    const settings = { ...useGameStore.getState().characterSettings };
    const stepsToGenerate = AUTO_ADVANCE_STEPS.filter((step) => settings[step] == null);

    if (stepsToGenerate.length === 0) {
      console.log("[runAutoGeneration] All steps already done");
      setAutoGenPhase("done");
      return;
    }

    const failedSteps: string[] = [];

    for (let i = 0; i < stepsToGenerate.length; i++) {
      const step = stepsToGenerate[i];
      console.log(`[runAutoGeneration] Generating ${step} (${i + 1}/${stepsToGenerate.length})...`);

      try {
        let result: Record<string, unknown>;

        if (step === "relationships") {
          const people: Record<string, unknown>[] = [];
          for (let pi = 0; pi < 3; pi++) {
            console.log(`[runAutoGeneration] Generating relationship person ${pi + 1}/3...`);
            const person = await withRetry(() =>
              api.character.generateRelationship({
                player_name: playerName,
                life_vision: lifeVision,
                previous_settings: settings,
                existing_people: people,
                person_index: pi,
                total_needed: 3,
                language,
              })
            );
            people.push(person);
          }
          console.log(`[runAutoGeneration] Generating relationships summary...`);
          const summaryResult = await withRetry(() =>
            api.character.generateRelationshipsSummary({
              player_name: playerName,
              life_vision: lifeVision,
              previous_settings: settings,
              key_people: people,
              language,
            })
          );
          result = {
            relationships_description: (summaryResult as Record<string, unknown>).relationships_description || "",
            key_people: people,
          };
        } else {
          result = await withRetry(() =>
            api.character.generateSetting({
              setting_type: step,
              player_name: playerName,
              life_vision: lifeVision,
              previous_settings: settings,
              language,
            })
          );
        }

        settings[step] = result;
        updateCharacterSetting(step, result);
      } catch (err) {
        console.error(`Auto-generate ${step} failed after retries:`, err);
        failedSteps.push(step);
      }
    }

    if (failedSteps.length > 0) {
      showToast("error", `部分设定生成失败(${failedSteps.map(s => STEP_LABELS[s]).join("、")})，请点击"返回修改"重试`);
    }

    setAutoGenPhase("done");
  }, [playerName, lifeVision, language, updateCharacterSetting, showToast]);

  // Start background generation on portrait step
  useEffect(() => {
    if (isPortraitStep && gameId) {
      const allDone = AUTO_ADVANCE_STEPS.every((step) => characterSettings[step] != null);

      if (allDone) {
        console.log("[portrait] All auto steps already done");
        setAutoGenPhase("done");
        backgroundGenStartedRef.current = true;
        return;
      }

      // ★ 如果后台已提前从 world 步骤启动，不自动切换 UI，保持 portrait 页面显示
      // 让用户在 portrait 步骤查看图片，点击"下一步"时再处理状态切换
      if (backgroundGenStartedRef.current) {
        console.log("[portrait] Background generation already started from world step");
        // 只在后台已完成时自动切换到 done
        if (!isBackgroundGenerating) {
          setAutoGenPhase("done");
        }
        return;
      }

      // 后台未开始，启动它（例如从 preset 加载时）
      if (!allDone) {
        console.log("[portrait] Starting background generation...");
        backgroundGenStartedRef.current = true;
        setIsBackgroundGenerating(true);
        runAutoGeneration().then(() => {
          console.log("[portrait] Background generation completed");
          setIsBackgroundGenerating(false);
        }).catch((err) => {
          console.error("[portrait] Background generation failed:", err);
          setIsBackgroundGenerating(false);
        });
      }
    }
  }, [isPortraitStep, gameId, characterSettings, isBackgroundGenerating, runAutoGeneration]);

  const handleAcceptAndNext = useCallback(async () => {
    if (!isPortraitStep && generatedContent) {
      updateCharacterSetting(currentStepKey, generatedContent);
    }
    setGeneratedContent(null);
    setFeedback("");
    
    if (currentStepKey === "world" && !gameId) {
      try {
        setIsGenerating(true);
        const result = await api.games.create({
          character_settings: characterSettings,
          player_name: playerName,
          life_vision: lifeVision,
          language,
        });
        console.log("[create] Game created for portrait step:", result.game_id);
        setGameSession(result.game_id, result.game_id.toString());

        // ★ 提前启动后台生成，与图片生成并行
        const allDone = AUTO_ADVANCE_STEPS.every((step) => characterSettings[step] != null);
        if (!allDone && !backgroundGenStartedRef.current) {
          console.log("[world] Starting background generation early...");
          backgroundGenStartedRef.current = true;
          setIsBackgroundGenerating(true);
          runAutoGeneration().then(() => {
            console.log("[world] Background generation completed");
            setIsBackgroundGenerating(false);
          }).catch((err) => {
            console.error("[world] Background generation failed:", err);
            setIsBackgroundGenerating(false);
          });
        }

        nextCreationStep();
      } catch (err) {
        console.error("[create] Failed to create game for portrait:", err);
        showToast("error", "创建游戏失败，请重试");
      } finally {
        setIsGenerating(false);
      }
      return;
    }
    
    if (isPortraitStep) {
      const currentSettings = useGameStore.getState().characterSettings;
      const allDone = AUTO_ADVANCE_STEPS.every((step) => currentSettings[step] != null);
      
      if (allDone) {
        console.log("[portrait] All background generation done, proceeding to done phase");
        setAutoGenPhase("done");
      } else if (isBackgroundGenerating) {
        console.log("[portrait] Background generation still in progress, showing loading...");
        setAutoGenPhase("generating");
        setAutoGenLabel("剩余角色背景");
        
        const checkInterval = setInterval(() => {
          const settings = useGameStore.getState().characterSettings;
          const done = AUTO_ADVANCE_STEPS.every((step) => settings[step] != null);
          if (done) {
            console.log("[portrait] Background generation completed during wait");
            clearInterval(checkInterval);
            setAutoGenPhase("done");
          }
        }, 500);
        
        setTimeout(() => {
          clearInterval(checkInterval);
          const settings = useGameStore.getState().characterSettings;
          const stillNotDone = AUTO_ADVANCE_STEPS.filter((step) => settings[step] == null);
          if (stillNotDone.length > 0) {
            console.error("[portrait] Background generation timeout, missing:", stillNotDone);
            setAutoGenPhase("done");
          }
        }, 60000);
      } else {
        console.warn("[portrait] Background generation not started, starting now...");
        runAutoGeneration();
      }
    } else if (isLastStep) {
      const currentSettings = useGameStore.getState().characterSettings;
      const allDone = AUTO_ADVANCE_STEPS.every((step) => currentSettings[step] != null);
      if (allDone) {
        setAutoGenPhase("done");
      } else {
        runAutoGeneration();
      }
    } else {
      nextCreationStep();
    }
  }, [
    isPortraitStep, generatedContent, currentStepKey, gameId, characterSettings,
    playerName, lifeVision, language, isLastStep, isBackgroundGenerating,
    updateCharacterSetting, setGameSession, nextCreationStep, showToast, runAutoGeneration
  ]);

  const handleRegenerate = useCallback(() => {
    handleGenerate(feedback || undefined);
    setFeedback("");
  }, [handleGenerate, feedback]);

  // Wrapper for prevCreationStep that clears subsequent settings
  const handlePrevStep = useCallback(() => {
    // Clear settings for all subsequent steps (including current) to force re-generation when going forward again
    // When user goes back from step N to step N-1, steps N, N+1, N+2... should all be cleared
    const targetStepIndex = creationStep - 1;
    CREATION_STEPS.forEach((step, index) => {
      if (index > targetStepIndex && characterSettings[step] != null) {
        updateCharacterSetting(step, null);
      }
    });
    // Clear generatedContent to prevent displaying stale content with wrong stepKey
    setGeneratedContent(null);
    setFeedback("");
    prevCreationStep();
  }, [creationStep, characterSettings, updateCharacterSetting, prevCreationStep]);

  const regenerateSetting = useCallback(async (stepKey: string, feedback: string) => {
    if (!gameId) {
      console.error("[regenerateSetting] No gameId available");
      throw new Error("游戏未创建");
    }

    setIsGenerating(true);
    try {
      console.log(`[regenerateSetting] Regenerating ${stepKey} with feedback:`, feedback);

      const result = await api.character.generateSetting({
        setting_type: stepKey,
        player_name: playerName,
        life_vision: lifeVision,
        previous_settings: characterSettings,
        language,
        feedback: feedback || null,
      });

      // Update characterSettings with the regenerated content
      updateCharacterSetting(stepKey, result);
      console.log(`[regenerateSetting] ${stepKey} regenerated successfully`);
    } catch (err) {
      console.error(`[regenerateSetting] Failed to regenerate ${stepKey}:`, err);
      throw err;
    } finally {
      setIsGenerating(false);
    }
  }, [gameId, playerName, lifeVision, characterSettings, language, updateCharacterSetting]);

  const handleSavePreset = useCallback(async () => {
    if (!presetName.trim()) return;
    setIsSavingPreset(true);
    try {
      await api.presets.create({
        preset_name: presetName.trim(),
        player_name: playerName,
        life_vision: lifeVision,
        character_settings: characterSettings,
      });
      setShowPresetSheet(false);
      setPresetName("");
      showToast("success", "预设保存成功");
    } catch (err) {
      console.error("Save preset failed:", err);
      showToast("error", "保存失败，请重试");
    } finally {
      setIsSavingPreset(false);
    }
  }, [presetName, playerName, lifeVision, characterSettings, showToast]);

  const handleStartGame = useCallback(async () => {
    if (isGenerating) {
      console.warn("[create] Already generating, ignoring click");
      return;
    }
    
    if (!playerName.trim()) {
      showToast("error", "请先输入角色姓名");
      return;
    }
    
    setIsGenerating(true);
    
    try {
      console.log("[create] Starting game creation...");
      
      const autoPresetName = `${playerName}_${new Date().toLocaleDateString("zh-CN").replace(/\//g, "-")}`;
      try {
        await api.presets.create({
          preset_name: autoPresetName,
          player_name: playerName,
          life_vision: lifeVision,
          character_settings: characterSettings,
        });
        console.log("[create] Auto-preset saved:", autoPresetName);
      } catch (saveErr) {
        console.warn("Auto-save preset failed (non-blocking):", saveErr);
      }

      if (gameId) {
        console.log("[create] Game already exists:", gameId);
        // Persist complete character_settings before starting
        try {
          await api.games.updateCharacterSettings(gameId, {
            character_settings: characterSettings,
          });
          console.log("[create] Character settings updated for game:", gameId);
        } catch (updateErr) {
          console.warn("[create] Failed to update character settings (non-blocking):", updateErr);
        }
        console.log("[create] Navigating to opening story...");
        router.push("/story/opening");
        return;
      }

      const result = await api.games.create({
        character_settings: characterSettings,
        player_name: playerName,
        life_vision: lifeVision,
        language,
      });
      
      console.log("[create] Game created:", result.game_id);
      useGameStore.getState().setGameSession(result.game_id, result.game_id.toString());
      
      await new Promise(resolve => setTimeout(resolve, 100));
      
      console.log("[create] Navigating to opening story...");
      router.push("/story/opening");
    } catch (err) {
      console.error("[create] Start game failed:", err);
      showToast("error", "创建游戏失败，请重试");
    } finally {
      setIsGenerating(false);
    }
  }, [isGenerating, playerName, lifeVision, characterSettings, gameId, language, router, showToast]);

  return {
    // Router
    router,
    
    // Game store values
    creationStep,
    characterSettings,
    playerName,
    lifeVision,
    isPresetLoaded,
    gameId,
    
    // Game store actions
    setCreationStep,
    nextCreationStep,
    prevCreationStep: handlePrevStep,
    updateCharacterSetting,
    setPlayerName,
    setLifeVision,
    resetCreation,
    setGameSession,
    
    // Image store values
    playerImages,
    selectedImageIndex,
    isGeneratingImage,
    imageFeedback,
    playerImage,
    
    // Image store actions
    setSelectedImageIndex,
    setImageFeedback,
    regeneratePlayerImage,
    regenerateFreshPlayerImage,
    
    // UI store
    language,
    
    // Local state
    isGenerating,
    feedback,
    setFeedback,
    showPresetSheet,
    setShowPresetSheet,
    presetName,
    setPresetName,
    isSavingPreset,
    generatedContent,
    toast,
    showToast,
    
    // Auto-gen state
    autoGenPhase,
    setAutoGenPhase,
    autoGenLabel,
    autoGenProgress,
    showDetails,
    setShowDetails,
    isBackgroundGenerating,
    
    // Computed values
    currentStepKey,
    isManualStep,
    isFirstStep,
    isLastStep,
    isPortraitStep,
    hasBasicInfo,
    
    // Handlers
    handleGenerate,
    handleRegenerate,
    regenerateSetting,
    handleAcceptAndNext,
    handleSavePreset,
    handleStartGame,
    runAutoGeneration,
    
    // Constants
    STEP_LABELS,
    STEP_DESCRIPTIONS,
    CREATION_STEPS,
    AUTO_ADVANCE_STEPS,
  };
}
