"use client";

import { useRef } from "react";
import { Pause, Play, RotateCcw, Square, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ReadingContext } from "@/lib/types";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";

interface StoryVoiceControlsProps {
  currentContext: ReadingContext;
  historyContext?: ReadingContext | null;
  autoReadText?: string;
  compact?: boolean;
  showTestControls?: boolean;
}

export function StoryVoiceControls({
  currentContext,
  historyContext,
  autoReadText,
  compact = false,
  showTestControls = false,
}: StoryVoiceControlsProps) {
  const readingState = useStoryVoiceStore((state) => state.readingState);
  const currentSource = useStoryVoiceStore((state) => state.currentSource);
  const currentContextLabel = useStoryVoiceStore((state) => state.currentContextLabel);
  const currentAudioUrl = useStoryVoiceStore((state) => state.currentAudioUrl);
  const currentJobId = useStoryVoiceStore((state) => state.currentJobId);
  const playbackMode = useStoryVoiceStore((state) => state.playbackMode);
  const spokenTextLength = useStoryVoiceStore((state) => state.spokenTextLength);
  const errorMessage = useStoryVoiceStore((state) => state.errorMessage);
  const queueText = useStoryVoiceStore((state) => state.queueText);
  const autoReadEnabled = useStoryVoiceStore((state) => state.autoReadEnabled);
  const musicDuckState = useStoryVoiceStore((state) => state.musicDuckState);
  const startReading = useStoryVoiceStore((state) => state.startReading);
  const pauseReading = useStoryVoiceStore((state) => state.pauseReading);
  const stopReading = useStoryVoiceStore((state) => state.stopReading);
  const completeReading = useStoryVoiceStore((state) => state.completeReading);
  const retryReading = useStoryVoiceStore((state) => state.retryReading);
  const failReading = useStoryVoiceStore((state) => state.failReading);
  const setAutoReadEnabled = useStoryVoiceStore((state) => state.setAutoReadEnabled);
  const enqueueCompletedAttempt = useStoryVoiceStore((state) => state.enqueueCompletedAttempt);
  const simulateMusicPlaying = useStoryVoiceStore((state) => state.simulateMusicPlaying);
  const userPauseMusicDuringReading = useStoryVoiceStore(
    (state) => state.userPauseMusicDuringReading
  );

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const textSize = compact ? "text-xs" : "text-sm";

  const handlePause = () => {
    audioRef.current?.pause();
    pauseReading();
  };

  const handleContinue = () => {
    const audio = audioRef.current;
    if (audio) {
      if (audio.ended) {
        audio.currentTime = 0;
      }
      void audio.play().catch(failReading);
    }
    retryReading();
  };

  const handleStop = () => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    stopReading();
  };

  return (
    <section
      aria-label="故事朗读"
      className="rounded border border-border bg-card/60 p-3 space-y-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void startReading(currentContext)}
          aria-label="朗读当前故事"
        >
          <Volume2 className="w-4 h-4 mr-1.5" />
          朗读当前故事
        </Button>
        {historyContext && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void startReading(historyContext)}
            aria-label="朗读历史故事"
          >
            <Volume2 className="w-4 h-4 mr-1.5" />
            朗读历史故事
          </Button>
        )}
        {readingState === "playing" ? (
          <Button type="button" size="sm" variant="ghost" onClick={handlePause}>
            <Pause className="w-4 h-4 mr-1.5" />
            暂停朗读
          </Button>
        ) : readingState !== "failed" ? (
          <Button type="button" size="sm" variant="ghost" onClick={handleContinue}>
            <Play className="w-4 h-4 mr-1.5" />
            继续朗读
          </Button>
        ) : null}
        <Button type="button" size="sm" variant="ghost" onClick={handleStop}>
          <Square className="w-4 h-4 mr-1.5" />
          停止朗读
        </Button>
        {readingState === "failed" && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => void startReading(currentContext)}
          >
            <RotateCcw className="w-4 h-4 mr-1.5" />
            重试朗读
          </Button>
        )}
      </div>

      <div className={`${textSize} text-muted-foreground flex flex-wrap gap-3`}>
        <span>
          状态: <span data-testid="voice-reading-state">{readingState}</span>
        </span>
        <span>
          来源: <span data-testid="voice-reading-source">{currentSource}</span>
        </span>
        <span data-testid="voice-reading-context">{currentContextLabel}</span>
        <span>
          Job: <span data-testid="voice-reading-job">{currentJobId ?? ""}</span>
        </span>
        <span>
          Audio: <span data-testid="voice-reading-audio-url">{currentAudioUrl}</span>
        </span>
        <span>
          Mode: <span data-testid="voice-reading-mode">{playbackMode}</span>
        </span>
        <span>
          Length: <span data-testid="voice-reading-spoken-length">{spokenTextLength}</span>
        </span>
        {errorMessage && (
          <span>
            错误: <span data-testid="voice-reading-error">{errorMessage}</span>
          </span>
        )}
      </div>

      {showTestControls && (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={autoReadEnabled ? "default" : "outline"}
            onClick={() => setAutoReadEnabled(!autoReadEnabled)}
          >
            {autoReadEnabled ? "关闭自动朗读" : "启用自动朗读"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => enqueueCompletedAttempt(autoReadText || currentContext.text)}
          >
            完成自动朗读入队
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={simulateMusicPlaying}>
            模拟音乐播放中
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={completeReading}>
            模拟朗读结束
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={userPauseMusicDuringReading}>
            用户手动暂停音乐
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={failReading}>
            模拟朗读失败
          </Button>
        </div>
      )}

      <div className={`${textSize} text-muted-foreground flex flex-wrap gap-3`}>
        <span>
          队列: <span data-testid="voice-reading-queue">{queueText}</span>
        </span>
        <span>
          音乐: <span data-testid="music-duck-state">{musicDuckState}</span>
        </span>
      </div>
      <audio
        ref={audioRef}
        data-testid="voice-reading-audio-player"
        src={currentAudioUrl || undefined}
        autoPlay={Boolean(currentAudioUrl)}
        preload="auto"
        onEnded={completeReading}
      />
    </section>
  );
}
