"use client";

import { useEffect, useRef, type ChangeEvent } from "react";
import { Loader2, Pause, Play, RotateCcw, Square, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ReadingContext } from "@/lib/types";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";

interface StoryVoiceControlsProps {
  currentContext: ReadingContext;
  historyContext?: ReadingContext | null;
  autoReadText?: string;
  autoReadReady?: boolean;
  compact?: boolean;
  enablePlaybackControls?: boolean;
  showTestControls?: boolean;
}

export function StoryVoiceControls({
  currentContext,
  historyContext,
  autoReadText,
  autoReadReady = false,
  compact = false,
  enablePlaybackControls = false,
  showTestControls = false,
}: StoryVoiceControlsProps) {
  const readingState = useStoryVoiceStore((state) => state.readingState);
  const currentSource = useStoryVoiceStore((state) => state.currentSource);
  const currentContextLabel = useStoryVoiceStore((state) => state.currentContextLabel);
  const currentAudioUrl = useStoryVoiceStore((state) => state.currentAudioUrl);
  const currentJobId = useStoryVoiceStore((state) => state.currentJobId);
  const currentProvider = useStoryVoiceStore((state) => state.currentProvider);
  const playbackMode = useStoryVoiceStore((state) => state.playbackMode);
  const spokenTextLength = useStoryVoiceStore((state) => state.spokenTextLength);
  const currentSpeechText = useStoryVoiceStore((state) => state.currentSpeechText);
  const errorMessage = useStoryVoiceStore((state) => state.errorMessage);
  const queueText = useStoryVoiceStore((state) => state.queueText);
  const autoReadEnabled = useStoryVoiceStore((state) => state.autoReadEnabled);
  const selectedVoiceId = useStoryVoiceStore((state) => state.selectedVoiceId);
  const musicDuckState = useStoryVoiceStore((state) => state.musicDuckState);
  const startReading = useStoryVoiceStore((state) => state.startReading);
  const pauseReading = useStoryVoiceStore((state) => state.pauseReading);
  const stopReading = useStoryVoiceStore((state) => state.stopReading);
  const completeReading = useStoryVoiceStore((state) => state.completeReading);
  const retryReading = useStoryVoiceStore((state) => state.retryReading);
  const failReading = useStoryVoiceStore((state) => state.failReading);
  const setAutoReadEnabled = useStoryVoiceStore((state) => state.setAutoReadEnabled);
  const setSelectedVoiceId = useStoryVoiceStore((state) => state.setSelectedVoiceId);
  const enqueueCompletedAttempt = useStoryVoiceStore((state) => state.enqueueCompletedAttempt);
  const simulateMusicPlaying = useStoryVoiceStore((state) => state.simulateMusicPlaying);
  const userPauseMusicDuringReading = useStoryVoiceStore(
    (state) => state.userPauseMusicDuringReading
  );

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastAutoReadKeyRef = useRef<string>("");
  const loadedSettingsRef = useRef(false);
  const textSize = compact ? "text-xs" : "text-sm";
  const isHistoryReading = currentContext.source_type === "history_round" || Boolean(historyContext);
  const shouldShowPlaybackControls = enablePlaybackControls || showTestControls;
  const showProductionSettings = !showTestControls;

  useEffect(() => {
    if (loadedSettingsRef.current) return;
    loadedSettingsRef.current = true;

    void api.voice_reading.getSettings()
      .then((settings) => {
        if (settings.auto_read_enabled !== autoReadEnabled) {
          setAutoReadEnabled(settings.auto_read_enabled);
        }
        if (settings.selected_voice_color && settings.selected_voice_color !== selectedVoiceId) {
          setSelectedVoiceId(settings.selected_voice_color);
        }
      })
      .catch((error) => {
        console.warn("[StoryVoiceControls] Voice settings load unavailable:", error);
      });
  }, [autoReadEnabled, selectedVoiceId, setAutoReadEnabled, setSelectedVoiceId]);

  useEffect(() => {
    const finalText = autoReadText?.trim();
    if (
      !autoReadReady ||
      !autoReadEnabled ||
      !finalText ||
      currentContext.source_type !== "current_story"
    ) {
      return;
    }

    const key = [
      currentContext.game_id,
      currentContext.week ?? "",
      currentContext.round_number ?? "",
      currentContext.stage ?? "",
      finalText,
    ].join(":");
    if (lastAutoReadKeyRef.current === key) return;
    lastAutoReadKeyRef.current = key;

    void startReading({
      ...currentContext,
      text: finalText,
      text_hash: currentContext.text_hash || "pending-client-hash",
    });
  }, [autoReadReady, autoReadEnabled, autoReadText, currentContext, startReading]);

  if (!shouldShowPlaybackControls) {
    return (
      <section
        aria-label="故事朗读预览"
        className="rounded-lg border border-border/70 bg-card/70 px-3 py-3 shadow-sm"
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded-md bg-muted p-2 text-muted-foreground">
            <Volume2 className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-medium text-foreground">故事朗读</h2>
              <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
                即将开放
              </span>
            </div>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              高质量 TTS 声音模型接入后可用。当前先保留故事文本阅读体验，
              {isHistoryReading ? "历史故事会优先保证可读和可回看。" : "不会启动不可用的朗读任务。"}
            </p>
          </div>
        </div>
      </section>
    );
  }

  const handlePause = () => {
    audioRef.current?.pause();
    window.speechSynthesis.pause();
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
    window.speechSynthesis.resume();
    retryReading();
  };

  const handleStop = () => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    window.speechSynthesis.cancel();
    stopReading();
  };

  const persistVoiceSettings = async (settings: {
    selected_voice_color?: string | null;
    auto_read_enabled?: boolean | null;
  }) => {
    try {
      await api.voice_reading.updateSettings(settings);
    } catch (error) {
      console.warn("[StoryVoiceControls] Voice settings persistence unavailable:", error);
    }
  };

  const handleAutoReadToggle = () => {
    const nextEnabled = !autoReadEnabled;
    setAutoReadEnabled(nextEnabled);
    void persistVoiceSettings({ auto_read_enabled: nextEnabled });
  };

  const handleVoiceChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextVoiceId = event.target.value;
    setSelectedVoiceId(nextVoiceId);
    void persistVoiceSettings({ selected_voice_color: nextVoiceId });
  };

  const primaryReadLabel =
    readingState === "loading"
      ? "正在准备朗读"
      : readingState === "playing"
        ? "正在朗读"
        : "朗读当前故事";
  const primaryReadDisabled = readingState === "loading" || readingState === "playing";

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
          disabled={primaryReadDisabled}
          aria-label={primaryReadLabel}
        >
          {readingState === "loading" ? (
            <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
          ) : (
            <Volume2 className="w-4 h-4 mr-1.5" />
          )}
          {primaryReadLabel}
        </Button>
        {showProductionSettings && (
          <>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              声音
              <select
                aria-label="选择朗读声音"
                value={selectedVoiceId}
                onChange={handleVoiceChange}
                className="h-8 rounded border border-border bg-background px-2 text-sm text-foreground"
              >
                <option value="warm_female">温柔女声</option>
                <option value="calm_male">沉稳男声</option>
                <option value="clear_neutral">清亮中性</option>
              </select>
            </label>
            <Button
              type="button"
              size="sm"
              variant={autoReadEnabled ? "default" : "outline"}
              onClick={handleAutoReadToggle}
              aria-label={autoReadEnabled ? "关闭自动朗读" : "启用自动朗读"}
            >
              {autoReadEnabled ? "关闭自动朗读" : "启用自动朗读"}
            </Button>
          </>
        )}
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
        ) : readingState === "paused" ? (
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

      {showTestControls && (
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
            Provider: <span data-testid="voice-reading-provider">{currentProvider}</span>
          </span>
          <span>
            Audio: <span data-testid="voice-reading-audio-url">{currentAudioUrl}</span>
          </span>
          <span>
            Mode: <span data-testid="voice-reading-mode">{playbackMode}</span>
          </span>
          <span>
            模式: <span data-testid="voice-reading-playback-mode">{playbackMode}</span>
          </span>
          <span>
            Length: <span data-testid="voice-reading-spoken-length">{spokenTextLength}</span>
          </span>
          <span className="sr-only" data-testid="voice-reading-speech-text">
            {currentSpeechText}
          </span>
          {errorMessage && (
            <span>
              错误: <span data-testid="voice-reading-error">{errorMessage}</span>
            </span>
          )}
        </div>
      )}

      {showTestControls && (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={autoReadEnabled ? "default" : "outline"}
            onClick={handleAutoReadToggle}
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

      {showTestControls && (
        <div className={`${textSize} text-muted-foreground flex flex-wrap gap-3`}>
          <span>
            队列: <span data-testid="voice-reading-queue">{queueText}</span>
          </span>
          <span>
            音乐: <span data-testid="music-duck-state">{musicDuckState}</span>
          </span>
        </div>
      )}
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
