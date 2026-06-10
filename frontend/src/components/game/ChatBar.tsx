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
import { api } from "@/lib/api";
import { streamRewrite } from "@/lib/sse";
import { useGameStore } from "@/stores/useGameStore";
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

interface LifeSummary {
  text: string;
  startWeek: number;
  endWeek: number;
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

function getSummaryWeekLabel(startWeek: number, endWeek: number): string {
  if (startWeek === endWeek) {
    return `第${startWeek}周`;
  }

  return `第${startWeek}-${endWeek}周`;
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
  onRewriteComplete?: (newStory: string) => void;
  isSaving?: boolean;
  isStoryBusy?: boolean;
  isViewingHistory?: boolean;  // ★ 是否在历史回顾模式
  className?: string;
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
  className,
}: ChatBarProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isRewriteOpen, setIsRewriteOpen] = useState(false);
  const [rewriteInstruction, setRewriteInstruction] = useState("");
  const [message, setMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isSummaryOpen, setIsSummaryOpen] = useState(false);
  const [lifeSummary, setLifeSummary] = useState<LifeSummary | null>(null);
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

  useEffect(() => {
    if (isExpanded && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isExpanded]);

  // Auto-scroll to bottom when new messages appear
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // 生成总结并显示在专用总结面板中
  const handleGenerateSummary = useCallback(async () => {
    if (!gameId || isGeneratingSummary || isStoryBusy) return;

    setIsSummaryOpen(true);
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
  }, [gameId, isGeneratingSummary, isStoryBusy]);

  const handleSend = useCallback(async () => {
    const text = message.trim();
    if (!text || !gameId || isSending) return;

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
    if (!instruction || !gameId || !fullStory || isRewriting || isStoryBusy) return;

    setIsRewriting(true);
    accumulatedStoryRef.current = "";
    rewriteAbortRef.current = new AbortController();
    setRewriteProgressMessage("正在准备改写...");
    showRewriteToast("loading", "正在准备改写...");

    const submitRewrite = () => streamRewrite(
        gameId,
        fullStory,
        instruction,
        fullStory,
        "zh",
        {
          onStory: (text) => {
            accumulatedStoryRef.current += text;
            queueMicrotask(() => {
              onRewriteComplete?.(accumulatedStoryRef.current);
            });
          },
          onStatus: (status) => {
            const message = getRewriteProgressMessage(status);
            setRewriteProgressMessage(message);
            showRewriteToast("loading", message);
          },
          onComplete: (data) => {
            const newStory =
              (data as { new_story?: string; rewritten_story?: string }).new_story ||
              (data as { new_story?: string; rewritten_story?: string }).rewritten_story;
            if (newStory) {
              setTimeout(() => onRewriteComplete?.(newStory), 0);
            }
            setRewriteInstruction("");
            setIsRewriting(false);
            showRewriteToast("success", "故事已改写");
            setTimeout(() => setIsRewriteOpen(false), 500);
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
    showRewriteToast,
    storyText,
  ]);

  if (!gameId) return null;

  const storyBusyTitle = "故事生成完成后可用";
  const storyActionDisabled = isViewingHistory || isStoryBusy;
  const rewriteDisabled = storyActionDisabled || !storyText.trim();
  const summaryDisabled = isGeneratingSummary || isSending || isStoryBusy;

  const rewriteSheet = (
    <Sheet open={isRewriteOpen} onOpenChange={setIsRewriteOpen}>
      <SheetContent
        side="bottom"
        data-testid="inline-rewrite-sheet"
        className="bg-card border-t border-border"
      >
        <SheetHeader>
          <SheetTitle className="text-foreground">故事调整</SheetTitle>
          <SheetDescription className="text-muted-foreground">
            告诉我你希望如何修改这段故事
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-4 mt-4">
          <Textarea
            value={rewriteInstruction}
            onChange={(e) => setRewriteInstruction(e.target.value)}
            placeholder="描述你想要的修改，例如：让场景更加温馨、增加一些对话、改变结局..."
            className="min-h-[120px] bg-secondary border-border text-sm"
            disabled={isRewriting}
          />
          <Button
            onClick={() => handleRewrite()}
            disabled={!rewriteInstruction.trim() || isRewriting || !storyText.trim() || isStoryBusy}
            className="w-full touch-target"
          >
            {isRewriting ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Pencil className="w-4 h-4 mr-2" />
            )}
            改写故事
          </Button>
          {isRewriting && rewriteProgressMessage && (
            <p
              aria-live="polite"
              className="text-xs text-muted-foreground"
              data-testid="rewrite-progress-message"
            >
              {rewriteProgressMessage}
            </p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );

  const rewriteToastNode = rewriteToast && (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div className={cn(
        "flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white",
        rewriteToast.type === "success"
          ? "bg-green-600"
          : rewriteToast.type === "loading"
          ? "bg-blue-600"
          : "bg-red-600"
      )}>
        {rewriteToast.type === "success" ? (
          <Check className="w-5 h-5" />
        ) : rewriteToast.type === "loading" ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <X className="w-5 h-5" />
        )}
        <span className="text-sm font-medium">{rewriteToast.message}</span>
      </div>
    </div>
  );

  const lifeSummaryPanel = isSummaryOpen && (
    <section
      data-testid="life-summary-panel"
      aria-label="人生总结"
      className={cn(
        "fixed bottom-20 left-4 right-4 sm:left-auto sm:w-[min(28rem,calc(100vw-2rem))] max-w-md z-50",
        "bg-card/95 backdrop-blur-sm border border-border shadow-xl rounded-lg",
        "p-4 safe-area-pb",
        className
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-4 h-4 text-primary" />
        <h2 className="text-sm font-semibold text-foreground">人生总结</h2>
        <div className="flex-1" />
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={() => setIsSummaryOpen(false)}
          aria-label="关闭人生总结"
          title="关闭人生总结"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      <div className="max-h-[320px] overflow-y-auto text-sm text-muted-foreground">
        {isGeneratingSummary ? (
          <div className="flex items-center gap-2 rounded-lg bg-secondary px-3 py-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            正在生成总结...
          </div>
        ) : lifeSummaryError ? (
          <div className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">
            {lifeSummaryError}
          </div>
        ) : lifeSummary ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              {getSummaryWeekLabel(lifeSummary.startWeek, lifeSummary.endWeek)}
            </p>
            <div className="prose prose-sm prose-invert max-w-none text-muted-foreground">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {lifeSummary.text}
              </ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-secondary px-3 py-2">暂无总结内容</div>
        )}
      </div>
    </section>
  );

  if (!isExpanded) {
    return (
      <>
        <div
          data-testid="chat-bar-launcher"
          className={cn(
            "fixed bottom-4 right-4 z-50 flex flex-wrap justify-end items-center gap-2 pointer-events-none",
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
            重新生成
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
                : "改写当前故事"
            }
          >
            <Pencil className="w-3 h-3 mr-1" />
            改写
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
    <div
      data-testid="chat-bar-panel"
      className={cn(
        "fixed bottom-4 left-4 right-4 sm:left-auto sm:w-[min(28rem,calc(100vw-2rem))] max-w-md z-50",
        "bg-card/95 backdrop-blur-sm border border-border shadow-xl rounded-lg",
        "p-3 safe-area-pb",
        className
      )}
    >
      {/* Quick actions row */}
      <div className="flex items-center gap-2 mb-2">
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
              : undefined
          }
        >
          <Pencil className="w-3 h-3 mr-1" />
          改写
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
          重新生成
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

        <div className="flex-1" />

        {chatHistory.length > 0 && (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground"
            onClick={() => setChatHistory([])}
            title="清空对话"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        )}

        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={() => setIsExpanded(false)}
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
              className={cn(
                "text-sm rounded-lg px-3 py-2 max-w-[85%]",
                msg.role === "user"
                  ? "bg-primary/20 text-foreground ml-auto"
                  : "bg-secondary text-muted-foreground prose prose-sm prose-invert max-w-none"
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
            <div className="bg-secondary text-muted-foreground text-sm rounded-lg px-3 py-2 max-w-[85%] flex items-center gap-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              {isGeneratingSummary ? "正在生成总结..." : "思考中..."}
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      )}

      {/* Input row */}
      <div className="flex gap-2">
        <Input
          ref={inputRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="向剧情助手提问..."
          className="flex-1 bg-secondary border-border text-sm h-10"
          disabled={isSending}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing && message.trim()) {
              handleSend();
            }
          }}
        />
        <Button
          size="icon"
          className="h-10 w-10"
          disabled={!message.trim() || isSending}
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
      {rewriteSheet}
      {lifeSummaryPanel}
      {rewriteToastNode}
    </div>
  );
}
