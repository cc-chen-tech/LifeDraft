"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
  className?: string;
  /**
   * If true, uses serif font for narrative text
   */
  narrative?: boolean;
  /**
   * Characters to display per frame (default: 2)
   */
  charsPerFrame?: number;
  /**
   * Milliseconds between frames (default: 30)
   */
  frameInterval?: number;
}

/**
 * StreamingText — SSE 流式文字渲染
 * - 打字机效果，逐字显示
 * - 用户滚动时不自动跳到底部
 * - Serif 排版用于叙事文本
 */
export function StreamingText({
  text,
  isStreaming,
  className,
  narrative = true,
  charsPerFrame = 2,
  frameInterval = 30,
}: StreamingTextProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [displayedText, setDisplayedText] = useState("");
  const displayedLenRef = useRef(0);
  const userScrollingRef = useRef(false);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ★ 逐字显示效果（仅在 isStreaming 时启用）
  useEffect(() => {
    // ★ 关键修复：如果不是流式模式，直接显示全部文本
    if (!isStreaming) {
      if (displayedText !== text) {
        setDisplayedText(text);
        displayedLenRef.current = text.length;
      }
      return;
    }
    
    if (text.length <= displayedLenRef.current) {
      // 文本被重置或没有新内容
      if (text.length < displayedLenRef.current) {
        setDisplayedText(text);
        displayedLenRef.current = text.length;
      }
      return;
    }

    // 逐字追加
    const timer = setInterval(() => {
      if (displayedLenRef.current < text.length) {
        const nextLen = Math.min(displayedLenRef.current + charsPerFrame, text.length);
        setDisplayedText(text.slice(0, nextLen));
        displayedLenRef.current = nextLen;
      } else {
        clearInterval(timer);
      }
    }, frameInterval);

    return () => clearInterval(timer);
  }, [text, isStreaming, charsPerFrame, frameInterval, displayedText]);

  // ★ 智能自动滚动：只在用户没有手动滚动时自动滚到底部
  useEffect(() => {
    if (!containerRef.current || userScrollingRef.current) return;
    
    const el = containerRef.current;
    // 只有当用户在底部附近时才自动滚动
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    if (isNearBottom) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [displayedText]);

  // ★ 检测用户手动滚动
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleScroll = () => {
      userScrollingRef.current = true;
      // 停止滚动 1 秒后恢复自动滚动
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
      scrollTimeoutRef.current = setTimeout(() => {
        userScrollingRef.current = false;
      }, 1000);
    };

    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      el.removeEventListener("scroll", handleScroll);
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  if (!displayedText && !isStreaming) return null;

  // Split text into paragraphs
  const paragraphs = displayedText.split("\n\n").filter(Boolean);
  const stillTyping = displayedLenRef.current < text.length || isStreaming;

  return (
    <div
      ref={containerRef}
      className={cn(
        "overflow-y-auto select-text",
        narrative && "prose-story",
        className
      )}
    >
      {paragraphs.map((para, i) => (
        <p key={i} className="animate-fade-in-word">
          {para}
          {/* Show cursor on the last paragraph while typing */}
          {stillTyping && i === paragraphs.length - 1 && (
            <span className="typewriter-cursor" />
          )}
        </p>
      ))}
      {/* If no paragraphs yet but streaming, show cursor */}
      {paragraphs.length === 0 && stillTyping && (
        <p className="animate-fade-in-word">
          <span className="typewriter-cursor" />
        </p>
      )}
    </div>
  );
}
