"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
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
} from "lucide-react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatBarProps {
  gameId: number | null;
  onSave?: () => void;
  onAdjustStory?: () => void;
  onRegenerate?: () => void;
  isSaving?: boolean;
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
  onAdjustStory,
  onRegenerate,
  isSaving = false,
  isViewingHistory = false,
  className,
}: ChatBarProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [message, setMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isExpanded && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isExpanded]);

  // Auto-scroll to bottom when new messages appear
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // 生成总结并显示在对话框中
  const handleGenerateSummary = useCallback(async () => {
    if (!gameId || isGeneratingSummary) return;
    
    setIsGeneratingSummary(true);
    
    // 添加用户请求消息
    const userMsg: ChatMessage = { role: "user", content: "请总结我的人生故事" };
    setChatHistory((prev) => [...prev, userMsg]);
    
    try {
      const result = await api.gameplay.generateSummary(gameId, { weeks: 52 });
      const summaryData = result as { summary_text?: string; summary?: string; start_week?: number; end_week?: number };
      const summaryText = summaryData.summary_text || summaryData.summary || "暂无总结内容";
      const startWeek = summaryData.start_week || 1;
      const endWeek = summaryData.end_week || 0;
      
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: `📊 **人生总结（第${startWeek}-${endWeek}周）**\n\n${summaryText}`,
      };
      setChatHistory((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error("Generate summary failed:", err);
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: "抱歉，生成总结时出了点问题，请稍后再试。" },
      ]);
    } finally {
      setIsGeneratingSummary(false);
    }
  }, [gameId, isGeneratingSummary]);

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

  if (!gameId) return null;

  if (!isExpanded) {
    return (
      <div
        className={cn(
          "fixed bottom-14 right-4 z-50 flex items-center gap-2",
          className
        )}
      >
        <Button
          size="icon"
          className="h-12 w-12 rounded-full shadow-lg bg-primary hover:bg-primary/90"
          onClick={() => setIsExpanded(true)}
          aria-label="打开聊天"
        >
          <MessageCircle className="w-5 h-5" />
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "fixed bottom-12 left-0 right-0 z-50",
        "bg-card/95 backdrop-blur-sm border-t border-border",
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
          onClick={() => {
            console.log("[ChatBar] Triggering SSE regeneration...");
            onRegenerate?.();
          }}
          disabled={isViewingHistory}
          title={isViewingHistory ? "历史回顾模式下不可用" : undefined}
        >
          <RotateCcw className="w-3 h-3 mr-1" />
          重新生成
        </Button>

        <Button
          size="sm"
          variant="outline"
          className="text-xs touch-target"
          onClick={() => onAdjustStory?.()}
          disabled={isViewingHistory}
          title={isViewingHistory ? "历史回顾模式下不可用" : undefined}
        >
          <Pencil className="w-3 h-3 mr-1" />
          改写
        </Button>

        <Button
          size="sm"
          variant="outline"
          className="text-xs touch-target"
          onClick={handleGenerateSummary}
          disabled={isGeneratingSummary || isSending}
        >
          {isGeneratingSummary ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <FileText className="w-3 h-3 mr-1" />
          )}
          总结
        </Button>

        <div className="flex-1" />

        {chatHistory.length > 0 && (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground"
            onClick={() => setChatHistory([])}
            title="清空对话"
            aria-label="清空对话"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        )}

        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={() => setIsExpanded(false)}
          title="关闭聊天"
          aria-label="关闭聊天"
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
          title="发送消息"
          aria-label="发送消息"
        >
          {isSending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>
    </div>
  );
}
