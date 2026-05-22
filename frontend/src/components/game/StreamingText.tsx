"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  const prevIsStreamingRef = useRef(isStreaming);

  // ★ 逐字显示效果
  // 关键修复：isStreaming 从 true 变为 false 时，如果打字机还没打完，
  // 不瞬间显示全部文本（避免"闪一下"），而是继续打字直到追平。
  // 其他情况（初始渲染非流式、新文本非流式）仍立即显示完整文本。
  useEffect(() => {
    const justStoppedStreaming =
      prevIsStreamingRef.current && !isStreaming;
    const midTyping =
      displayedLenRef.current > 0 &&
      displayedLenRef.current < text.length;
    prevIsStreamingRef.current = isStreaming;

    // 非流式且不是"刚停止流式且正在打字中"：立即显示全部
    if (!isStreaming && !(justStoppedStreaming && midTyping)) {
      setDisplayedText(text);
      displayedLenRef.current = text.length;
      return;
    }

    if (text.length < displayedLenRef.current) {
      // 文本被重置
      setDisplayedText(text);
      displayedLenRef.current = text.length;
      return;
    }

    if (displayedLenRef.current >= text.length) {
      // 已经追平，没有新内容
      return;
    }

    // 逐字追加（流式模式，或刚停止流式但还没打完）
    const timer = setInterval(() => {
      if (displayedLenRef.current < text.length) {
        const nextLen = Math.min(
          displayedLenRef.current + charsPerFrame,
          text.length
        );
        displayedLenRef.current = nextLen;
        setDisplayedText(text.slice(0, nextLen));
      } else {
        clearInterval(timer);
      }
    }, frameInterval);

    return () => clearInterval(timer);
  }, [text, isStreaming, charsPerFrame, frameInterval]);

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

  // ★ 流式模式下隐藏不完整的 markdown 标记，避免用户看到原始语法
  const sanitizedText = isStreaming
    ? stripIncompleteMarkdown(displayedText)
    : displayedText;
  const narrativeMarkdown = narrative
    ? formatNarrativeMarkdownForDisplay(sanitizedText)
    : sanitizedText;

  if (!displayedText && !isStreaming) return null;

  return (
    <div
      ref={containerRef}
      className={cn(
        "overflow-y-auto select-text",
        narrative && "prose-story",
        className
      )}
    >
      {narrative ? (
        <div className="animate-fade-in-word">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {narrativeMarkdown}
          </ReactMarkdown>
          {isStreaming && <span className="typewriter-cursor" />}
        </div>
      ) : (
        <>
          {/* Split text into paragraphs for non-narrative mode */}
          {displayedText.split("\n\n").filter(Boolean).map((para, i, arr) => (
            <p key={i} className="animate-fade-in-word">
              {para}
              {i === arr.length - 1 && isStreaming && (
                <span className="typewriter-cursor" />
              )}
            </p>
          ))}
        </>
      )}
    </div>
  );
}

/**
 * Adds visual paragraph breaks for long single-line Chinese narrative text.
 * Existing markdown/newlines are treated as authored formatting and preserved.
 */
export function formatNarrativeMarkdownForDisplay(text: string): string {
  if (!text) return text;
  if (/\n/.test(text)) return text;

  const trimmed = text.trim();
  if (trimmed.length < 120) return text;

  const sentences = extractChineseSentences(trimmed);
  if (sentences.length < 4) return text;

  const paragraphs: string[] = [];
  for (let i = 0; i < sentences.length; i += 2) {
    paragraphs.push(sentences.slice(i, i + 2).join("").trim());
  }

  return paragraphs.join("\n\n");
}

function extractChineseSentences(text: string): string[] {
  const sentencePattern = /[^。！？!?；;]+[。！？!?；;]+[”’」』）】》]?/g;
  const matches: string[] = text.match(sentencePattern) || [];
  const consumedLength = matches.join("").length;
  const tail = text.slice(consumedLength).trim();

  if (tail) {
    matches.push(tail);
  }

  return matches.map((sentence) => sentence.trim()).filter(Boolean);
}

/**
 * 移除文本末尾不完整的 markdown 标记。
 * 在流式显示时，避免用户看到 `**bold` 这种未闭合的原始语法。
 */
export function stripIncompleteMarkdown(text: string): string {
  if (!text) return text;

  // 检查末尾是否有未闭合的 `**`（粗体）
  const boldOpenCount = (text.match(/\*\*/g) || []).length;
  if (boldOpenCount % 2 !== 0) {
    // 奇数个 **，最后一个未闭合，移除它
    const lastIdx = text.lastIndexOf("**");
    if (lastIdx !== -1 && lastIdx > text.length - 4) {
      text = text.slice(0, lastIdx) + text.slice(lastIdx + 2);
    }
  }

  // 检查末尾是否有未闭合的 `*`（斜体）—— 注意不能误删 ** 的一部分
  // 简单处理：如果末尾是单独的 *，移除它
  if (text.endsWith("*") && !text.endsWith("**")) {
    text = text.slice(0, -1);
  }

  // 检查末尾是否有未闭合的 `~~`（删除线 / strikethrough）
  const strikeCount = (text.match(/~~/g) || []).length;
  if (strikeCount % 2 !== 0) {
    const lastIdx = text.lastIndexOf("~~");
    if (lastIdx !== -1 && lastIdx > text.length - 4) {
      text = text.slice(0, lastIdx) + text.slice(lastIdx + 2);
    }
  }

  // 检查末尾是否有单独的 `~`（可能是删除线的开始）
  if (text.endsWith("~") && !text.endsWith("~~")) {
    text = text.slice(0, -1);
  }

  // 检查末尾是否有未闭合的 `_`（斜体/下划线）
  if (text.endsWith("_")) {
    const underscoreCount = (text.match(/_/g) || []).length;
    if (underscoreCount % 2 !== 0) {
      text = text.slice(0, -1);
    }
  }

  // 检查末尾是否有未闭合的 `` ` ``（行内代码）
  const backtickCount = (text.match(/`/g) || []).length;
  if (backtickCount % 2 !== 0) {
    const lastIdx = text.lastIndexOf("`");
    if (lastIdx !== -1 && lastIdx > text.length - 3) {
      text = text.slice(0, lastIdx) + text.slice(lastIdx + 1);
    }
  }

  return text;
}
