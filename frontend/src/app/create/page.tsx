"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { SkeletonStory } from "@/components/game/SkeletonStory";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { useGameStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS } from "@/stores/useGameStore";
import { useUIStore } from "@/stores/useUIStore";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  RotateCcw,
  Loader2,
  Save,
  Play,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Eye,
} from "lucide-react";

const STEP_LABELS: Record<string, string> = {
  era: "时代背景",
  age: "年龄阶段",
  gender: "性别",
  world: "世界观",
  portrait: "人物形象",  // ★ 新增
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
  portrait: "AI将为你生成人物形象",  // ★ 新增
  family: "AI将为你生成家庭背景",
  relationships: "AI将为你创造关键人物关系",
  traits: "AI将基于你的设定生成性格特征",
  wealth: "AI将确定你的初始财富水平",
};

export default function CreatePage() {
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
    // ★ 图片相关
    playerImages,
    selectedImageIndex,
    isGeneratingImage,
    imageFeedback,
    setPlayerImage,
    setSelectedImageIndex,
    generatePlayerImage,
    regeneratePlayerImage,
    regenerateFreshPlayerImage,  // ★ 完全重新生成
    setImageFeedback,
    gameId,
    setGameSession,
  } = useGameStore();

  // ★ 兼容旧代码，playerImage 是当前选中的图片
  const playerImage = playerImages[selectedImageIndex] || playerImages[0] || null;

  const { language } = useUIStore();

  const [isGenerating, setIsGenerating] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [showPresetSheet, setShowPresetSheet] = useState(false);
  const [presetName, setPresetName] = useState("");
  const [isSavingPreset, setIsSavingPreset] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<Record<string, unknown> | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
  };

  // Auto-generation batch state (steps 5-8)
  // If all auto-advance settings are already populated (e.g., from preset load),
  // start directly in "done" phase to show summary screen.
  const allAutoSettingsPresent = AUTO_ADVANCE_STEPS.every(
    (step) => characterSettings[step] != null
  );
  const [autoGenPhase, setAutoGenPhase] = useState<"idle" | "generating" | "done">(
    allAutoSettingsPresent ? "done" : "idle"
  );
  const [autoGenLabel, setAutoGenLabel] = useState("");
  const [autoGenProgress, setAutoGenProgress] = useState("");
  const [showDetails, setShowDetails] = useState(false);

  // Ref to track which step has already triggered auto-generation (prevents double-trigger)
  const autoGenTriggeredRef = useRef<Record<string, boolean>>({});
  
  // ★ 后台生成状态：用于 portrait 步骤并行生成 family/relationships/traits/wealth
  const backgroundGenStartedRef = useRef(false);  // 是否已启动后台生成
  const [isBackgroundGenerating, setIsBackgroundGenerating] = useState(false);  // 后台是否正在生成

  const currentStepKey = CREATION_STEPS[creationStep];
  const isManualStep = MANUAL_STEPS.includes(currentStepKey);
  // ★ 所有步骤都是手动步骤，portrait 是最后一个
  const isFirstStep = creationStep === 0;
  const isLastStep = creationStep === CREATION_STEPS.length - 1;  // portrait 是最后一步
  // ★ portrait 步骤特殊处理
  const isPortraitStep = currentStepKey === "portrait";

  // Check prerequisites
  const hasBasicInfo = playerName.trim().length > 0;

  // ★ 进入新步骤时自动生成（如果还没有数据）
  // 只对 era, age, gender, world 自动生成 setting
  // portrait 步骤是图片生成，不走 setting 生成逻辑
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStepKey, hasBasicInfo, isGenerating, generatedContent, characterSettings]);

  // ★ portrait 步骤自动生成图片
  const hasGeneratedImage = useRef(false);  // ★ 防止重复生成
  
  // ★ 当 gameId 变化时重置标记
  useEffect(() => {
    hasGeneratedImage.current = false;
    backgroundGenStartedRef.current = false;  // ★ 重置后台生成标记
    setIsBackgroundGenerating(false);
  }, [gameId]);
  
  useEffect(() => {
    if (isPortraitStep && gameId && playerImages.length === 0 && !isGeneratingImage && !hasGeneratedImage.current) {
      console.log("[portrait] Auto-generating player image...");
      hasGeneratedImage.current = true;  // ★ 标记已生成
      generatePlayerImage().catch((err) => {
        console.error("[portrait] Auto-generate failed:", err);
        hasGeneratedImage.current = false;  // ★ 失败时重置
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPortraitStep, gameId, playerImages.length, isGeneratingImage]);
  
  // ★ 进入 portrait 步骤时，并行启动后台生成 family/relationships/traits/wealth
  useEffect(() => {
    if (isPortraitStep && gameId && !backgroundGenStartedRef.current) {
      // 检查是否所有自动步骤都已完成（可能来自预设）
      const allDone = AUTO_ADVANCE_STEPS.every((step) => characterSettings[step] != null);
      if (!allDone) {
        console.log("[portrait] Starting background generation for family/relationships/traits/wealth...");
        backgroundGenStartedRef.current = true;
        setIsBackgroundGenerating(true);
        
        // 启动后台生成（不阻塞 UI）
        runAutoGeneration().then(() => {
          console.log("[portrait] Background generation completed");
          setIsBackgroundGenerating(false);
        }).catch((err) => {
          console.error("[portrait] Background generation failed:", err);
          setIsBackgroundGenerating(false);
        });
      } else {
        console.log("[portrait] All auto steps already done (from preset)");
        backgroundGenStartedRef.current = true;  // 标记为已处理
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPortraitStep, gameId, characterSettings]);

  // Auto-generate for non-manual steps
  // Helper: retry wrapper for single API calls
  const withRetrySingle = async <T,>(
    fn: () => Promise<T>,
    maxRetries: number = 3
  ): Promise<T> => {
    let lastError: unknown;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;
        console.warn(`[handleGenerate] Attempt ${attempt}/${maxRetries} failed:`, err);
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, 1000 * attempt));
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
        // ★ 只处理 era, age, gender, world 步骤的设定生成
        const result = await withRetrySingle(() =>
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
    [currentStepKey, playerName, lifeVision, characterSettings, language, hasBasicInfo]
  );

  // ==================== Batch auto-generation (runs in background during portrait step) ====================
  // Helper: retry wrapper for API calls
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
          await new Promise((r) => setTimeout(r, delayMs * attempt)); // 递增延迟
        }
      }
    }
    throw lastError;
  };

  // ★ 后台生成：完全静默进行，不显示加载页面
  const runAutoGeneration = useCallback(async () => {
    // ★ 不设置 setAutoGenPhase("generating")，保持静默
    console.log("[runAutoGeneration] Starting background generation...");
    
    // Use a mutable copy of settings so each step sees previous results
    const settings = { ...useGameStore.getState().characterSettings };

    // Only generate steps that don't already have data (preset data is preserved)
    const stepsToGenerate = AUTO_ADVANCE_STEPS.filter((step) => settings[step] == null);

    if (stepsToGenerate.length === 0) {
      console.log("[runAutoGeneration] All steps already done");
      setAutoGenPhase("done");
      return;
    }

    const failedSteps: string[] = [];

    for (let i = 0; i < stepsToGenerate.length; i++) {
      const step = stepsToGenerate[i];
      // ★ 只在控制台输出进度，不更新 UI
      console.log(`[runAutoGeneration] Generating ${step} (${i + 1}/${stepsToGenerate.length})...`);

      try {
        let result: Record<string, unknown>;

        if (step === "relationships") {
          // Generate 3 people one by one + summary
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
          // Generate summary
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
        // Continue with next step even if one fails
      }
    }

    // If some steps failed, show warning but still proceed
    if (failedSteps.length > 0) {
      showToast("error", `部分设定生成失败(${failedSteps.map(s => STEP_LABELS[s]).join("、")})，请点击“返回修改”重试`);
    }

    setAutoGenPhase("done");
  }, [playerName, lifeVision, language, updateCharacterSetting]);

  const handleAcceptAndNext = async () => {
    // 非 portrait 步骤，保存生成的 setting
    if (!isPortraitStep && generatedContent) {
      updateCharacterSetting(currentStepKey, generatedContent);
    }
    setGeneratedContent(null);
    setFeedback("");
    
    // ★ 如果当前是 world 步骤，先创建游戏获取 gameId
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
        // ★ 直接进入 portrait 步骤，不需要等待状态更新
        // 因为 generatePlayerImage 会从 store 获取最新的 gameId
        nextCreationStep();
      } catch (err) {
        console.error("[create] Failed to create game for portrait:", err);
        showToast("error", "创建游戏失败，请重试");
      } finally {
        setIsGenerating(false);
      }
      return;  // ★ 提前返回，上面的 nextCreationStep 已经处理了步骤切换
    }
    
    // ★ portrait 步骤是最后一个交互步骤，完成后检查后台生成状态
    if (isPortraitStep) {
      // 检查后台生成是否已完成
      const currentSettings = useGameStore.getState().characterSettings;
      const allDone = AUTO_ADVANCE_STEPS.every((step) => currentSettings[step] != null);
      
      if (allDone) {
        // 后台生成已完成（可能来自预设，或刚好完成）
        console.log("[portrait] All background generation done, proceeding to done phase");
        setAutoGenPhase("done");
      } else if (isBackgroundGenerating) {
        // 后台生成还在进行，显示加载页面等待
        console.log("[portrait] Background generation still in progress, showing loading...");
        setAutoGenPhase("generating");
        // 设置一个提示信息
        setAutoGenLabel("剩余角色背景");
        
        // 等待后台生成完成
        const checkInterval = setInterval(() => {
          const settings = useGameStore.getState().characterSettings;
          const done = AUTO_ADVANCE_STEPS.every((step) => settings[step] != null);
          if (done) {
            console.log("[portrait] Background generation completed during wait");
            clearInterval(checkInterval);
            setAutoGenPhase("done");
          }
        }, 500);
        
        // 最多等待 60 秒后超时
        setTimeout(() => {
          clearInterval(checkInterval);
          const settings = useGameStore.getState().characterSettings;
          const stillNotDone = AUTO_ADVANCE_STEPS.filter((step) => settings[step] == null);
          if (stillNotDone.length > 0) {
            console.error("[portrait] Background generation timeout, missing:", stillNotDone);
            // 即使超时也进入 done 页面，让用户可以手动重试
            setAutoGenPhase("done");
          }
        }, 60000);
      } else {
        // 后台生成未启动（异常情况），重新启动
        console.warn("[portrait] Background generation not started, starting now...");
        runAutoGeneration();
      }
    } else if (isLastStep) {
      // 其他最后一个步骤（不应该到达这里，因为 portrait 是最后一个）
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
  };

  const handleRegenerate = () => {
    handleGenerate(feedback || undefined);
    setFeedback("");
  };

  const handleSavePreset = async () => {
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
  };

  const handleStartGame = async () => {
    // ★ 防止重复点击
    if (isGenerating) {
      console.warn("[create] Already generating, ignoring click");
      return;
    }
    
    // ★ 验证必填字段
    if (!playerName.trim()) {
      showToast("error", "请先输入角色姓名");
      return;
    }
    
    setIsGenerating(true);
    
    try {
      console.log("[create] Starting game creation...");
      
      // 自动保存角色设定（使用玩家名字作为预设名称）
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
        // 保存预设失败不影响游戏开始，只记录日志
        console.warn("Auto-save preset failed (non-blocking):", saveErr);
      }

      // ★ 如果已经有 gameId（在 portrait 步骤创建），直接跳转
      if (gameId) {
        console.log("[create] Game already exists:", gameId);
        console.log("[create] Navigating to opening story...");
        router.push("/story/opening");
        return;
      }

      // Create game (backend will generate attributes internally)
      const result = await api.games.create({
        character_settings: characterSettings,
        player_name: playerName,
        life_vision: lifeVision,
        language,
      });
      
      console.log("[create] Game created:", result.game_id);

      // ★ 只使用 game_id，session_id 实际就是 game_id
      useGameStore.getState().setGameSession(result.game_id, result.game_id.toString());
      
      // ★ 等待一下确保状态已持久化
      await new Promise(resolve => setTimeout(resolve, 100));
      
      console.log("[create] Navigating to opening story...");
      // Navigate to opening story
      router.push("/story/opening");
    } catch (err) {
      console.error("[create] Start game failed:", err);
      showToast("error", "创建游戏失败，请重试");
    } finally {
      setIsGenerating(false);
    }
  };

  // ==================== Auto-generation full-screen UI ====================
  if (autoGenPhase === "generating") {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 animate-page-enter">
        <Sparkles className="w-14 h-14 text-primary animate-pulse mb-6" />
        <p className="text-xl text-primary font-medium animate-pulse">
          正在生成{autoGenLabel}...
        </p>
        <p className="text-sm text-muted-foreground mt-3">
          {autoGenProgress}
        </p>
        <p className="text-xs text-muted-foreground/60 mt-6">
          系统正在根据你的设定自动构建角色背景
        </p>
      </div>
    );
  }

  if (autoGenPhase === "done") {
    return (
      <div className="min-h-screen bg-background animate-page-enter flex flex-col">
        <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-sm border-b border-border">
          <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                // Go back to the last step (portrait)
                setAutoGenPhase("idle");
                setCreationStep(CREATION_STEPS.length - 1);
              }}
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              返回修改
            </Button>
            <span className="text-sm text-muted-foreground">角色创建完成</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowPresetSheet(true)}
            >
              <Save className="w-4 h-4 mr-1" />
              保存
            </Button>
          </div>
        </header>

        {/* Centered completion message */}
        <main className="flex-1 flex flex-col items-center justify-center px-4 py-8">
          {/* ★ 主角图片展示 */}
          {playerImages.length > 0 && (
            <div className="mb-6 flex flex-col items-center">
              <img
                src={playerImages[selectedImageIndex]?.image_url || playerImages[0]?.image_url}
                alt={playerName || "主角"}
                className="w-32 h-48 object-cover rounded-lg border-2 border-primary/30 shadow-lg"
              />
              <span className="text-sm font-medium text-foreground mt-2">{playerName}</span>
            </div>
          )}
          
          <Sparkles className="w-14 h-14 text-primary mb-4" />
          <h2 className="text-xl font-bold text-foreground mb-1">角色设定完成</h2>
          <p className="text-sm text-muted-foreground text-center mb-6">
            {isPresetLoaded ? "已加载预设角色背景" : "已为你自动生成角色背景"}
          </p>

          {/* View details toggle */}
          <Button
            variant="ghost"
            size="sm"
            className="mb-4 text-muted-foreground"
            onClick={() => setShowDetails(!showDetails)}
          >
            <Eye className="w-4 h-4 mr-1" />
            查看设定详情
            {showDetails ? (
              <ChevronUp className="w-4 h-4 ml-1" />
            ) : (
              <ChevronDown className="w-4 h-4 ml-1" />
            )}
          </Button>

          {/* Collapsible details */}
          {showDetails && (
            <div className="w-full max-w-lg space-y-4 mb-6 animate-page-enter">
              {AUTO_ADVANCE_STEPS.map((step) => {
                const data = characterSettings[step];
                if (!data) return null;
                return (
                  <div key={step} className="space-y-1">
                    <h3 className="text-xs font-medium text-primary">
                      {STEP_LABELS[step]}
                    </h3>
                    <SettingDisplay
                      stepKey={step}
                      data={data as Record<string, unknown>}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-col gap-3 w-full max-w-xs">
            <Button
              className="w-full touch-target h-12"
              onClick={handleStartGame}
              disabled={isGenerating || !hasBasicInfo}
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              {hasBasicInfo ? "开始游戏" : "请先输入角色姓名"}
            </Button>
            <Button
              variant="outline"
              className="w-full touch-target"
              onClick={() => setShowPresetSheet(true)}
            >
              <Save className="w-4 h-4 mr-1" />
              保存为预设
            </Button>
          </div>
        </main>

        {/* Save preset sheet */}
        <Sheet open={showPresetSheet} onOpenChange={setShowPresetSheet}>
          <SheetContent side="bottom" className="bg-card border-t border-border">
            <SheetHeader>
              <SheetTitle className="text-foreground">保存角色预设</SheetTitle>
              <SheetDescription className="text-muted-foreground">
                保存当前角色设定以便下次使用
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-4 mt-4">
              <Input
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                placeholder="预设名称"
                className="bg-secondary border-border h-12"
                autoFocus
              />
              <Button
                className="w-full touch-target"
                disabled={!presetName.trim() || isSavingPreset}
                onClick={handleSavePreset}
              >
                {isSavingPreset && (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                )}
                保存
              </Button>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    );
  }

  // ==================== Interactive steps UI (steps 1-4) ====================
  return (
    <div className="min-h-screen bg-background animate-page-enter">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              resetCreation();
              router.push("/");
            }}
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            返回
          </Button>

          {/* Step indicator — all 5 steps */}
          <div className="flex items-center gap-1">
            {CREATION_STEPS.map((_, i) => (
              <button
                key={i}
                className={cn(
                  "w-2 h-2 rounded-full transition-all",
                  i === creationStep
                    ? "bg-primary w-6"
                    : i < creationStep
                    ? "bg-primary/50"
                    : "bg-muted"
                )}
                onClick={() => i < creationStep && setCreationStep(i)}
              />
            ))}
          </div>

          <span className="text-xs text-muted-foreground">
            {creationStep + 1}/{CREATION_STEPS.length}
          </span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Player name input (shown at step 0) */}
        {isFirstStep && (
          <div className="space-y-4 mb-8">
            <div>
              <label className="text-sm text-muted-foreground mb-1 block">
                角色姓名
              </label>
              <Input
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                placeholder="输入你的角色名"
                className="bg-secondary border-border h-12 text-base"
                autoFocus
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-1 block">
                人生愿景（可选）
              </label>
              <Textarea
                value={lifeVision}
                onChange={(e) => setLifeVision(e.target.value)}
                placeholder="描述你希望的人生方向..."
                className="bg-secondary border-border text-sm resize-none min-h-[80px]"
              />
            </div>
          </div>
        )}

        {/* Step content */}
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold text-foreground">
              {STEP_LABELS[currentStepKey]}
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              {STEP_DESCRIPTIONS[currentStepKey]}
            </p>
          </div>

          {/* Current setting display */}
          {characterSettings[currentStepKey] != null && !generatedContent && currentStepKey !== "portrait" && (
            <SettingDisplay
              stepKey={currentStepKey}
              data={characterSettings[currentStepKey] as Record<string, unknown>}
            />
          )}
          
          {/* ★ Portrait step - 显示人物形象（多张） */}
          {currentStepKey === "portrait" && (
            <div className="space-y-4">
              {/* 图片展示区 - 多张图片并排 */}
              <div className="w-full">
                {isGeneratingImage ? (
                  <div className="w-full aspect-[9/17] max-w-sm mx-auto bg-secondary rounded-lg overflow-hidden flex items-center justify-center">
                    <div className="flex flex-col items-center gap-2 text-muted-foreground">
                      <Loader2 className="w-8 h-8 animate-spin" />
                      <span className="text-sm">AI正在生成人物形象...</span>
                      <span className="text-xs text-muted-foreground/60">（生成人物形象）</span>
                    </div>
                  </div>
                ) : playerImages.length > 0 ? (
                  <div className="space-y-3">
                    {/* 主图展示 - 容器比例匹配图片(9:17) */}
                    <div className="w-full aspect-[9/17] max-w-sm mx-auto bg-secondary rounded-lg overflow-hidden">
                      <img 
                        src={playerImage?.image_url} 
                        alt={playerName}
                        className="w-full h-full object-contain"
                      />
                    </div>
                    
                    {/* 缩略图选择 - 多张图片时显示 */}
                    {playerImages.length > 1 && (
                      <div className="flex gap-2 justify-center">
                        {playerImages.map((img, idx) => (
                          <button
                            key={img.image_id}
                            className={cn(
                              "w-16 h-20 rounded overflow-hidden border-2 transition-all",
                              idx === selectedImageIndex 
                                ? "border-primary ring-2 ring-primary/30" 
                                : "border-transparent opacity-70 hover:opacity-100"
                            )}
                            onClick={() => setSelectedImageIndex(idx)}
                          >
                            <img 
                              src={img.image_url} 
                              alt={`${playerName} - ${idx + 1}`}
                              className="w-full h-full object-contain"
                            />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="w-full aspect-[9/17] max-w-sm mx-auto bg-secondary rounded-lg overflow-hidden flex items-center justify-center">
                    <div className="text-center text-muted-foreground p-4">
                      <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
                      <p className="text-sm">正在准备生成...</p>
                    </div>
                  </div>
                )}
              </div>
              
              {/* ★ 后台生成进度提示 */}
              {isBackgroundGenerating && playerImages.length > 0 && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground bg-secondary/50 rounded-lg px-3 py-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>后台正在生成家庭背景、人际关系等设定...</span>
                </div>
              )}
              
              {/* 修改意见输入 */}
              {playerImages.length > 0 && !isGeneratingImage && (
                <div className="space-y-2">
                  <Input
                    value={imageFeedback}
                    onChange={(e) => setImageFeedback(e.target.value)}
                    placeholder="不满意？描述你想要的修改...（会保留之前的角色设定）"
                    className="bg-secondary border-border"
                  />
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={async () => {
                      if (imageFeedback.trim()) {
                        try {
                          await regeneratePlayerImage(imageFeedback);
                          setImageFeedback("");
                        } catch (err) {
                          console.error("[portrait] Failed to regenerate:", err);
                          showToast("error", String(err) || "重新生成失败");
                        }
                      }
                    }}
                    disabled={!imageFeedback.trim()}
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    根据修改意见重新生成
                  </Button>
                  
                  {/* ★ 完全重新生成按钮 */}
                  <Button
                    variant="ghost"
                    className="w-full text-muted-foreground"
                    onClick={async () => {
                      try {
                        await regenerateFreshPlayerImage();
                      } catch (err) {
                        console.error("[portrait] Failed to fresh regenerate:", err);
                        showToast("error", String(err) || "完全重新生成失败");
                      }
                    }}
                    disabled={isGeneratingImage}
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    完全重新生成（抛弃历史修改）
                  </Button>
                </div>
              )}
              
              {/* 等待 gameId */}
              {playerImages.length === 0 && !isGeneratingImage && !gameId && (
                <div className="flex flex-col items-center gap-2 text-muted-foreground py-4">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">正在准备...</span>
                </div>
              )}
            </div>
          )}

          {/* Generated content preview */}
          {generatedContent && (
            <SettingDisplay
              stepKey={currentStepKey}
              data={generatedContent}
              isNew
            />
          )}

          {/* Loading state - ★ 现在自动生成，显示加载状态 */}
          {isGenerating && <SkeletonStory message={`AI正在生成${STEP_LABELS[currentStepKey]}...`} />}

          {/* ★ 如果没有姓名，提示用户先输入 */}
          {!isPortraitStep && !isGenerating && !generatedContent && characterSettings[currentStepKey] == null && !hasBasicInfo && (
            <div className="text-center py-8 text-muted-foreground">
              <p>请先输入角色姓名</p>
            </div>
          )}

          {/* Feedback + regenerate */}
          {(generatedContent || characterSettings[currentStepKey] != null) && !isGenerating && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="不满意？告诉AI你的想法..."
                  className="flex-1 bg-secondary border-border text-sm h-10"
                />
                <Button
                  variant="outline"
                  size="icon"
                  className="h-10 w-10"
                  onClick={handleRegenerate}
                  disabled={isGenerating}
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="flex gap-3 mt-8 pt-6 border-t border-border">
          {!isFirstStep && (
            <Button
              variant="outline"
              className="touch-target"
              onClick={() => {
                setGeneratedContent(null);
                setFeedback("");
                prevCreationStep();
              }}
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              上一步
            </Button>
          )}

          <div className="flex-1" />

          <Button
            className="touch-target"
            onClick={handleAcceptAndNext}
            disabled={
              isGenerating ||
              isGeneratingImage ||
              // portrait 步骤检查 playerImages
              (isPortraitStep ? playerImages.length === 0 : (!generatedContent && characterSettings[currentStepKey] == null))
            }
          >
            {isLastStep ? (
              <>
                <Sparkles className="w-4 h-4 mr-1" />
                生成角色
              </>
            ) : (
              <>
                下一步
                <ArrowRight className="w-4 h-4 ml-1" />
              </>
            )}
          </Button>
        </div>
      </main>

      {/* Save preset sheet — keep for interactive mode too */}
      <Sheet open={showPresetSheet} onOpenChange={setShowPresetSheet}>
        <SheetContent side="bottom" className="bg-card border-t border-border">
          <SheetHeader>
            <SheetTitle className="text-foreground">保存角色预设</SheetTitle>
            <SheetDescription className="text-muted-foreground">
              保存当前角色设定以便下次使用
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-4 mt-4">
            <Input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="预设名称"
              className="bg-secondary border-border h-12"
              autoFocus
            />
            <Button
              className="w-full touch-target"
              disabled={!presetName.trim() || isSavingPreset}
              onClick={handleSavePreset}
            >
              {isSavingPreset && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              保存
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm z-50 animate-fade-in",
            toast.type === "success"
              ? "bg-green-500/90 text-white"
              : "bg-red-500/90 text-white"
          )}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
