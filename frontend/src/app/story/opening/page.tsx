"use client";

// Augment window for E2E test data injection
declare global {
  interface Window {
    __TEST_DATA__?: unknown;
  }
}

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { StreamingText } from "@/components/game/StreamingText";
import { OpeningCompletionGate } from "@/components/game/OpeningCompletionGate";
import {
  NarrativeLoadingState,
  getNarrativeLoadingDelay,
} from "@/components/narrative-loading/NarrativeLoadingState";
import { useGameStore } from "@/stores/useGameStore";
import { useUIStore } from "@/stores/useUIStore";
import { useImageStore } from "@/stores/useImageStore";
import { useHydration } from "@/hooks/useHydration";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";
import { games } from "@/lib/api";
import { streamOpeningStory } from "@/lib/sse";
import { Loader2, Home, ImageIcon, RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";

export default function OpeningStoryPage() {
  const router = useRouter();
  const gameId = useGameStore((s) => s.gameId);
  const openingStory = useGameStore((s) => s.openingStory);
  const setOpeningStory = useGameStore((s) => s.setOpeningStory);
  const playerName = useGameStore((s) => s.playerName);
  const lifeVision = useGameStore((s) => s.lifeVision);
  const characterSettings = useGameStore((s) => s.characterSettings);
  // ★ 图片相关状态从 useImageStore 获取
  const openingIllustration = useImageStore((s) => s.openingIllustration);
  const isGeneratingIllustration = useImageStore((s) => s.isGeneratingIllustration);
  const illustrationError = useImageStore((s) => s.illustrationError);
  const generateOpeningIllustration = useImageStore((s) => s.generateOpeningIllustration);
  const regenerateOpeningIllustration = useImageStore((s) => s.regenerateOpeningIllustration);
  const { language } = useUIStore();

  const [isStreaming, setIsStreaming] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [storyText, setStoryText] = useState("");
  const [displayedCompleteText, setDisplayedCompleteText] = useState("");
  const [error, setError] = useState("");
  const [illustrationPrompt, setIllustrationPrompt] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const hydrated = useHydration();
  const showHydrationLoading = useDelayedLoading({
    isLoading: !hydrated,
    delay: getNarrativeLoadingDelay("hydrate"),
    loadingIdentity: "opening-hydration",
  });
  const illustrationGeneratedRef = useRef(false);
  
  // ★ 防止重复执行的标记
  const initializedRef = useRef(false);
  
  // ★ 添加渲染计数器来诊断问题
  const renderCountRef = useRef(0);
  // Note: ref access moved to useEffect to avoid React warning

  useEffect(() => {
    console.log(`[OpeningStory] Render #${renderCountRef.current}, hydrated=${hydrated}, initialized=${initializedRef.current}`);
  });

  // ★ 初始化：只执行一次
  useEffect(() => {
    if (!hydrated || initializedRef.current) return;
    initializedRef.current = true;
    let cancelled = false;

    const initialize = async () => {
      // ★ 支持测试数据注入（E2E 测试用）
      const testData = (typeof window !== "undefined" && window.__TEST_DATA__) || null;
      if (testData) {
        console.log("[OpeningStory] Using test data injection");
      }

      let state = useGameStore.getState();

      // 使用测试数据或 store 状态
      const injected = testData as Record<string, unknown> | null;
      let resolvedCharacterSettings = (injected?.characterSettings as typeof state.characterSettings) || state.characterSettings;
      let resolvedPlayerName = (injected?.playerName as string) || state.playerName;
      let resolvedLifeVision = (injected?.lifeVision as string) || state.lifeVision;

      const needsRecoveredCharacterState =
        !testData &&
        !state.openingStory &&
        (Object.keys(resolvedCharacterSettings).length === 0 || !resolvedPlayerName);

      if (needsRecoveredCharacterState) {
        try {
          const activeGameId = state.gameId || (await games.getActive()).game_id;
          if (activeGameId) {
            console.log("[OpeningStory] Recovering active game before opening generation:", activeGameId);
            await useGameStore.getState().loadGameState(activeGameId);
            state = useGameStore.getState();
            resolvedCharacterSettings = state.characterSettings;
            resolvedPlayerName = state.playerName;
            resolvedLifeVision = state.lifeVision;
          }
        } catch (err) {
          console.warn("[OpeningStory] Active game recovery failed before opening generation:", err);
        }
      }

      if (cancelled) return;

      console.log("[OpeningStory] Initializing:", {
        gameId: state.gameId,
        hasStory: !!state.openingStory,
        playerName: resolvedPlayerName,
        settingsCount: Object.keys(resolvedCharacterSettings).length,
      });

      // 如果已有故事，直接显示
      if (state.openingStory) {
        console.log("[OpeningStory] Using existing story");
        setStoryText(state.openingStory);
        setIsComplete(true);
        return;
      }

      // 检查是否有足够的数据生成故事
      const hasSettings = Object.keys(resolvedCharacterSettings).length > 0;
      const hasPlayerName = !!resolvedPlayerName;

      if (!hasSettings || !hasPlayerName) {
        console.error("[OpeningStory] Missing data:", { hasSettings, hasPlayerName });
        setError("缺少角色数据，无法生成开场故事");
        return;
      }

      // 开始生成故事
      console.log("[OpeningStory] Starting generation...");
      setIsStreaming(true);
      abortRef.current = new AbortController();

      let streamedText = "";

      streamOpeningStory(
        resolvedCharacterSettings,
        resolvedPlayerName,
        resolvedLifeVision,
        language,
        {
          onStory: (text) => {
            setDisplayedCompleteText("");
            streamedText += text;
            setStoryText((prev) => prev + text);
          },
          onComplete: (data) => {
            const fullText = (data && typeof data === 'object' && 'full_story' in data)
              ? (data as { full_story?: string }).full_story || ""
              : "";
            const finalText = fullText || streamedText;
            console.log("[OpeningStory] Generation complete, length:", finalText.length);
            if (finalText) {
              setStoryText(finalText);
              setOpeningStory(finalText);
            }
            setIsStreaming(false);

            // ★ 故事生成完成后，触发插画生成
            const currentGameId = useGameStore.getState().gameId;
            if (!illustrationGeneratedRef.current && currentGameId) {
              illustrationGeneratedRef.current = true;
              console.log("[OpeningStory] Story complete, triggering illustration generation...");
              // 延迟一点生成插画，让用户先看到故事
              setTimeout(() => {
                generateOpeningIllustration(currentGameId, finalText, resolvedCharacterSettings, resolvedPlayerName);
              }, 500);
            }
            setIsComplete(true);
          },
          onError: (err) => {
            console.error("[OpeningStory] SSE error:", err);
            setIsStreaming(false);
            setError("故事生成失败: " + (err.message || "未知错误"));
          },
        },
        {
          signal: abortRef.current.signal,
          enableReconnect: false,
        }
      );
    };

    void initialize();

    return () => {
      cancelled = true;
      console.log("[OpeningStory] Cleanup: aborting SSE");
      abortRef.current?.abort();
    };
  }, [hydrated, language, setOpeningStory, generateOpeningIllustration]);

  const handleRetry = () => {
    console.log("[OpeningStory] Retrying generation...");
    setError("");
    setStoryText("");
    setDisplayedCompleteText("");
    setIsStreaming(true);
    setIsComplete(false);
    
    const state = useGameStore.getState();
    abortRef.current = new AbortController();
    
    let streamedText = "";

    streamOpeningStory(
      state.characterSettings,
      state.playerName,
      state.lifeVision,
      language,
      {
        onStory: (text) => {
          setDisplayedCompleteText("");
          streamedText += text;
          setStoryText((prev) => prev + text);
        },
        onComplete: (data) => {
          const fullText = (data && typeof data === 'object' && 'full_story' in data)
            ? (data as { full_story?: string }).full_story || ""
            : "";
          const finalText = fullText || streamedText;
          if (finalText) {
            setStoryText(finalText);
            setOpeningStory(finalText);
          }
          setIsStreaming(false);
          setIsComplete(true);
        },
        onError: (err) => {
          console.error("[OpeningStory] Retry error:", err);
          setIsStreaming(false);
          setError("重试失败: " + (err.message || "未知错误"));
        },
      },
      { 
        signal: abortRef.current.signal,
        enableReconnect: false,
      }
    );
  };

  const handleStart = async () => {
    if (!isComplete || displayedCompleteText !== storyText) return;

    const currentGameId = useGameStore.getState().gameId;
    
    console.log("[OpeningStory] Starting game, gameId:", currentGameId);
    
    if (currentGameId) {
      const openingForContinuity = (openingStory || storyText).trim();

      try {
        await games.patchCharacterSettings(
          currentGameId,
          { ...characterSettings, opening_story: openingForContinuity },
          { player_name: playerName.trim(), life_vision: lifeVision },
        );
      } catch (err) {
        console.warn("[OpeningStory] Failed to persist opening continuity:", err);
      }

      router.push("/play");
    } else {
      console.warn("[OpeningStory] No gameId, going to create page");
      router.push("/create");
    }
  };

  // 等待 hydration
  if (!hydrated) {
    return showHydrationLoading ? (
      <NarrativeLoadingState context="hydrate" layout="screen" />
    ) : (
      <div className="min-h-screen" aria-busy="true" />
    );
  }

  // 错误状态
  if (error) {
    return (
      <div className="min-h-screen">
        <NarrativeLoadingState
          context="opening"
          layout="screen"
          phase="generating"
          transport="failed"
          onAction={handleRetry}
        />
        <div className="absolute inset-x-0 bottom-8 flex flex-col items-center gap-3 px-4">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={() => router.push("/")}>
            <Home className="w-4 h-4 mr-2" />
            返回首页
          </Button>
        </div>
      </div>
    );
  }

  if (!storyText && (isStreaming || !isComplete)) {
    return <NarrativeLoadingState context="opening" layout="screen" phase="generating" />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-background animate-page-enter">
      <div className="flex-1 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-[65ch] space-y-8">
          {storyText && (
            <StreamingText
              text={storyText}
              isStreaming={isStreaming}
              narrative
              onDisplayComplete={setDisplayedCompleteText}
            />
          )}

          {storyText && isStreaming && (
            <NarrativeLoadingState context="opening" layout="inline" phase="generating" />
          )}
          
          {/* ★ 开场插画展示区 */}
          {isComplete && (
            <div className="flex flex-col items-center space-y-4 animate-fade-in">
              {/* 插画生成中 */}
              {isGeneratingIllustration && (
                <div className="flex flex-col items-center gap-3 py-8">
                  <div className="relative">
                    <div className="w-16 h-16 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
                    <ImageIcon className="absolute inset-0 m-auto w-6 h-6 text-primary" />
                  </div>
                  <div className="text-center space-y-1">
                    <p className="text-sm text-muted-foreground animate-pulse">
                      AI正在为你绘制人生插画...
                    </p>
                    <p className="text-xs text-muted-foreground/60">
                      从故事中选择一个重要场景进行创作
                    </p>
                  </div>
                </div>
              )}
              
              {/* 插画生成错误 */}
              {illustrationError && !isGeneratingIllustration && (
                <div className="text-center py-4 space-y-3">
                  <p className="text-xs text-muted-foreground/60">
                    插画生成失败，但不影响游戏体验
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      console.log("[OpeningStory] Retrying illustration generation...");
                      if (gameId) {
                        generateOpeningIllustration(gameId, openingStory || storyText, characterSettings, playerName);
                      }
                    }}
                  >
                    <ImageIcon className="w-4 h-4 mr-2" />
                    重新生成插画
                  </Button>
                </div>
              )}
              
              {/* 插画展示 */}
              {openingIllustration && !isGeneratingIllustration && (
                <div className="w-full space-y-4">
                  <div className="w-full aspect-video max-w-2xl mx-auto bg-secondary rounded-lg overflow-hidden shadow-lg">
                    <img 
                      src={openingIllustration.image_url} 
                      alt="开场插画"
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <p className="text-xs text-center text-muted-foreground/60">
                    {openingIllustration.scene_description}
                  </p>
                  
                  {/* ★ 用户输入提示词重新生成 */}
                  <div className="w-full max-w-2xl mx-auto space-y-2 pt-2">
                    <Input
                      value={illustrationPrompt}
                      onChange={(e) => setIllustrationPrompt(e.target.value)}
                      placeholder="想修改插画？描述你的想法，如：换成夜晚场景、增加 rain 效果..."
                      className="bg-secondary border-border text-sm"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        if (illustrationPrompt.trim() && gameId) {
                          regenerateOpeningIllustration(gameId, openingStory || storyText, characterSettings, playerName, illustrationPrompt);
                          setIllustrationPrompt("");
                        }
                      }}
                      disabled={!illustrationPrompt.trim() || isGeneratingIllustration}
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      根据描述重新生成
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="p-6 flex justify-center">
        {isComplete ? (
          <OpeningCompletionGate
            backendComplete={isComplete}
            visibleComplete={Boolean(storyText) && displayedCompleteText === storyText}
            onStart={handleStart}
          />
        ) : !isStreaming ? (
          <Button
            variant="outline"
            className="touch-target"
            onClick={handleRetry}
          >
            <Loader2 className="w-4 h-4 mr-2" />
            重新加载
          </Button>
        ) : null}
      </div>
    </div>
  );
}
