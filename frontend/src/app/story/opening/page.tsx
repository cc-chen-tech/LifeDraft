"use client";

// Augment window for E2E test data injection
declare global {
  interface Window {
    __TEST_DATA__?: unknown;
  }
}

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StreamingText } from "@/components/game/StreamingText";
import { OpeningCompletionGate } from "@/components/game/OpeningCompletionGate";
import { FormField, PageTransition, Surface } from "@/components/story101";
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
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit, unicodeCharacterLength } from "@/lib/inputLimits";

export default function OpeningStoryPage() {
  const router = useRouter();
  const gameId = useGameStore((s) => s.gameId);
  const openingStory = useGameStore((s) => s.openingStory);
  const setOpeningStory = useGameStore((s) => s.setOpeningStory);
  const playerName = useGameStore((s) => s.playerName);
  const characterSettings = useGameStore((s) => s.characterSettings);
  const constraintLevel = useGameStore((s) => s.constraintLevel);
  // ★ 图片相关状态从 useImageStore 获取
  const openingIllustration = useImageStore((s) => s.openingIllustration);
  const isGeneratingIllustration = useImageStore((s) => s.isGeneratingIllustration);
  const illustrationError = useImageStore((s) => s.illustrationError);
  const generateOpeningIllustration = useImageStore((s) => s.generateOpeningIllustration);
  const regenerateOpeningIllustration = useImageStore((s) => s.regenerateOpeningIllustration);
  const { language } = useUIStore();

  const [isStreaming, setIsStreaming] = useState(false);
  const [isComplete, setIsComplete] = useState(() => Boolean(openingStory));
  const [storyText, setStoryText] = useState(() => openingStory);
  const [displayedCompleteText, setDisplayedCompleteText] = useState("");
  const [error, setError] = useState("");
  const [streamingIdentity, setStreamingIdentity] = useState(0);
  const [storyDisplayIdentity, setStoryDisplayIdentity] = useState(0);
  const [illustrationPrompt, setIllustrationPrompt] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const activeAttemptRef = useRef(0);
  const openingPersistenceRef = useRef<{
    key: string;
    promise: Promise<void>;
  } | null>(null);
  const hydrated = useHydration();
  const showHydrationLoading = useDelayedLoading({
    isLoading: !hydrated,
    delay: getNarrativeLoadingDelay("hydrate"),
    loadingIdentity: "opening-hydration",
  });
  const isOpeningDelayed = useDelayedLoading({
    isLoading: hydrated && isStreaming,
    delay: getNarrativeLoadingDelay("opening", constraintLevel),
    loadingIdentity: streamingIdentity,
  });
  const illustrationGeneratedRef = useRef(false);
  const illustrationPromptRemaining =
    INPUT_LIMITS.feedback - unicodeCharacterLength(illustrationPrompt);
  const illustrationPromptWithinLimit = isWithinInputLimit(
    illustrationPrompt,
    INPUT_LIMITS.feedback,
  );
  
  // ★ 添加渲染计数器来诊断问题
  const renderCountRef = useRef(0);
  // Note: ref access moved to useEffect to avoid React warning

  useEffect(() => {
    console.log(`[OpeningStory] Render #${renderCountRef.current}, hydrated=${hydrated}`);
  });

  const ensureOpeningContinuityPersisted = useCallback(({
    persistenceGameId,
    persistenceStory,
    persistenceCharacterSettings,
    persistencePlayerName,
    persistenceLifeVision,
  }: {
    persistenceGameId: number;
    persistenceStory: string;
    persistenceCharacterSettings: Record<string, unknown>;
    persistencePlayerName: string;
    persistenceLifeVision: string;
  }): Promise<void> => {
    const normalizedStory = persistenceStory.trim();
    if (!normalizedStory) return Promise.resolve();

    const key = `${persistenceGameId}:${normalizedStory}`;
    if (openingPersistenceRef.current?.key === key) {
      return openingPersistenceRef.current.promise;
    }

    const promise = (async () => {
      for (let attempt = 1; attempt <= 2; attempt += 1) {
        try {
          await games.patchCharacterSettings(
            persistenceGameId,
            { ...persistenceCharacterSettings, opening_story: normalizedStory },
            {
              player_name: persistencePlayerName.trim(),
              life_vision: persistenceLifeVision,
            },
          );
          return;
        } catch (err) {
          console.warn("[OpeningStory] Opening continuity persistence failed", {
            gameId: persistenceGameId,
            attempt,
            willRetry: attempt === 1,
            errorType: err instanceof Error ? err.name : typeof err,
          });
        }
      }
    })();

    openingPersistenceRef.current = { key, promise };
    return promise;
  }, []);

  const waitForPersistenceBounded = useCallback((persistence: Promise<void>) => (
    new Promise<void>((resolve) => {
      const timeoutId = window.setTimeout(resolve, 2000);
      void persistence.then(() => {
        window.clearTimeout(timeoutId);
        resolve();
      });
    })
  ), []);

  const startOpeningStream = useCallback(({
    attemptGameId,
    attemptCharacterSettings,
    attemptPlayerName,
    attemptLifeVision,
    attemptLanguage,
    generateIllustrationOnComplete,
  }: {
    attemptGameId: number | null;
    attemptCharacterSettings: Record<string, unknown>;
    attemptPlayerName: string;
    attemptLifeVision: string;
    attemptLanguage: string;
    generateIllustrationOnComplete: boolean;
  }) => {
    const attemptId = activeAttemptRef.current + 1;
    activeAttemptRef.current = attemptId;
    abortRef.current?.abort();

    const controller = new AbortController();
    abortRef.current = controller;
    let streamedText = "";
    let hasReceivedChunk = false;
    let settled = false;

    const isActiveAttempt = () =>
      activeAttemptRef.current === attemptId && !controller.signal.aborted && !settled;

    const failAttempt = (streamError: unknown) => {
      if (!isActiveAttempt()) return;

      settled = true;
      controller.abort();
      const message =
        streamError instanceof Error
          ? streamError.message
          : typeof streamError === "object" &&
              streamError !== null &&
              "message" in streamError &&
              typeof streamError.message === "string"
            ? streamError.message
            : "未知错误";
      console.error("[OpeningStory] SSE error:", streamError);
      setIsStreaming(false);
      setError("故事生成失败: " + (message || "未知错误"));
    };

    setError("");
    setStreamingIdentity(attemptId);
    setIsStreaming(true);
    setIsComplete(false);

    try {
      const streamPromise = streamOpeningStory(
        attemptCharacterSettings,
        attemptPlayerName,
        attemptLifeVision,
        attemptLanguage,
        {
          onStory: (text) => {
            if (!isActiveAttempt() || !text) return;

            const replacePreviousAttempt = !hasReceivedChunk;
            hasReceivedChunk = true;
            const nextAttemptText = streamedText + text;
            streamedText = nextAttemptText;
            setDisplayedCompleteText("");
            if (replacePreviousAttempt) {
              setStoryDisplayIdentity(attemptId);
            }
            setStoryText(nextAttemptText);
          },
          onComplete: (data) => {
            if (!isActiveAttempt()) return;

            const fullText = (data && typeof data === "object" && "full_story" in data)
              ? (data as { full_story?: string }).full_story || ""
              : "";
            const finalText = fullText || streamedText;
            if (!finalText.trim()) {
              failAttempt(new Error("故事内容为空"));
              return;
            }

            settled = true;
            console.log("[OpeningStory] Generation complete, length:", finalText.length);
            if (finalText) {
              setStoryText(finalText);
              setOpeningStory(finalText);
            }
            setIsStreaming(false);
            setError("");

            const currentGameId = attemptGameId;
            if (currentGameId) {
              void ensureOpeningContinuityPersisted({
                persistenceGameId: currentGameId,
                persistenceStory: finalText,
                persistenceCharacterSettings: attemptCharacterSettings,
                persistencePlayerName: attemptPlayerName,
                persistenceLifeVision: attemptLifeVision,
              });
            }

            if (generateIllustrationOnComplete) {
              // ★ 故事生成完成后，触发插画生成
              if (!illustrationGeneratedRef.current && currentGameId) {
                illustrationGeneratedRef.current = true;
                console.log("[OpeningStory] Story complete, triggering illustration generation...");
                // 延迟一点生成插画，让用户先看到故事
                setTimeout(() => {
                  generateOpeningIllustration(
                    currentGameId,
                    finalText,
                    attemptCharacterSettings,
                    attemptPlayerName
                  );
                }, 500);
              }
            }
            setIsComplete(true);
          },
          onError: failAttempt,
        },
        {
          signal: controller.signal,
          enableReconnect: false,
        }
      );

      void Promise.resolve(streamPromise).catch(failAttempt);
    } catch (streamError) {
      failAttempt(streamError);
    }
  }, [ensureOpeningContinuityPersisted, generateOpeningIllustration, setOpeningStory]);

  // Defer initialization by one microtask so StrictMode can replay the effect
  // without issuing and immediately aborting a duplicate backend request.
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;

    const initialize = async () => {
      if (cancelled) return;

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
        if (state.gameId) {
          void ensureOpeningContinuityPersisted({
            persistenceGameId: state.gameId,
            persistenceStory: state.openingStory,
            persistenceCharacterSettings: resolvedCharacterSettings,
            persistencePlayerName: resolvedPlayerName,
            persistenceLifeVision: resolvedLifeVision,
          });
        }
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
      startOpeningStream({
        attemptGameId: state.gameId,
        attemptCharacterSettings: resolvedCharacterSettings,
        attemptPlayerName: resolvedPlayerName,
        attemptLifeVision: resolvedLifeVision,
        attemptLanguage: language,
        generateIllustrationOnComplete: true,
      });
    };

    void Promise.resolve().then(initialize);

    return () => {
      cancelled = true;
      console.log("[OpeningStory] Cleanup: aborting SSE");
      abortRef.current?.abort();
    };
  }, [ensureOpeningContinuityPersisted, hydrated, language, startOpeningStream]);

  const handleRetry = () => {
    console.log("[OpeningStory] Retrying generation...");
    const state = useGameStore.getState();
    startOpeningStream({
      attemptGameId: state.gameId,
      attemptCharacterSettings: state.characterSettings,
      attemptPlayerName: state.playerName,
      attemptLifeVision: state.lifeVision,
      attemptLanguage: language,
      generateIllustrationOnComplete: false,
    });
  };

  const handleStart = async () => {
    if (!isComplete || displayedCompleteText !== storyText || isStarting) return;

    const state = useGameStore.getState();
    const currentGameId = state.gameId;
    
    console.log("[OpeningStory] Starting game, gameId:", currentGameId);
    
    if (currentGameId) {
      setIsStarting(true);
      const persistence = ensureOpeningContinuityPersisted({
        persistenceGameId: currentGameId,
        persistenceStory: (state.openingStory || storyText).trim(),
        persistenceCharacterSettings: state.characterSettings,
        persistencePlayerName: state.playerName,
        persistenceLifeVision: state.lifeVision,
      });
      await waitForPersistenceBounded(persistence);

      router.push("/play");
    } else {
      console.warn("[OpeningStory] No gameId, going to create page");
      router.push("/create");
    }
  };

  // 等待 hydration
  if (!hydrated) {
    if (storyText || openingStory) {
      return <div className="min-h-screen" aria-busy="true" />;
    }
    return showHydrationLoading ? (
      <NarrativeLoadingState context="hydrate" layout="screen" />
    ) : (
      <div className="min-h-screen" aria-busy="true" />
    );
  }

  // 错误状态
  if (error && !storyText) {
    return (
      <div className="relative min-h-[100dvh]">
        <NarrativeLoadingState
          context="opening"
          layout="screen"
          phase="generating"
          transport="failed"
          onAction={handleRetry}
        />
        <div className="absolute inset-x-0 bottom-8 flex flex-col items-center gap-3 px-4">
          <p className="text-center text-sm text-[var(--danger-foreground)]">{error}</p>
          <Button
            type="button"
            variant="quiet"
            size="touch"
            onClick={() => router.push("/")}
          >
            <Home className="w-4 h-4 mr-2" />
            返回首页
          </Button>
        </div>
      </div>
    );
  }

  if (!storyText && (isStreaming || !isComplete)) {
    return (
      <NarrativeLoadingState
        context="opening"
        layout="screen"
        phase="generating"
        delayed={isOpeningDelayed}
      />
    );
  }

  return (
    <PageTransition className="min-h-[100dvh] bg-[var(--surface-canvas)] px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto w-full max-w-[70ch]">
        <header className="mb-5 border-b border-[var(--border-default)] pb-4">
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-3xl">
            人生开篇
          </h1>
        </header>

        <Surface variant="reading" className="px-4 py-6 sm:px-8 sm:py-9">
          <div className="space-y-8">
          {storyText && (
            <StreamingText
              key={storyDisplayIdentity}
              text={storyText}
              isStreaming={isStreaming}
              narrative
              showCursor={false}
              onDisplayComplete={setDisplayedCompleteText}
            />
          )}

          {storyText && isStreaming && (
            <NarrativeLoadingState
              context="opening"
              layout="inline"
              phase="generating"
              delayed={isOpeningDelayed}
            />
          )}

          {storyText && error && (
            <NarrativeLoadingState
              context="opening"
              layout="inline"
              phase="generating"
              transport="failed"
              onAction={handleRetry}
            />
          )}

          {isComplete && (
            <div className="space-y-5 border-t border-[var(--border-default)] pt-7">
              {isGeneratingIllustration && (
                <div className="flex flex-col items-center gap-3 py-6 text-center">
                  <ImageIcon
                    aria-hidden="true"
                    className="h-6 w-6 text-[var(--text-secondary)]"
                  />
                  <p className="text-sm text-[var(--text-primary)]">正在绘制人生插画</p>
                  <p className="text-xs text-[var(--text-secondary)]">
                    从故事中选择一个重要场景
                  </p>
                </div>
              )}

              {illustrationError && !isGeneratingIllustration && (
                <div className="space-y-3 py-4 text-center">
                  <p className="text-sm text-[var(--danger-foreground)]">
                    插画生成失败，但不影响游戏体验
                  </p>
                  <Button
                    type="button"
                    variant="narrative"
                    size="touch"
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

              {openingIllustration && !isGeneratingIllustration && (
                <div className="w-full space-y-5">
                  <div className="mx-auto aspect-video w-full max-w-2xl overflow-hidden rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)]">
                    <img
                      src={openingIllustration.image_url}
                      alt="开场插画"
                      className="h-full w-full object-cover"
                    />
                  </div>
                  <p className="text-center text-xs text-[var(--text-secondary)]">
                    {openingIllustration.scene_description}
                  </p>

                  <div className="mx-auto w-full max-w-2xl space-y-3 pt-2">
                    <FormField
                      id="opening-illustration-instruction"
                      label="调整开场插画"
                      description="写下希望改变的画面细节。"
                    >
                      {({ describedBy }) => (
                        <>
                          <Textarea
                            id="opening-illustration-instruction"
                            name="opening-illustration-instruction"
                            value={illustrationPrompt}
                            onChange={(event) => setIllustrationPrompt(event.target.value)}
                            placeholder="例如：换成夜晚，增加雨景"
                            surface="filled"
                            controlSize="touch"
                            disabled={isGeneratingIllustration}
                            aria-invalid={!illustrationPromptWithinLimit}
                            aria-describedby={[
                              describedBy,
                              "opening-illustration-instruction-count",
                            ].filter(Boolean).join(" ")}
                          />
                          <p
                            id="opening-illustration-instruction-count"
                            className={
                              illustrationPromptRemaining < 0
                                ? "text-right text-xs text-[var(--danger-foreground)]"
                                : "text-right text-xs text-[var(--text-secondary)]"
                            }
                          >
                            {illustrationPromptRemaining < 0
                              ? `已超出 ${Math.abs(illustrationPromptRemaining)} 字`
                              : `还可输入 ${illustrationPromptRemaining} 字`}
                          </p>
                        </>
                      )}
                    </FormField>
                    <Button
                      type="button"
                      variant="narrative"
                      size="touch"
                      className="w-full"
                      onClick={() => {
                        if (
                          illustrationPrompt.trim() &&
                          gameId &&
                          illustrationPromptWithinLimit
                        ) {
                          regenerateOpeningIllustration(gameId, openingStory || storyText, characterSettings, playerName, illustrationPrompt);
                          setIllustrationPrompt("");
                        }
                      }}
                      disabled={
                        !illustrationPrompt.trim() ||
                        isGeneratingIllustration ||
                        !illustrationPromptWithinLimit
                      }
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      根据描述重新生成
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

            <div className="flex justify-center border-t border-[var(--border-default)] pt-7">
              {isComplete ? (
                <OpeningCompletionGate
                  backendComplete={isComplete}
                  visibleComplete={Boolean(storyText) && displayedCompleteText === storyText}
                  pending={isStarting}
                  onStart={handleStart}
                />
              ) : !isStreaming && !error ? (
                <Button
                  type="button"
                  variant="narrative"
                  size="touch"
                  onClick={handleRetry}
                >
                  <Loader2 className="w-4 h-4 mr-2" />
                  重新加载
                </Button>
              ) : null}
            </div>
          </div>
        </Surface>
      </div>
    </PageTransition>
  );
}
