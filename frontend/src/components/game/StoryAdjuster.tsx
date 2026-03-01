"use client";

import { useState, useRef } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, RotateCcw, Pencil, Check, X } from "lucide-react";
import { streamRewrite } from "@/lib/sse";
import { useGameStore } from "@/stores/useGameStore";

interface StoryAdjusterProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  gameId: number;
  fullStory: string;
  onRewriteComplete: (newStory: string) => void;
  onRegenerateComplete: () => void;
}

/**
 * StoryAdjuster — 改写/重新生成 Sheet
 * - 底部滑出（Mobile-first）
 * - 直接输入修改指令改写故事
 * - 支持整段重新生成（流式 SSE）
 */
export function StoryAdjuster({
  open,
  onOpenChange,
  gameId,
  fullStory,
  onRewriteComplete,
  onRegenerateComplete,
}: StoryAdjusterProps) {
  const [instruction, setInstruction] = useState("");
  const [isRewriting, setIsRewriting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error" | "loading"; message: string } | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const accumulatedStoryRef = useRef("");  // 用 ref 累加流式文本

  const showToast = (type: "success" | "error" | "loading", message: string) => {
    setToast({ type, message });
    // Don't auto-hide loading toasts
    if (type !== "loading") {
      setTimeout(() => setToast(null), 3000);
    }
  };

  const handleRewrite = async (isRetry = false) => {
    if (!instruction.trim()) return;
    setIsRewriting(true);
    accumulatedStoryRef.current = "";  // 重置累加器
    showToast("loading", "正在改写中...");
    
    // 创建 AbortController 用于取消请求
    abortControllerRef.current = new AbortController();
    
    try {
      console.log("[StoryAdjuster] Starting streaming rewrite request...");
      
      const result = await streamRewrite(
        gameId,
        fullStory,
        instruction.trim(),
        fullStory,  // segment_to_replace
        "zh",  // language
        {
          onStory: (text) => {
            // 流式接收故事文本，累加后更新
            console.log("[StoryAdjuster] Received story chunk:", text?.substring(0, 50));
            accumulatedStoryRef.current += text;
            // ★ 使用 queueMicrotask 延迟到渲染周期外执行，避免 "setState in render" 错误
            queueMicrotask(() => {
              onRewriteComplete(accumulatedStoryRef.current);
            });
          },
          onStatus: (status) => {
            console.log("[StoryAdjuster] Status:", status);
            if (status.phase === "rewriting") {
              showToast("loading", "正在改写中...");
            }
          },
          onComplete: (data) => {
            console.log("[StoryAdjuster] Rewrite complete:", data);
            const newStory = (data as { new_story?: string; rewritten_story?: string }).new_story 
              || (data as { new_story?: string; rewritten_story?: string }).rewritten_story;
            if (newStory) {
              // ★ 使用 setTimeout 延迟执行，避免 "setState in render" 错误
              setTimeout(() => onRewriteComplete(newStory), 0);
            }
            showToast("success", "故事已改写");
            setInstruction("");
            setIsRewriting(false);
            // 延迟关闭 Sheet，让用户看到成功提示
            setTimeout(() => {
              onOpenChange(false);
            }, 500);
          },
          onError: (error) => {
            console.error("[StoryAdjuster] Rewrite error:", error);
            showToast("error", error.message || "改写失败，请重试");
          },
        },
        {
          signal: abortControllerRef.current.signal,
        }
      );
      
      // 检查是否成功
      if (!result.completed && !result.error) {
        console.log("[StoryAdjuster] Stream ended without completion");
      }
      
    } catch (err) {
      const error = err as { status?: number; message?: string };
      const errorMsg = String(error.message || "");
      
      // 用户取消不显示错误
      if (errorMsg.includes("abort") || errorMsg.includes("cancel")) {
        console.log("[StoryAdjuster] Request cancelled");
        return;
      }
      
      // If session expired, try to restore and retry once
      const isSessionExpired = error.status === 404 || 
        errorMsg.includes("404") || 
        errorMsg.includes("No active game session");
      
      if (!isRetry && isSessionExpired) {
        console.log("[StoryAdjuster] Session expired, attempting to restore...");
        showToast("loading", "恢复会话中...");
        try {
          await useGameStore.getState().syncState();
          console.log("[StoryAdjuster] Session restored, retrying rewrite...");
          setIsRewriting(false);
          return handleRewrite(true);
        } catch (restoreErr) {
          console.error("[StoryAdjuster] Failed to restore session:", restoreErr);
        }
      }
      console.error("Rewrite failed:", err);
      showToast("error", "改写失败，请重试");
    } finally {
      setIsRewriting(false);
      abortControllerRef.current = null;
    }
  };

  const handleRegenerate = () => {
    console.log("[StoryAdjuster] Triggering SSE regeneration...");
    // 关闭 Sheet，触发流式重新生成
    onOpenChange(false);
    onRegenerateComplete();
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="bottom" className="bg-card border-t border-border">
          <SheetHeader>
            <SheetTitle className="text-foreground">故事调整</SheetTitle>
            <SheetDescription className="text-muted-foreground">
              告诉我你希望如何修改这段故事
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-4 mt-4">
            {/* Rewrite instruction */}
            <div className="space-y-2">
              <Textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="描述你想要的修改，例如：让场景更加温馨、增加一些对话、改变结局..."
                className="min-h-[120px] bg-secondary border-border text-sm"
                disabled={isRewriting}
              />
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <Button
                onClick={() => handleRewrite()}
                disabled={!instruction.trim() || isRewriting}
                className="flex-1 touch-target"
              >
                {isRewriting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Pencil className="w-4 h-4 mr-2" />
                )}
                改写故事
              </Button>

              <Button
                variant="outline"
                onClick={handleRegenerate}
                disabled={isRewriting}
                className="touch-target"
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                重新生成
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
      
      {/* Toast notification - rendered outside Sheet so it persists after close */}
      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg ${
            toast.type === "success" 
              ? "bg-green-600 text-white" 
              : toast.type === "loading"
              ? "bg-blue-600 text-white"
              : "bg-red-600 text-white"
          }`}>
            {toast.type === "success" ? (
              <Check className="w-5 h-5" />
            ) : toast.type === "loading" ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <X className="w-5 h-5" />
            )}
            <span className="text-sm font-medium">{toast.message}</span>
          </div>
        </div>
      )}
    </>
  );
}
