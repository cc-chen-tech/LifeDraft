"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { StreamingText } from "@/components/game/StreamingText";
import { SkeletonStory } from "@/components/game/SkeletonStory";
import { useGameStore } from "@/stores/useGameStore";
import { useUIStore } from "@/stores/useUIStore";
import { useImageStore } from "@/stores/useImageStore";
import { useHydration } from "@/hooks/useHydration";
import { streamOpeningStory } from "@/lib/sse";
import { Play, Loader2, Home, ImageIcon, RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";

export default function OpeningStoryPage() {
  const router = useRouter();
  const gameId = useGameStore((s) => s.gameId);
  const openingStory = useGameStore((s) => s.openingStory);
  const setOpeningStory = useGameStore((s) => s.setOpeningStory);
  const playerName = useGameStore((s) => s.playerName);
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
  const [error, setError] = useState("");
  const [illustrationPrompt, setIllustrationPrompt] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const hydrated = useHydration();
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

    // ★ 支持测试数据注入（E2E 测试用）
    const testData = (typeof window !== "undefined" && (window as any).__TEST_DATA__) || null;
    if (testData) {
      console.log("[OpeningStory] Using test data injection");
    }

    const state = useGameStore.getState();

    // 使用测试数据或 store 状态
    const characterSettings = testData?.characterSettings || state.characterSettings;
    const playerName = testData?.playerName || state.playerName;
    const lifeVision = testData?.lifeVision || state.lifeVision;

    console.log("[OpeningStory] Initializing:", {
      gameId: state.gameId,
      hasStory: !!state.openingStory,
      playerName,
      settingsCount: Object.keys(characterSettings).length,
    });

    // 如果已有故事，直接显示
    if (state.openingStory) {
      console.log("[OpeningStory] Using existing story");
      setStoryText(state.openingStory);
      setIsComplete(true);
      return;
    }

    // 检查是否有足够的数据生成故事
    const hasSettings = Object.keys(characterSettings).length > 0;
    const hasPlayerName = !!playerName;

    if (!hasSettings || !hasPlayerName) {
      console.error("[OpeningStory] Missing data:", { hasSettings, hasPlayerName });
      setError("缺少角色数据，无法生成开场故事");
      return;
    }
    
    // 开始生成故事
    console.log("[OpeningStory] Starting generation...");
    setIsStreaming(true);
    abortRef.current = new AbortController();

    streamOpeningStory(
      state.characterSettings,
      state.playerName,
      state.lifeVision,
      language,
      {
        onStory: (text) => {
          setStoryText((prev) => prev + text);
        },
        onComplete: (data) => {
          const fullText = (data && typeof data === 'object' && 'full_story' in data)
            ? (data as { full_story?: string }).full_story || ""
            : "";
          console.log("[OpeningStory] Generation complete, length:", fullText.length);
          if (fullText) {
            setStoryText(fullText);
            setOpeningStory(fullText);
          }
          setIsStreaming(false);
          setIsComplete(true);

          // ★ 故事生成完成后，触发插画生成
          if (!illustrationGeneratedRef.current && gameId) {
            illustrationGeneratedRef.current = true;
            console.log("[OpeningStory] Story complete, triggering illustration generation...");
            // 延迟一点生成插画，让用户先看到故事
            setTimeout(() => {
              generateOpeningIllustration(gameId, storyText, characterSettings, playerName);
            }, 500);
          }
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

    return () => {
      console.log("[OpeningStory] Cleanup: aborting SSE");
      abortRef.current?.abort();
    };
  }, [hydrated, language, setOpeningStory]);

  const handleRetry = () => {
    console.log("[OpeningStory] Retrying generation...");
    setError("");
    setStoryText("");
    setIsStreaming(true);
    setIsComplete(false);
    
    const state = useGameStore.getState();
    abortRef.current = new AbortController();
    
    streamOpeningStory(
      state.characterSettings,
      state.playerName,
      state.lifeVision,
      language,
      {
        onStory: (text) => {
          setStoryText((prev) => prev + text);
        },
        onComplete: (data) => {
          const fullText = (data && typeof data === 'object' && 'full_story' in data)
            ? (data as { full_story?: string }).full_story || ""
            : "";
          if (fullText) {
            setStoryText(fullText);
            setOpeningStory(fullText);
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

  const handleStart = () => {
    const currentGameId = useGameStore.getState().gameId;
    
    console.log("[OpeningStory] Starting game, gameId:", currentGameId);
    
    if (currentGameId) {
      router.push("/play");
    } else {
      console.warn("[OpeningStory] No gameId, going to create page");
      router.push("/create");
    }
  };

  // 等待 hydration
  if (!hydrated) {
    return <SkeletonStory message="加载中..." />;
  }

  // 错误状态
  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4">
        <div className="text-center space-y-4 max-w-md">
          <p className="text-destructive">{error}</p>
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={() => router.push("/")}>
              <Home className="w-4 h-4 mr-2" />
              返回首页
            </Button>
            <Button onClick={handleRetry}>
              <Loader2 className="w-4 h-4 mr-2" />
              重试
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background animate-page-enter">
      <div className="flex-1 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-[65ch] space-y-8">
          {/* ★ 修复：streaming 初始状态也显示 loading，避免空白 */}
          {(!storyText || isStreaming) && (
            <SkeletonStory message="正在编写你的人生开篇..." />
          )}

          {storyText && (
            <StreamingText
              text={storyText}
              isStreaming={isStreaming}
              narrative
            />
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
          <Button
            size="lg"
            className="h-14 px-8 text-base touch-target animate-fade-in-word"
            onClick={handleStart}
          >
            <Play className="w-5 h-5 mr-2" />
            开始我的人生
          </Button>
        ) : isStreaming ? (
          <div className="text-sm text-muted-foreground animate-pulse">
            故事正在展开...
          </div>
        ) : (
          <Button
            variant="outline"
            className="touch-target"
            onClick={handleRetry}
          >
            <Loader2 className="w-4 h-4 mr-2" />
            重新加载
          </Button>
        )}
      </div>
    </div>
  );
}
