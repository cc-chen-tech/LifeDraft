"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { FeedbackNotice, FormField, Surface } from "@/components/story101";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";
import { api } from "@/lib/api";
import { streamRewrite } from "@/lib/sse";
import { useGameStore } from "@/stores/useGameStore";
import type { EventOption } from "@/lib/types";
import { LifeSummaryPanel, type LifeSummaryData } from "./LifeSummaryPanel";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  MessageCircle,
  X,
  Send,
  Loader2,
  Pencil,
  RotateCcw,
  Save,
  Trash2,
  FileText,
  Check,
} from "lucide-react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

function normalizeSummaryWeek(value: number | undefined, fallback: number): number {
  const num = Math.trunc(Number(value));
  if (!Number.isFinite(num) || Number.isNaN(num) || num <= 0) {
    return fallback;
  }
  return num;
}

function normalizeSummaryWeeks(startWeek: number | undefined, endWeek: number | undefined): {
  startWeek: number;
  endWeek: number;
} {
  const normalizedStart = normalizeSummaryWeek(startWeek, 1);
  const normalizedEnd = normalizeSummaryWeek(endWeek, normalizedStart);

  return {
    startWeek: normalizedStart,
    endWeek: Math.max(normalizedStart, normalizedEnd),
  };
}

function getRewriteProgressMessage(status: { phase?: string; message?: string }): string {
  const message = status.message?.trim();
  if (message) return message;

  switch (status.phase) {
    case "analyzing":
      return "正在理解改写要求";
    case "rewriting":
      return "正在生成改写文本";
    case "validating":
      return "正在检查故事一致性";
    case "finalizing":
      return "正在整理改写结果";
    default:
      return "正在改写中...";
  }
}

interface ChatBarProps {
  gameId: number | null;
  onSave?: () => void;
  onRegenerate?: () => void;
  storyText?: string;
  onRewriteComplete?: (newStory: string, event?: {
    event_id?: string;
    revision?: number;
    story_date?: string;
    options?: EventOption[];
  }) => void;
  isSaving?: boolean;
  isStoryBusy?: boolean;
  isViewingHistory?: boolean;  // ★ 是否在历史回顾模式
  showLauncher?: boolean;
  command?: ChatBarCommand | null;
  onSurfaceOpenChange?: (open: boolean) => void;
  isDailyTimeline?: boolean;
  className?: string;
}

export type ChatBarAction = "chat" | "rewrite" | "summary" | "close";

export interface ChatBarCommand {
  id: number;
  action: ChatBarAction;
}

/**
 * ChatBar — 底部固定剧情助手 chat bar
 * - 收起态：小圆按钮
 * - 展开态：快捷操作 + 聊天消息 + 输入框
 * - Mobile-first sticky bottom
 */
export function ChatBar({
  gameId,
  onSave,
  onRegenerate,
  storyText = "",
  onRewriteComplete,
  isSaving = false,
  isStoryBusy = false,
  isViewingHistory = false,
  showLauncher = true,
  command = null,
  onSurfaceOpenChange,
  isDailyTimeline = false,
  className,
}: ChatBarProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isRewriteOpen, setIsRewriteOpen] = useState(false);
  const [rewriteInstruction, setRewriteInstruction] = useState("");
  const [message, setMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isSummaryOpen, setIsSummaryOpen] = useState(false);
  const [lifeSummary, setLifeSummary] = useState<LifeSummaryData | null>(null);
  const [lifeSummaryError, setLifeSummaryError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [isRewriting, setIsRewriting] = useState(false);
  const [rewriteProgressMessage, setRewriteProgressMessage] = useState("");
  const [rewriteToast, setRewriteToast] = useState<{
    type: "success" | "error" | "loading";
    message: string;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const rewriteAbortRef = useRef<AbortController | null>(null);
  const accumulatedStoryRef = useRef("");
  const handledCommandIdRef = useRef<number | null>(null);
  const surfaceReturnFocusRef = useRef<HTMLElement | null>(null);
  const reportedSurfaceOpenRef = useRef(false);

  const fullStoryOverLimit = !isWithinInputLimit(
    storyText,
    INPUT_LIMITS.fullStory,
  );
  const rewriteDisabled =
    isViewingHistory ||
    isStoryBusy ||
    !storyText.trim() ||
    fullStoryOverLimit;

  const captureSurfaceReturnFocus = useCallback(() => {
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLElement &&
      activeElement !== document.body
    ) {
      surfaceReturnFocusRef.current = activeElement;
    }
  }, []);

  const reportUnifiedSurfaceOpen = useCallback(
    (open: boolean) => {
      if (showLauncher || reportedSurfaceOpenRef.current === open) return;
      reportedSurfaceOpenRef.current = open;
      onSurfaceOpenChange?.(open);
    },
    [onSurfaceOpenChange, showLauncher],
  );

  const restoreSurfaceFocus = useCallback(() => {
    const returnTarget = surfaceReturnFocusRef.current;
    surfaceReturnFocusRef.current = null;
    queueMicrotask(() => returnTarget?.focus());
  }, []);

  const closeAssistantSurfaces = useCallback(() => {
    if (!showLauncher && isRewriting) {
      setIsExpanded(false);
      setIsSummaryOpen(false);
      return;
    }

    const activeElement = document.activeElement;
    const focusIsInsideAssistantSurface =
      activeElement instanceof HTMLElement &&
      [
        document.querySelector('[data-testid="chat-bar-panel"]'),
        document.querySelector('[data-testid="inline-rewrite-sheet"]'),
        document.querySelector('[data-testid="life-summary-panel"]'),
      ].some((surface) => surface?.contains(activeElement));
    const shouldRestoreFocus =
      !showLauncher &&
      focusIsInsideAssistantSurface &&
      Boolean(surfaceReturnFocusRef.current);

    if (!shouldRestoreFocus) {
      surfaceReturnFocusRef.current = null;
    }
    setIsExpanded(false);
    setIsRewriteOpen(false);
    setIsSummaryOpen(false);
    if (shouldRestoreFocus) restoreSurfaceFocus();
  }, [isRewriting, restoreSurfaceFocus, showLauncher]);

  const unifiedSurfaceOpen =
    !showLauncher && (isExpanded || isRewriteOpen || isSummaryOpen);

  useEffect(() => {
    reportUnifiedSurfaceOpen(unifiedSurfaceOpen);
  }, [reportUnifiedSurfaceOpen, unifiedSurfaceOpen]);

  useEffect(
    () => () => {
      if (!reportedSurfaceOpenRef.current) return;
      reportedSurfaceOpenRef.current = false;
      onSurfaceOpenChange?.(false);
    },
    [onSurfaceOpenChange],
  );

  useEffect(() => {
    if (isExpanded && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isExpanded]);

  // Auto-scroll to bottom when new messages appear
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  useEffect(() => {
    if (!isStoryBusy && !isViewingHistory) return;

    closeAssistantSurfaces();
  }, [closeAssistantSurfaces, isStoryBusy, isViewingHistory]);

  // 生成总结并显示在专用总结面板中
  const handleGenerateSummary = useCallback(async () => {
    if (!gameId || isStoryBusy) return;

    reportUnifiedSurfaceOpen(true);
    setIsSummaryOpen(true);
    if (isGeneratingSummary) return;

    setLifeSummaryError(null);
    setIsGeneratingSummary(true);
    
    try {
      const result = await api.gameplay.generateSummary(gameId, { weeks: 52 });
      const summaryData = result as { summary_text?: string; summary?: string; start_week?: number; end_week?: number };
      const summaryText = summaryData.summary_text || summaryData.summary || "暂无总结内容";
      const { startWeek, endWeek } = normalizeSummaryWeeks(
        summaryData.start_week,
        summaryData.end_week
      );

      setLifeSummary({ text: summaryText, startWeek, endWeek });
    } catch (err) {
      console.error("Generate summary failed:", err);
      setLifeSummaryError("生成总结时出了点问题，请稍后再试。");
    } finally {
      setIsGeneratingSummary(false);
    }
  }, [gameId, isGeneratingSummary, isStoryBusy, reportUnifiedSurfaceOpen]);

  useEffect(() => {
    if (!command || handledCommandIdRef.current === command.id) return;

    handledCommandIdRef.current = command.id;
    if (command.action === "close") {
      closeAssistantSurfaces();
      return;
    }

    if (isStoryBusy || isViewingHistory) return;
    if (command.action === "rewrite" && rewriteDisabled) return;

    reportUnifiedSurfaceOpen(true);
    captureSurfaceReturnFocus();

    if (command.action === "chat") {
      setIsRewriteOpen(false);
      setIsSummaryOpen(false);
      setIsExpanded(true);
      return;
    }

    setIsExpanded(false);
    if (command.action === "rewrite") {
      setIsSummaryOpen(false);
      setIsRewriteOpen(true);
      return;
    }

    setIsRewriteOpen(false);
    void handleGenerateSummary();
  }, [
    captureSurfaceReturnFocus,
    closeAssistantSurfaces,
    command,
    handleGenerateSummary,
    isStoryBusy,
    isViewingHistory,
    reportUnifiedSurfaceOpen,
    rewriteDisabled,
  ]);

  const handleSend = useCallback(async () => {
    const text = message.trim();
    if (
      !text ||
      !gameId ||
      isSending ||
      !isWithinInputLimit(text, INPUT_LIMITS.storyDialogue)
    ) return;

    // Add user message
    const userMsg: ChatMessage = { role: "user", content: text };
    setChatHistory((prev) => [...prev, userMsg]);
    setMessage("");
    setIsSending(true);

    const tryChat = async (isRetry = false): Promise<void> => {
      try {
        const result = await api.story.chat(gameId, { message: text });
        const assistantMsg: ChatMessage = {
          role: "assistant",
          content: result.reply || "抱歉，暂时无法回答。",
        };
        setChatHistory((prev) => [...prev, assistantMsg]);
      } catch (err) {
        const error = err as { status?: number; message?: string };
        const errorMsg = String(error.message || "");
        // If session expired (404 or "No active game session"), try to restore and retry once
        const isSessionExpired = error.status === 404 || 
          errorMsg.includes("404") || 
          errorMsg.includes("No active game session");
        
        if (!isRetry && isSessionExpired) {
          console.log("[ChatBar] Session expired, attempting to restore...");
          try {
            await useGameStore.getState().syncState();
            console.log("[ChatBar] Session restored, retrying chat...");
            return tryChat(true);
          } catch (restoreErr) {
            console.error("[ChatBar] Failed to restore session:", restoreErr);
          }
        }
        console.error("Chat failed:", err);
        setChatHistory((prev) => [
          ...prev,
          { role: "assistant", content: "抱歉，出了点问题，请稍后再试。" },
        ]);
      }
    };

    await tryChat();
    setIsSending(false);
    // Re-focus input
    setTimeout(() => inputRef.current?.focus(), 100);
  }, [message, gameId, isSending]);

  const showRewriteToast = useCallback((type: "success" | "error" | "loading", message: string) => {
    setRewriteToast({ type, message });
    if (type !== "loading") {
      setTimeout(() => setRewriteToast(null), 3000);
    }
  }, []);

  const handleRewrite = useCallback(async (): Promise<void> => {
    const instruction = rewriteInstruction.trim();
    const fullStory = storyText.trim();
    if (
      !instruction ||
      !gameId ||
      !fullStory ||
      isRewriting ||
      isStoryBusy ||
      !isWithinInputLimit(instruction, INPUT_LIMITS.rewriteInstruction) ||
      !isWithinInputLimit(fullStory, INPUT_LIMITS.fullStory)
    ) return;

    setIsRewriting(true);
    accumulatedStoryRef.current = "";
    rewriteAbortRef.current = new AbortController();
    setRewriteProgressMessage("正在准备改写...");
    showRewriteToast("loading", "正在准备改写...");

    const submitRewrite = () => streamRewrite(
        gameId,
        fullStory,
        instruction,
        "",
        "zh",
        {
          onStory: (text) => {
            accumulatedStoryRef.current += text;
            queueMicrotask(() => {
              onRewriteComplete?.(accumulatedStoryRef.current);
            });
          },
          onStatus: (status) => {
            if (status.phase === "retry") {
              // The server discards the prior attempt before streaming a replacement.
              accumulatedStoryRef.current = "";
            }
            const message = getRewriteProgressMessage(status);
            setRewriteProgressMessage(message);
            showRewriteToast("loading", message);
          },
          onComplete: (data) => {
            const payload = data as {
              new_story?: string;
              rewritten_story?: string;
              event?: {
                event_id?: string;
                revision?: number;
                story_date?: string;
                options?: EventOption[];
              };
            };
            const newStory = payload.new_story || payload.rewritten_story;
            if (newStory) {
              setTimeout(() => onRewriteComplete?.(newStory, payload.event), 0);
            }
            setRewriteInstruction("");
            setIsRewriting(false);
            showRewriteToast("success", "故事已改写");
            if (showLauncher) {
              setTimeout(() => setIsRewriteOpen(false), 500);
            }
          },
          onError: (error) => {
            setRewriteProgressMessage("");
            showRewriteToast("error", error.message || "改写失败，请重试");
          },
          onReconnecting: (attempt, maxRetries) => {
            const message = `连接中断，正在重试 ${attempt}/${maxRetries}`;
            setRewriteProgressMessage(message);
            showRewriteToast("loading", message);
          },
        },
        { signal: rewriteAbortRef.current?.signal }
      );

    try {
      const result = await submitRewrite();
      if (!result.completed && !result.error) {
        setRewriteProgressMessage("");
        showRewriteToast("error", "改写未完成，请重试");
      }
    } catch (err) {
      const error = err as { status?: number; message?: string };
      const errorMsg = String(error.message || "");

      if (errorMsg.includes("abort") || errorMsg.includes("cancel")) {
        return;
      }

      const isSessionExpired =
        error.status === 404 ||
        errorMsg.includes("404") ||
        errorMsg.includes("No active game session");

      if (isSessionExpired) {
        showRewriteToast("loading", "恢复会话中...");
        try {
          await useGameStore.getState().syncState();
          const result = await submitRewrite();
          if (!result.completed && !result.error) {
            setRewriteProgressMessage("");
            showRewriteToast("error", "改写未完成，请重试");
          }
          return;
        } catch (restoreErr) {
          console.error("[ChatBar] Failed to restore session:", restoreErr);
        }
      }

      setRewriteProgressMessage("");
      showRewriteToast("error", "改写失败，请重试");
    } finally {
      setIsRewriting(false);
      rewriteAbortRef.current = null;
    }
  }, [
    gameId,
    isRewriting,
    isStoryBusy,
    onRewriteComplete,
    rewriteInstruction,
    showLauncher,
    showRewriteToast,
    storyText,
  ]);

  if (!gameId || isStoryBusy || isViewingHistory) return null;

  const storyBusyTitle = "故事生成完成后可用";
  const storyActionDisabled = isViewingHistory || isStoryBusy;
  const summaryDisabled = isGeneratingSummary || isSending || isStoryBusy;

  const rewriteSheet = (
    <Sheet
      open={isRewriteOpen}
      onOpenChange={(open) => {
        if (!open && !showLauncher && isRewriting) return;
        setIsRewriteOpen(open);
      }}
    >
      <SheetContent
        side="bottom"
        data-testid="inline-rewrite-sheet"
        showCloseButton={false}
        overlayClassName="z-[60]"
        className="z-[61] max-h-[88dvh] gap-0 overflow-y-auto rounded-t-[var(--radius-overlay)] border-[var(--border-default)] bg-[var(--surface-overlay)] p-0"
        onCloseAutoFocus={(event) => {
          if (!showLauncher) {
            event.preventDefault();
            if (surfaceReturnFocusRef.current) restoreSurfaceFocus();
          }
        }}
      >
        <SheetHeader className="border-b border-[var(--border-default)] px-5 py-4 pr-16 text-left">
          <SheetTitle className="text-[var(--text-primary)]">故事调整</SheetTitle>
          <SheetDescription className="text-[var(--text-secondary)]">
            告诉我你希望如何修改这段故事
          </SheetDescription>
        </SheetHeader>
        <Button
          type="button"
          variant="quiet"
          size="icon-touch"
          className="absolute right-3 top-3"
          aria-label="关闭故事调整"
          aria-busy={!showLauncher && isRewriting ? true : undefined}
          disabled={!showLauncher && isRewriting}
          onClick={() => setIsRewriteOpen(false)}
        >
          <X className="h-4 w-4" />
        </Button>

        <div className="space-y-4 px-5 pb-[max(1.25rem,var(--safe-area-inset-bottom))] pt-5">
          <FormField
            id="story-rewrite-instruction"
            label="改写要求"
            description="说明想保留和调整的部分。"
            error={
              isWithinInputLimit(rewriteInstruction, INPUT_LIMITS.rewriteInstruction)
                ? undefined
                : `改写要求不能超过 ${INPUT_LIMITS.rewriteInstruction} 字`
            }
          >
            {({ describedBy, invalid }) => (
              <>
                <Textarea
                  id="story-rewrite-instruction"
                  value={rewriteInstruction}
                  onChange={(e) => setRewriteInstruction(e.target.value)}
                  placeholder="描述你想要的修改，例如：让场景更温暖、增加对话或调整节奏"
                  surface="filled"
                  controlSize="touch"
                  className="min-h-[120px] text-sm"
                  disabled={isRewriting}
                  aria-invalid={invalid}
                  aria-describedby={[
                    describedBy,
                    "story-rewrite-instruction-count",
                  ].filter(Boolean).join(" ")}
                />
                <LengthIndicator
                  id="story-rewrite-instruction-count"
                  value={rewriteInstruction}
                  limit={INPUT_LIMITS.rewriteInstruction}
                  announce={false}
                />
              </>
            )}
          </FormField>
          <Button
            type="button"
            variant="narrative"
            size="touch"
            onClick={() => handleRewrite()}
            disabled={
              !rewriteInstruction.trim() ||
              isRewriting ||
              rewriteDisabled ||
              !isWithinInputLimit(rewriteInstruction, INPUT_LIMITS.rewriteInstruction)
            }
            className="w-full"
          >
            {isRewriting ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Pencil className="w-4 h-4 mr-2" />
            )}
            改写故事
          </Button>
          {!showLauncher && rewriteToast && (
            <FeedbackNotice
              tone={
                rewriteToast.type === "success"
                  ? "success"
                  : rewriteToast.type === "loading"
                    ? "info"
                    : "danger"
              }
            >
              <span
                className="flex items-center gap-2"
                data-testid={
                  rewriteToast.type === "loading"
                    ? "rewrite-progress-message"
                    : undefined
                }
              >
                {rewriteToast.type === "success" ? (
                  <Check className="h-4 w-4" />
                ) : rewriteToast.type === "loading" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <X className="h-4 w-4" />
                )}
                {rewriteToast.type === "loading" && rewriteProgressMessage
                  ? rewriteProgressMessage
                  : rewriteToast.message}
              </span>
            </FeedbackNotice>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );

  const rewriteToastNode = rewriteToast && showLauncher && (
    <div className="play-feedback fixed left-1/2 z-[80] w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2">
      <FeedbackNotice
        tone={
          rewriteToast.type === "success"
            ? "success"
            : rewriteToast.type === "loading"
              ? "info"
              : "danger"
        }
      >
        <span className="flex items-center gap-2">
        {rewriteToast.type === "success" ? (
          <Check className="h-4 w-4" />
        ) : rewriteToast.type === "loading" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <X className="h-4 w-4" />
        )}
          <span className="text-sm font-medium">{rewriteToast.message}</span>
        </span>
      </FeedbackNotice>
    </div>
  );

  const lifeSummaryPanel = isSummaryOpen && (
    <LifeSummaryPanel
      summary={lifeSummary}
      isLoading={isGeneratingSummary}
      error={lifeSummaryError}
      onClose={() => {
        setIsSummaryOpen(false);
        if (!showLauncher) restoreSurfaceFocus();
      }}
      className={className}
    />
  );

  if (!isExpanded) {
    if (!showLauncher) {
      return (
        <>
          {rewriteSheet}
          {lifeSummaryPanel}
          {rewriteToastNode}
        </>
      );
    }

    return (
      <>
        <div
          data-testid="chat-bar-launcher"
          className={cn(
            "fixed bottom-4 right-4 z-50 flex flex-wrap justify-end items-center gap-2 pointer-events-none animate-in fade-in duration-200",
            "max-w-[calc(100vw-2rem)]",
            className
          )}
        >
          <Button
            size="sm"
            variant="outline"
            className="h-10 px-3 text-xs shadow-lg bg-card/95 backdrop-blur-sm pointer-events-auto"
            onClick={() => onRegenerate?.()}
            disabled={storyActionDisabled}
            title={
              isStoryBusy
                ? storyBusyTitle
                : isViewingHistory
                ? "历史回顾模式下不可用"
                : "重新生成当前故事"
            }
          >
            <RotateCcw className="w-3 h-3 mr-1" />
            {isDailyTimeline ? "重新生成今天" : "重新生成"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            data-testid="rewrite-button"
            className="h-10 px-3 text-xs shadow-lg bg-card/95 backdrop-blur-sm pointer-events-auto"
            onClick={() => setIsRewriteOpen(true)}
            disabled={rewriteDisabled}
            title={
              isStoryBusy
                ? storyBusyTitle
                : isViewingHistory
                ? "历史回顾模式下不可用"
                : !storyText.trim()
                ? "暂无可改写的故事"
                : fullStoryOverLimit
                ? `当前故事超过 ${INPUT_LIMITS.fullStory} 字，无法提交改写`
                : "改写当前故事"
            }
          >
            <Pencil className="w-3 h-3 mr-1" />
            {isDailyTimeline ? "改写今天" : "改写"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-10 px-3 text-xs shadow-lg bg-card/95 backdrop-blur-sm pointer-events-auto"
            onClick={() => void handleGenerateSummary()}
            disabled={summaryDisabled}
            title={isStoryBusy ? storyBusyTitle : "生成人生总结"}
          >
            {isGeneratingSummary ? (
              <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            ) : (
              <FileText className="w-3 h-3 mr-1" />
            )}
            人生总结
          </Button>
          <Button
            size="icon"
            aria-label="打开聊天"
            className="h-12 w-12 rounded-full shadow-lg bg-primary hover:bg-primary/90 pointer-events-auto"
            onClick={() => setIsExpanded(true)}
          >
            <MessageCircle className="w-5 h-5" />
          </Button>
        </div>
        {rewriteSheet}
        {lifeSummaryPanel}
        {rewriteToastNode}
      </>
    );
  }

  return (
    <Surface asChild variant="overlay">
    <div
      data-testid="chat-bar-panel"
      data-presentation={showLauncher ? "legacy" : "unified"}
      className={cn(
        "fixed left-4 right-4 z-[70] max-w-md p-3 safe-area-pb sm:left-auto sm:w-[min(28rem,calc(100vw-2rem))]",
        showLauncher ? "bottom-4" : "play-chat-surface",
        className
      )}
    >
      {/* Quick actions row */}
      <div className="flex items-center gap-2 mb-2">
        {!showLauncher && (
          <h2 className="text-sm font-medium text-[var(--text-primary)]">
            剧情助手
          </h2>
        )}
        {showLauncher && (
          <>
        <Button
          size="sm"
          variant="outline"
          className="text-xs touch-target"
          onClick={onSave}
          disabled={isSaving}
        >
          {isSaving ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <Save className="w-3 h-3 mr-1" />
          )}
          保存
        </Button>

        <Button
          size="sm"
          variant="outline"
          data-testid="rewrite-button"
          className="text-xs touch-target"
          onClick={() => setIsRewriteOpen(true)}
          disabled={rewriteDisabled}
          title={
            isStoryBusy
              ? storyBusyTitle
              : isViewingHistory
              ? "历史回顾模式下不可用"
              : !storyText.trim()
              ? "暂无可改写的故事"
              : fullStoryOverLimit
              ? `当前故事超过 ${INPUT_LIMITS.fullStory} 字，无法提交改写`
              : undefined
          }
        >
          <Pencil className="w-3 h-3 mr-1" />
          {isDailyTimeline ? "改写今天" : "改写"}
        </Button>

        <Button
          size="sm"
          variant="outline"
          className="text-xs touch-target"
          onClick={() => {
            console.log("[ChatBar] Triggering SSE regeneration...");
            onRegenerate?.();
          }}
          disabled={storyActionDisabled}
          title={
            isStoryBusy
              ? storyBusyTitle
              : isViewingHistory
              ? "历史回顾模式下不可用"
              : undefined
          }
        >
          <RotateCcw className="w-3 h-3 mr-1" />
          {isDailyTimeline ? "重新生成今天" : "重新生成"}
        </Button>

        <Button
          size="sm"
          variant="outline"
          className="text-xs touch-target"
          onClick={() => void handleGenerateSummary()}
          disabled={summaryDisabled}
          title={isStoryBusy ? storyBusyTitle : "生成人生总结"}
        >
          {isGeneratingSummary ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <FileText className="w-3 h-3 mr-1" />
          )}
          人生总结
        </Button>
          </>
        )}

        <div className="flex-1" />

        {chatHistory.length > 0 && (
          <Button
            size={showLauncher ? "icon" : "icon-touch"}
            variant={showLauncher ? "ghost" : "quiet"}
            className={cn(showLauncher && "h-8 w-8 text-muted-foreground")}
            onClick={() => setChatHistory([])}
            aria-label="清空对话"
            title="清空对话"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        )}

        <Button
          size={showLauncher ? "icon" : "icon-touch"}
          variant={showLauncher ? "ghost" : "quiet"}
          className={cn(showLauncher && "h-8 w-8")}
          onClick={() => {
            setIsExpanded(false);
            if (!showLauncher) restoreSurfaceFocus();
          }}
          aria-label="关闭剧情助手"
          title="关闭剧情助手"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Chat messages */}
      {chatHistory.length > 0 && (
        <div className="max-h-[200px] overflow-y-auto mb-2 space-y-2 px-1">
          {chatHistory.map((msg, i) => (
            <div
              key={i}
              data-slot={showLauncher ? undefined : "chat-message"}
              className={cn(
                "text-sm",
                showLauncher
                  ? "max-w-[85%] rounded-lg px-3 py-2"
                  : "max-w-none rounded-none border-b border-[var(--border-default)] bg-transparent px-0 py-3",
                msg.role === "user"
                  ? showLauncher
                    ? "ml-auto bg-primary/20 text-foreground"
                    : "text-[var(--text-primary)]"
                  : showLauncher
                    ? "bg-secondary text-muted-foreground prose prose-sm prose-invert max-w-none"
                    : "prose-story max-w-none text-[var(--text-secondary)]",
              )}
            >
              {msg.role === "user" ? (
                msg.content
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              )}
            </div>
          ))}
          {(isSending || isGeneratingSummary) && (
            <div
              className={cn(
                "flex items-center gap-2 text-sm",
                showLauncher
                  ? "max-w-[85%] rounded-lg bg-secondary px-3 py-2 text-muted-foreground"
                  : "max-w-none rounded-none border-b border-[var(--border-default)] bg-transparent px-0 py-3 text-[var(--text-secondary)]",
              )}
            >
              <Loader2 className="w-3 h-3 animate-spin" />
              {isGeneratingSummary ? "正在生成总结..." : "思考中..."}
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      )}

      {/* Input row */}
      <FormField
        id="story-assistant-question"
        label="剧情助手问题"
        error={
          isWithinInputLimit(message, INPUT_LIMITS.storyDialogue)
            ? undefined
            : `问题不能超过 ${INPUT_LIMITS.storyDialogue} 字`
        }
      >
        {({ describedBy, invalid }) => (
          <>
            <div className="flex gap-2">
              <Input
                id="story-assistant-question"
                ref={inputRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="向剧情助手提问..."
                surface={showLauncher ? "default" : "filled"}
                controlSize={showLauncher ? "default" : "touch"}
                className={cn("flex-1 text-sm", showLauncher && "h-10 bg-secondary border-border")}
                disabled={isSending}
                aria-invalid={invalid}
                aria-describedby={[
                  describedBy,
                  "story-assistant-question-count",
                ].filter(Boolean).join(" ")}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.nativeEvent.isComposing && message.trim()) {
                    handleSend();
                  }
                }}
              />
              <Button
                type="button"
                size={showLauncher ? "icon" : "icon-touch"}
                variant={showLauncher ? "default" : "narrative"}
                className={cn(showLauncher && "h-10 w-10")}
                disabled={
                  !message.trim() ||
                  isSending ||
                  !isWithinInputLimit(message, INPUT_LIMITS.storyDialogue)
                }
                onClick={handleSend}
                aria-label="发送消息"
                title="发送消息"
              >
                {isSending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>
            <LengthIndicator
              id="story-assistant-question-count"
              value={message}
              limit={INPUT_LIMITS.storyDialogue}
              announce={false}
            />
          </>
        )}
      </FormField>
      {rewriteSheet}
      {lifeSummaryPanel}
      {rewriteToastNode}
    </div>
    </Surface>
  );
}
