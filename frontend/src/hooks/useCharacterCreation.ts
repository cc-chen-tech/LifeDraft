"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useGameStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS } from "@/stores/useGameStore";
import { useUIStore } from "@/stores/useUIStore";
import { useImageStore } from "@/stores/useImageStore";
import type { CharacterSettings } from "@/lib/types";
import api from "@/lib/api";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit, unicodeCharacterLength } from "@/lib/inputLimits";

const STEP_LABELS: Record<string, string> = {
  era: "时代背景",
  age: "年龄阶段",
  gender: "性别",
  world: "世界观",
  portrait: "人物形象",
  family: "家庭背景",
  relationships: "人际关系",
  traits: "性格特征",
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
};

type RelationshipPerson = Record<string, unknown> & {
  name: string;
  role: string;
  relationship: string;
};

type RelationshipCandidate = {
  relationships_description: string;
  key_people: RelationshipPerson[];
};

const RELATIONSHIP_RESULT_ERROR = "人际关系生成结果不完整，已保留原设定";
const RELATIONSHIP_REQUEST_ERROR = "人际关系重新生成失败，已保留原设定，请重试";

function nonEmptyText(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : null;
}

function validateRelationshipPerson(value: unknown): RelationshipPerson {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(RELATIONSHIP_RESULT_ERROR);
  }
  const record = value as Record<string, unknown>;
  const name = nonEmptyText(record.name);
  const role = nonEmptyText(record.role);
  const relationship =
    nonEmptyText(record.relationship) ?? nonEmptyText(record.relationship_desc);
  if (!name || !role || !relationship) {
    throw new Error(RELATIONSHIP_RESULT_ERROR);
  }
  return {
    ...record,
    name,
    role,
    relationship,
  };
}

function validateRelationshipCandidate(
  people: RelationshipPerson[],
  summary: unknown,
  expectedCount: number,
): RelationshipCandidate {
  const relationshipsDescription = nonEmptyText(summary);
  const uniqueNames = new Set(
    people.map((person) => person.name.toLocaleLowerCase()),
  );
  if (
    people.length !== expectedCount ||
    uniqueNames.size !== expectedCount ||
    !relationshipsDescription
  ) {
    throw new Error(RELATIONSHIP_RESULT_ERROR);
  }
  return {
    relationships_description: relationshipsDescription,
    key_people: people,
  };
}

export type ToastType = { type: "success" | "error"; message: string } | null;
export type PresetSaveStatus = "idle" | "saving" | "error";

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
  imageGenerationError: string | null;
  imageFeedback: string;
  playerImage: { image_id: number; image_url: string } | null;
  
  // Image store actions
  setSelectedImageIndex: (index: number) => void;
  setImageFeedback: (feedback: string) => void;
  generatePlayerImage: (
    gameId: number,
    playerName: string,
    characterSettings: CharacterSettings,
    feedback?: string
  ) => Promise<void>;
  refreshPortraitImageJob: (gameId: number) => Promise<void>;
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
  presetSaveStatus: PresetSaveStatus;
  presetSaveMessage: string;
  generatedContent: Record<string, unknown> | null;
  toast: ToastType;
  showToast: (type: "success" | "error", message: string) => void;
  
  // Auto-gen state
  autoGenPhase: "idle" | "generating" | "done";
  setAutoGenPhase: (phase: "idle" | "generating" | "done") => void;
  autoGenLabel: string;
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
    setPlayerName: storeSetPlayerName,
    setLifeVision: storeSetLifeVision,
    resetCreation,
    gameId,
    setGameSession,
  } = useGameStore();

  const {
    playerImages,
    selectedImageIndex,
    isGeneratingImage,
    imageGenerationError,
    imageFeedback,
    setSelectedImageIndex,
    generatePlayerImage,
    refreshPortraitImageJob,
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
  const [presetSaveStatus, setPresetSaveStatus] = useState<PresetSaveStatus>("idle");
  const [presetSaveMessage, setPresetSaveMessage] = useState("");
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
  const [showDetails, setShowDetails] = useState(false);

  const autoGenTriggeredRef = useRef<Record<string, boolean>>({});
  const basicInfoVersionRef = useRef(0);
  const backgroundGenStartedRef = useRef(false);
  const [isBackgroundGenerating, setIsBackgroundGenerating] = useState(false);

  const currentStepKey = CREATION_STEPS[creationStep];
  const isManualStep = MANUAL_STEPS.includes(currentStepKey);
  const isFirstStep = creationStep === 0;
  const isLastStep = creationStep === CREATION_STEPS.length - 1;
  const isPortraitStep = currentStepKey === "portrait";
  const hasBasicInfo =
    playerName.trim().length > 0 &&
    isWithinInputLimit(playerName, INPUT_LIMITS.name) &&
    isWithinInputLimit(lifeVision, INPUT_LIMITS.lifeVision);

  const invalidateEraGeneration = useCallback(() => {
    basicInfoVersionRef.current += 1;
    if (currentStepKey !== "era") return;
    autoGenTriggeredRef.current[currentStepKey] = false;
    setGeneratedContent(null);
  }, [currentStepKey]);

  const setPlayerName = useCallback(
    (name: string) => {
      invalidateEraGeneration();
      storeSetPlayerName(name);
    },
    [invalidateEraGeneration, storeSetPlayerName]
  );

  const setLifeVision = useCallback(
    (vision: string) => {
      invalidateEraGeneration();
      storeSetLifeVision(vision);
    },
    [invalidateEraGeneration, storeSetLifeVision]
  );

  const handleSetPresetName = useCallback((name: string) => {
    setPresetName(name);
    if (presetSaveStatus === "error") {
      setPresetSaveStatus("idle");
      setPresetSaveMessage("");
    }
  }, [presetSaveStatus]);

  const handleSetShowPresetSheet = useCallback((show: boolean) => {
    setShowPresetSheet(show);
    if (!show) {
      setPresetSaveStatus("idle");
      setPresetSaveMessage("");
    }
  }, []);

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
        if ((err as { status?: number } | null)?.status === 422) {
          throw err;
        }
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, delayMs * attempt));
        }
      }
    }
    throw lastError;
  };

  const handleGenerate = useCallback(
    async (fb?: string) => {
      if (
        !hasBasicInfo ||
        (fb != null && !isWithinInputLimit(fb, INPUT_LIMITS.feedback))
      ) return;
      const requestInput = { currentStepKey, playerName, lifeVision };
      const requestBasicInfoVersion = basicInfoVersionRef.current;
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
        const latestState = useGameStore.getState();
        const latestInput = {
          currentStepKey: CREATION_STEPS[latestState.creationStep],
          playerName: latestState.playerName,
          lifeVision: latestState.lifeVision,
        };
        if (
          requestBasicInfoVersion !== basicInfoVersionRef.current ||
          latestInput.currentStepKey !== requestInput.currentStepKey ||
          latestInput.playerName !== requestInput.playerName ||
          latestInput.lifeVision !== requestInput.lifeVision
        ) {
          return;
        }
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

  useEffect(() => {
    if (currentStepKey !== "era") return;
    autoGenTriggeredRef.current[currentStepKey] = false;
    setGeneratedContent(null);
  }, [currentStepKey, playerName, lifeVision]);

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
    if (
      isPortraitStep &&
      gameId &&
      hasBasicInfo &&
      playerImages.length === 0 &&
      !isGeneratingImage &&
      !imageGenerationError &&
      !hasGeneratedImage.current
    ) {
      console.log("[portrait] Auto-generating player image...");
      hasGeneratedImage.current = true;
      generatePlayerImage(gameId, playerName, characterSettings).catch((err) => {
        console.error("[portrait] Auto-generate failed:", err);
      });
    }
  }, [
    isPortraitStep,
    gameId,
    playerImages.length,
    isGeneratingImage,
    imageGenerationError,
    generatePlayerImage,
    playerName,
    characterSettings,
    hasBasicInfo,
  ]);

  // Background generation for auto-advance steps
  const runAutoGeneration = useCallback(async () => {
    if (!hasBasicInfo) {
      showToast("error", "角色姓名或人生愿景超过允许长度，请修改后重试");
      return;
    }
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
      setAutoGenLabel(STEP_LABELS[step] ?? "剩余角色背景");

      try {
        let result: Record<string, unknown>;

        if (step === "relationships") {
          const people: Record<string, unknown>[] = [];
          for (let pi = 0; pi < 3; pi++) {
            console.log(`[runAutoGeneration] Generating relationship person ${pi + 1}/3...`);
            setAutoGenLabel("生成关键人物");
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
          setAutoGenLabel("整理人际关系");
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
  }, [playerName, lifeVision, language, updateCharacterSetting, showToast, hasBasicInfo]);

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
    if (!hasBasicInfo) {
      showToast("error", "角色姓名或人生愿景超过允许长度，请修改后重试");
      return;
    }
    let acceptedCharacterSettings = characterSettings;
    if (!isPortraitStep && generatedContent) {
      acceptedCharacterSettings = {
        ...characterSettings,
        [currentStepKey]: generatedContent,
      };
      updateCharacterSetting(currentStepKey, generatedContent);
    }
    setGeneratedContent(null);
    setFeedback("");
    
    if (currentStepKey === "world" && !gameId) {
      try {
        setIsGenerating(true);
        const result = await api.games.create({
          character_settings: acceptedCharacterSettings,
          player_name: playerName,
          life_vision: lifeVision,
          language,
        });
        console.log("[create] Game created for portrait step:", result.game_id);
        setGameSession(result.game_id, result.game_id.toString());

        // ★ 提前启动后台生成，与图片生成并行
        const allDone = AUTO_ADVANCE_STEPS.every((step) => acceptedCharacterSettings[step] != null);
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
        setAutoGenLabel((currentLabel) => currentLabel || "剩余角色背景");
        
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
    updateCharacterSetting, setGameSession, nextCreationStep, showToast, runAutoGeneration,
    hasBasicInfo
  ]);

  const handleRegenerate = useCallback(() => {
    if (!isWithinInputLimit(feedback, INPUT_LIMITS.feedback)) return;
    handleGenerate(feedback || undefined);
    setFeedback("");
  }, [handleGenerate, feedback]);

  // Wrapper for prevCreationStep that clears subsequent settings
  const handlePrevStep = useCallback(() => {
    // Clear settings for steps AFTER the current one (not including current).
    // When user goes back from step N to step N-1, only steps N+1, N+2... are cleared.
    // The current step N is preserved so returning forward does not force re-generation.
    CREATION_STEPS.forEach((step, index) => {
      if (index > creationStep && characterSettings[step] != null) {
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
    if (
      !hasBasicInfo ||
      !isWithinInputLimit(feedback, INPUT_LIMITS.feedback)
    ) {
      throw new Error("输入内容超过允许长度，请缩短后重试");
    }

    setIsGenerating(true);
    try {
      console.log(`[regenerateSetting] Regenerating ${stepKey}`);

      if (stepKey === "relationships") {
        const relationshipState = characterSettings.relationships;
        const rawExistingPeople =
          relationshipState &&
          typeof relationshipState === "object" &&
          !Array.isArray(relationshipState)
            ? (relationshipState as Record<string, unknown>).key_people
            : undefined;
        const existingPeople = Array.isArray(rawExistingPeople)
          ? rawExistingPeople
          : [];
        const totalNeeded = existingPeople.length > 0 ? existingPeople.length : 3;
        const candidatePeople: RelationshipPerson[] = [];

        for (let personIndex = 0; personIndex < totalNeeded; personIndex += 1) {
          const generatedPerson = await api.character.generateRelationship({
            player_name: playerName,
            life_vision: lifeVision,
            previous_settings: characterSettings,
            existing_people: candidatePeople,
            person_index: personIndex,
            total_needed: totalNeeded,
            feedback: feedback || null,
            language,
          });
          candidatePeople.push(validateRelationshipPerson(generatedPerson));
        }

        const summaryResult = await api.character.generateRelationshipsSummary({
          player_name: playerName,
          life_vision: lifeVision,
          previous_settings: characterSettings,
          key_people: candidatePeople,
          language,
        });
        const candidate = validateRelationshipCandidate(
          candidatePeople,
          summaryResult.relationships_description,
          totalNeeded,
        );

        await api.games.patchCharacterSettings(gameId, {
          relationships: candidate,
        });
        updateCharacterSetting(stepKey, candidate);
        console.log("[regenerateSetting] relationships committed successfully");
        return;
      }

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
      if (
        stepKey === "relationships" &&
        (!(err instanceof Error) || !err.message.startsWith("人际关系"))
      ) {
        throw new Error(RELATIONSHIP_REQUEST_ERROR);
      }
      throw err;
    } finally {
      setIsGenerating(false);
    }
  }, [gameId, playerName, lifeVision, characterSettings, language, updateCharacterSetting, hasBasicInfo]);

  const handleSavePreset = useCallback(async () => {
    if (
      !presetName.trim() ||
      !isWithinInputLimit(presetName, INPUT_LIMITS.name) ||
      !hasBasicInfo
    ) return;
    setIsSavingPreset(true);
    setPresetSaveStatus("saving");
    setPresetSaveMessage("正在保存角色预设...");
    try {
      await api.presets.create({
        preset_name: presetName.trim(),
        player_name: playerName,
        life_vision: lifeVision,
        character_settings: characterSettings,
      });
      handleSetShowPresetSheet(false);
      setPresetName("");
      setPresetSaveStatus("idle");
      setPresetSaveMessage("");
      showToast("success", "预设保存成功");
    } catch (err) {
      console.error("Save preset failed:", err);
      setPresetSaveStatus("error");
      setPresetSaveMessage("保存失败，预设未保存，请重试。");
      showToast("error", "保存失败，请重试");
    } finally {
      setIsSavingPreset(false);
    }
  }, [presetName, playerName, lifeVision, characterSettings, handleSetShowPresetSheet, showToast, hasBasicInfo]);

  const handleStartGame = useCallback(async () => {
    if (isGenerating) {
      console.warn("[create] Already generating, ignoring click");
      return;
    }
    
    if (!playerName.trim()) {
      showToast("error", "请先输入角色姓名");
      return;
    }

    if (!hasBasicInfo) {
      showToast("error", "角色姓名或人生愿景超过允许长度，请修改后重试");
      return;
    }
    
    setIsGenerating(true);
    
    try {
      console.log("[create] Starting game creation...");
      
      const presetSuffix = `_${new Date().toLocaleDateString("zh-CN").replace(/\//g, "-")}`;
      const autoPresetName =
        unicodeCharacterLength(playerName) + unicodeCharacterLength(presetSuffix) <= INPUT_LIMITS.name
          ? `${playerName}${presetSuffix}`
          : playerName;
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
        // Persist auto-generated character settings back to the server
        try {
          await api.games.patchCharacterSettings(gameId, characterSettings, {
            player_name: playerName.trim(),
            life_vision: lifeVision,
          });
          console.log("[create] Character settings patched successfully");
        } catch (patchErr) {
          console.warn("[create] Failed to patch character settings (non-blocking):", patchErr);
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
  }, [isGenerating, playerName, lifeVision, characterSettings, gameId, language, router, showToast, hasBasicInfo]);

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
    imageGenerationError,
    imageFeedback,
    playerImage,
    
    // Image store actions
    setSelectedImageIndex,
    setImageFeedback,
    generatePlayerImage,
    refreshPortraitImageJob,
    regeneratePlayerImage,
    regenerateFreshPlayerImage,
    
    // UI store
    language,
    
    // Local state
    isGenerating,
    feedback,
    setFeedback,
    showPresetSheet,
    setShowPresetSheet: handleSetShowPresetSheet,
    presetName,
    setPresetName: handleSetPresetName,
    isSavingPreset,
    presetSaveStatus,
    presetSaveMessage,
    generatedContent,
    toast,
    showToast,
    
    // Auto-gen state
    autoGenPhase,
    setAutoGenPhase,
    autoGenLabel,
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
