"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react";
import {
  BookOpenText,
  ChevronDown,
  ChevronUp,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  Volume2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { storyVoiceTextToHash } from "@/lib/storyVoiceTextHash";
import type {
  EventOption,
  ReadingContext,
  VoiceReadingJobResponse,
  VoiceReadingProgress,
  VoiceReadingSegment,
} from "@/lib/types";
import { cn } from "@/lib/utils";

import { OptionCards } from "./OptionCards";

type ListeningStatus =
  | "preparing"
  | "ready"
  | "playing"
  | "paused"
  | "failed";

interface StoryListeningExperienceProps {
  context: ReadingContext;
  storyText: string;
  dateTitle?: string | null;
  dayNumber?: number | null;
  totalDays?: number | null;
  options: EventOption[];
  onSelectChoice: (index: number) => void | Promise<void>;
  media?: ReactNode;
}

const VOICES = [
  { id: "warm_female", label: "温暖女声" },
  { id: "calm_male", label: "沉静男声" },
  { id: "clear_neutral", label: "清澈中性" },
];
const SPEEDS = [0.75, 1, 1.25, 1.5];
const STALL_WATCHDOG_MS = 8_000;

function splitParagraphs(text: string): string[] {
  return text
    .replace(/\r\n?/g, "\n")
    .trim()
    .split(/\n\s*\n+/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function StoryListeningExperience({
  context,
  storyText,
  dateTitle,
  dayNumber,
  totalDays,
  options,
  onSelectChoice,
  media,
}: StoryListeningExperienceProps) {
  const paragraphs = useMemo(() => splitParagraphs(storyText), [storyText]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cancelledRef = useRef(false);
  const generationRef = useRef(0);
  const autoPlayRequestedRef = useRef(true);
  const autoReadRef = useRef(true);
  const pendingResumePositionRef = useRef<number | null>(0);
  const lastProgressWriteRef = useRef(0);
  const activeParagraphRef = useRef(0);
  const playbackGenerationRef = useRef(0);
  const recoveryTimerRef = useRef<number | null>(null);
  const recoveredParagraphsRef = useRef(new Set<number>());

  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [textHash, setTextHash] = useState("");
  const [segments, setSegments] = useState<VoiceReadingSegment[]>([]);
  const [jobId, setJobId] = useState<number | null>(null);
  const [status, setStatus] = useState<ListeningStatus>("preparing");
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedVoice, setSelectedVoice] = useState("warm_female");
  const [speed, setSpeed] = useState(1);
  const [autoRead, setAutoRead] = useState(true);
  const [activeParagraph, setActiveParagraph] = useState(0);
  const [positionMs, setPositionMs] = useState(0);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const [mediaDurations, setMediaDurations] = useState<Record<number, number>>({});
  const [networkRetryRequired, setNetworkRetryRequired] = useState(false);

  const currentSegment = segments.find(
    (segment) => segment.paragraph_index === activeParagraph,
  );
  const readySegments = segments.filter((segment) => segment.audio_url);
  const segmentDuration = (segment: VoiceReadingSegment) =>
    mediaDurations[segment.paragraph_index] ?? segment.duration_ms ?? 0;
  const totalDurationMs = segments.reduce((total, segment) => total + segmentDuration(segment), 0);
  const elapsedBeforeCurrent = segments
    .filter((segment) => segment.paragraph_index < activeParagraph)
    .reduce((total, segment) => total + segmentDuration(segment), 0);
  const chapterPositionMs = Math.min(
    totalDurationMs,
    elapsedBeforeCurrent + positionMs,
  );
  const progressRatio = totalDurationMs > 0 ? chapterPositionMs / totalDurationMs : 0;

  const clearRecoveryWatchdog = () => {
    if (recoveryTimerRef.current !== null) {
      window.clearTimeout(recoveryTimerRef.current);
      recoveryTimerRef.current = null;
    }
  };

  const recordAudioDiagnostic = (mediaState: string) => {
    const audio = audioRef.current;
    console.info("[StoryListeningExperience] audio", {
      paragraphIndex: activeParagraphRef.current,
      mediaState,
      currentTimeMs: Math.round((audio?.currentTime ?? 0) * 1000),
      observedAtMs: Date.now(),
    });
  };

  const cancelActivePlayback = () => {
    clearRecoveryWatchdog();
    playbackGenerationRef.current += 1;
    audioRef.current?.pause();
  };

  useEffect(() => {
    activeParagraphRef.current = activeParagraph;
  }, [activeParagraph]);

  useEffect(() => {
    cancelledRef.current = false;
    const audio = audioRef.current;
    void Promise.all([api.voice_reading.getSettings(), storyVoiceTextToHash(storyText)])
      .then(([settings, hash]) => {
        if (cancelledRef.current) return;
        setSelectedVoice(settings.selected_voice_color || "warm_female");
        setSpeed(settings.selected_speed || 1);
        setAutoRead(settings.auto_read_enabled);
        autoReadRef.current = settings.auto_read_enabled;
        autoPlayRequestedRef.current = settings.auto_read_enabled;
        setTextHash(hash);
        setSettingsLoaded(true);
      })
      .catch((error) => {
        if (cancelledRef.current) return;
        setStatus("failed");
        setErrorMessage(error instanceof Error ? error.message : "无法读取朗读设置");
      });
    return () => {
      cancelledRef.current = true;
      generationRef.current += 1;
      clearRecoveryWatchdog();
      playbackGenerationRef.current += 1;
      if (audio) audio.pause();
    };
  }, [storyText]);

  const applyJob = useCallback((job: VoiceReadingJobResponse) => {
    setSegments(job.segments);
    if (job.status === "failed") {
      setStatus("failed");
      setErrorMessage(job.message || job.error_code || "高质量语音生成失败");
      return;
    }
    if (job.segments.some((segment) => segment.audio_url)) {
      setStatus((current) => (current === "playing" ? current : "ready"));
    } else {
      setStatus("preparing");
    }
  }, []);

  useEffect(() => {
    if (!settingsLoaded || !textHash || context.source_type !== "current_story") return;
    const generation = ++generationRef.current;
    let active = true;
    setStatus("preparing");
    setErrorMessage("");
    setSegments([]);
    setActiveParagraph(0);
    setPositionMs(0);
    pendingResumePositionRef.current = 0;
    recoveredParagraphsRef.current.clear();
    setMediaDurations({});
    setNetworkRetryRequired(false);

    const identity = {
      game_id: context.game_id,
      day_index: context.day_index ?? 0,
      text_hash: textHash,
      voice_id: selectedVoice,
      speed,
    };

    const run = async () => {
      try {
        try {
          const progress = await api.voice_reading.getProgress(identity);
          if (!active || generation !== generationRef.current) return;
          setActiveParagraph(Math.min(progress.paragraph_index, Math.max(0, paragraphs.length - 1)));
          setPositionMs(progress.position_ms);
          pendingResumePositionRef.current = progress.position_ms;
        } catch (error) {
          if ((error as { status?: number }).status !== 404) {
            console.warn("[StoryListeningExperience] Progress recovery unavailable", error);
          }
        }

        const response = await api.voice_reading.requestReading({
          context: {
            source_type: context.source_type,
            game_id: context.game_id,
            week: context.week,
            round_number: context.round_number,
            stage: context.stage,
            attempt_id: context.attempt_id,
            day_index: context.day_index,
            story_date: context.story_date,
            text: storyText,
            text_hash: textHash,
          },
          voice_id: selectedVoice,
          speed,
          auto_play: autoReadRef.current,
        });
        if (!active || generation !== generationRef.current) return;
        setJobId(response.job_id);
        applyJob(response);

        let job: VoiceReadingJobResponse = response;
        while (active && generation === generationRef.current && !["ready", "failed"].includes(job.status)) {
          job = await api.voice_reading.getJob(response.job_id);
          if (!active || generation !== generationRef.current) return;
          applyJob(job);
          if (!["ready", "failed"].includes(job.status)) await delay(700);
        }
      } catch (error) {
        if (!active || generation !== generationRef.current) return;
        setStatus("failed");
        setErrorMessage(error instanceof Error ? error.message : "高质量语音生成失败");
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [
    applyJob,
    context.attempt_id,
    context.day_index,
    context.game_id,
    context.round_number,
    context.source_type,
    context.stage,
    context.story_date,
    context.week,
    paragraphs.length,
    retryNonce,
    selectedVoice,
    settingsLoaded,
    speed,
    storyText,
    textHash,
  ]);

  const persistProgress = useCallback(
    (paragraphIndex: number, milliseconds: number, completed = false) => {
      if (!textHash) return;
      const progress: VoiceReadingProgress = {
        game_id: context.game_id,
        day_index: context.day_index ?? 0,
        story_date: context.story_date,
        text_hash: textHash,
        voice_id: selectedVoice,
        speed,
        paragraph_index: paragraphIndex,
        position_ms: Math.max(0, Math.round(milliseconds)),
        completed,
      };
      void api.voice_reading.updateProgress(progress).catch((error) => {
        console.warn("[StoryListeningExperience] Progress persistence unavailable", error);
      });
    },
    [context.day_index, context.game_id, context.story_date, selectedVoice, speed, textHash],
  );

  const playAudio = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio || !currentSegment?.audio_url) return;
    const playbackGeneration = playbackGenerationRef.current;
    try {
      await audio.play();
      if (playbackGeneration !== playbackGenerationRef.current) return;
      setStatus("playing");
      setErrorMessage("");
      setNetworkRetryRequired(false);
    } catch {
      if (playbackGeneration !== playbackGenerationRef.current) return;
      setStatus("ready");
      setErrorMessage("点击播放，开启自动朗读");
    }
  }, [currentSegment?.audio_url]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !currentSegment?.audio_url) return;
    clearRecoveryWatchdog();
    playbackGenerationRef.current += 1;
  }, [activeParagraph, currentSegment?.audio_url]);

  const chooseParagraph = (index: number) => {
    cancelActivePlayback();
    setActiveParagraph(index);
    setPositionMs(0);
    pendingResumePositionRef.current = 0;
    autoPlayRequestedRef.current = true;
    setNetworkRetryRequired(false);
    persistProgress(index, 0);
  };

  const handleEnded = () => {
    clearRecoveryWatchdog();
    recordAudioDiagnostic("ended");
    const nextIndex = activeParagraph + 1;
    if (nextIndex < paragraphs.length) {
      chooseParagraph(nextIndex);
      return;
    }
    setStatus("ready");
    const duration = currentSegment ? segmentDuration(currentSegment) : 0;
    setPositionMs(duration);
    persistProgress(activeParagraph, duration, true);
  };

  const handleTimeUpdate = () => {
    const milliseconds = (audioRef.current?.currentTime ?? 0) * 1000;
    setPositionMs(milliseconds);
    const now = Date.now();
    if (now - lastProgressWriteRef.current >= 2_000) {
      lastProgressWriteRef.current = now;
      persistProgress(activeParagraph, milliseconds);
    }
  };

  const handlePrimaryAction = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (status === "playing") {
      cancelActivePlayback();
      autoPlayRequestedRef.current = false;
      setStatus("paused");
      persistProgress(activeParagraph, audio.currentTime * 1000);
      return;
    }
    autoPlayRequestedRef.current = true;
    void playAudio();
  };

  const handleRestart = () => chooseParagraph(0);

  const handleSeek = (event: ChangeEvent<HTMLInputElement>) => {
    const target = Number(event.target.value);
    let remaining = target;
    for (const segment of segments) {
      const duration = segmentDuration(segment);
      if (remaining <= duration || segment === segments.at(-1)) {
        const wasPlaying = status === "playing";
        cancelActivePlayback();
        setActiveParagraph(segment.paragraph_index);
        setPositionMs(remaining);
        pendingResumePositionRef.current = remaining;
        autoPlayRequestedRef.current = wasPlaying;
        setNetworkRetryRequired(false);
        persistProgress(segment.paragraph_index, remaining);
        break;
      }
      remaining -= duration;
    }
  };

  const handleVoiceChange = (event: ChangeEvent<HTMLSelectElement>) => {
    cancelActivePlayback();
    const value = event.target.value;
    setSelectedVoice(value);
    void api.voice_reading.updateSettings({ selected_voice_color: value });
  };

  const handleSpeedChange = (event: ChangeEvent<HTMLSelectElement>) => {
    cancelActivePlayback();
    const value = Number(event.target.value);
    setSpeed(value);
    void api.voice_reading.updateSettings({ selected_speed: value });
  };

  const handleAutoReadChange = () => {
    const value = !autoRead;
    setAutoRead(value);
    autoReadRef.current = value;
    autoPlayRequestedRef.current = value;
    void api.voice_reading.updateSettings({ auto_read_enabled: value });
  };

  const handleChoice = (index: number) => {
    const audio = audioRef.current;
    cancelActivePlayback();
    if (audio) persistProgress(activeParagraph, audio.currentTime * 1000);
    generationRef.current += 1;
    autoPlayRequestedRef.current = false;
    setStatus("paused");
    return onSelectChoice(index);
  };

  const scheduleRecoveryWatchdog = (mediaState: "waiting" | "stalled" | "error") => {
    clearRecoveryWatchdog();
    recordAudioDiagnostic(mediaState);
    const audio = audioRef.current;
    if (!audio || !currentSegment?.audio_url) return;
    const paragraphIndex = activeParagraph;
    const playbackGeneration = playbackGenerationRef.current;
    const resumePositionMs = Math.max(0, audio.currentTime * 1000);
    recoveryTimerRef.current = window.setTimeout(() => {
      recoveryTimerRef.current = null;
      if (
        playbackGeneration !== playbackGenerationRef.current ||
        paragraphIndex !== activeParagraphRef.current
      ) {
        return;
      }
      if (recoveredParagraphsRef.current.has(paragraphIndex)) {
        autoPlayRequestedRef.current = false;
        setStatus("failed");
        setNetworkRetryRequired(true);
        setErrorMessage("网络不稳定，继续朗读");
        recordAudioDiagnostic("recovery_required");
        return;
      }
      recoveredParagraphsRef.current.add(paragraphIndex);
      pendingResumePositionRef.current = resumePositionMs;
      autoPlayRequestedRef.current = true;
      setStatus("ready");
      recordAudioDiagnostic("automatic_recovery");
      audio.load();
    }, STALL_WATCHDOG_MS);
  };

  const handleLoadedMetadata = () => {
    const audio = audioRef.current;
    if (!audio || !currentSegment) return;
    const durationMs = Math.round(audio.duration * 1000);
    if (Number.isFinite(durationMs) && durationMs > 0) {
      setMediaDurations((current) => (
        current[currentSegment.paragraph_index] === durationMs
          ? current
          : { ...current, [currentSegment.paragraph_index]: durationMs }
      ));
    }
    if (pendingResumePositionRef.current !== null) {
      const resumeMs = durationMs > 0
        ? Math.min(Math.max(0, pendingResumePositionRef.current), durationMs)
        : Math.max(0, pendingResumePositionRef.current);
      audio.currentTime = resumeMs / 1000;
      setPositionMs(resumeMs);
      pendingResumePositionRef.current = null;
    }
    recordAudioDiagnostic("loadedmetadata");
  };

  const handleCanPlay = () => {
    recordAudioDiagnostic("canplay");
    if (autoPlayRequestedRef.current && !networkRetryRequired) void playAudio();
  };

  const handlePlaying = () => {
    clearRecoveryWatchdog();
    recordAudioDiagnostic("playing");
    setStatus("playing");
    setErrorMessage("");
    setNetworkRetryRequired(false);
  };

  const handleNetworkRetry = () => {
    const audio = audioRef.current;
    if (!audio || !currentSegment?.audio_url) return;
    clearRecoveryWatchdog();
    playbackGenerationRef.current += 1;
    pendingResumePositionRef.current = Math.max(0, audio.currentTime * 1000);
    autoPlayRequestedRef.current = true;
    setStatus("ready");
    setErrorMessage("");
    setNetworkRetryRequired(false);
    recordAudioDiagnostic("manual_recovery");
    audio.load();
  };

  const statusLabel =
    status === "preparing"
      ? "正在准备这一章"
      : status === "playing"
        ? `正在朗读第 ${activeParagraph + 1} 段`
        : status === "paused"
          ? "朗读已暂停"
          : status === "failed"
            ? "这一章暂时无法朗读"
            : readySegments.length > 0
              ? "语音已准备好"
              : "等待高质量语音";

  return (
    <section
      data-testid="story-listening-experience"
      className="relative -mx-4 min-h-[calc(100svh-9rem)] overflow-hidden border-y border-[var(--border-default)] bg-[var(--surface-reading)] px-4 py-8 sm:-mx-8 sm:px-8"
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center">
        <header className="w-full text-center">
          <p className="font-mono text-[11px] tracking-[0.24em] text-[var(--text-secondary)]">
            {dateTitle || "今日故事"}
          </p>
          <h1 className="mt-3 font-serif text-3xl font-semibold tracking-[0.12em] text-[var(--text-primary)] sm:text-4xl">
            听故事
          </h1>
          {dayNumber && totalDays ? (
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              第 {dayNumber} 天 · 共 {totalDays} 天
            </p>
          ) : null}
        </header>

        <div
          className="relative my-9 grid h-56 w-56 place-items-center rounded-full border border-[var(--border-strong)] bg-[var(--surface-canvas)] sm:h-64 sm:w-64"
          style={{
            background: `conic-gradient(var(--text-primary) ${Math.round(progressRatio * 360)}deg, var(--surface-canvas) 0deg)`,
            padding: "1px",
          }}
          aria-hidden="true"
        >
          <div className="grid h-full w-full place-items-center rounded-full bg-[var(--surface-canvas)]">
            <div className="text-center">
              <Volume2 className="mx-auto h-7 w-7 text-[var(--text-secondary)]" />
              <p className="mt-4 font-serif text-xl text-[var(--text-primary)]">
                第 {activeParagraph + 1} 段
              </p>
              <p className="mt-2 text-xs text-[var(--text-secondary)]">{statusLabel}</p>
            </div>
          </div>
        </div>

        <audio
          ref={audioRef}
          src={currentSegment?.audio_url || undefined}
          onLoadedMetadata={handleLoadedMetadata}
          onCanPlay={handleCanPlay}
          onPlaying={handlePlaying}
          onWaiting={() => scheduleRecoveryWatchdog("waiting")}
          onStalled={() => scheduleRecoveryWatchdog("stalled")}
          onEnded={handleEnded}
          onTimeUpdate={handleTimeUpdate}
          onError={() => scheduleRecoveryWatchdog("error")}
        />

        <div className="w-full max-w-xl">
          <label className="sr-only" htmlFor="chapter-progress">朗读进度</label>
          <input
            id="chapter-progress"
            type="range"
            min={0}
            max={Math.max(1, totalDurationMs)}
            value={chapterPositionMs}
            onChange={handleSeek}
            className="h-1 w-full accent-[var(--text-primary)]"
          />
          <div className="mt-5 flex items-center justify-center gap-4">
            <Button type="button" variant="quiet" size="icon-touch" onClick={handleRestart} aria-label="从头朗读">
              <RotateCcw className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="narrative"
              size="icon-touch"
              className="h-16 w-16 rounded-full"
              disabled={status === "preparing" || !currentSegment?.audio_url}
              onClick={handlePrimaryAction}
              aria-label={status === "playing" ? "暂停朗读" : "播放朗读"}
            >
              {status === "preparing" ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : status === "playing" ? (
                <Pause className="h-6 w-6" />
              ) : (
                <Play className="ml-0.5 h-6 w-6" />
              )}
            </Button>
            <Button
              type="button"
              variant="quiet"
              size="icon-touch"
              onClick={() => setTranscriptOpen((open) => !open)}
              aria-label={transcriptOpen ? "收起正文" : "查看正文"}
            >
              <BookOpenText className="h-4 w-4" />
            </Button>
          </div>

          <div className="mt-7 grid grid-cols-2 gap-3 border-y border-[var(--border-default)] py-4 sm:grid-cols-3">
            <label className="text-xs text-[var(--text-secondary)]">
              音色
              <select value={selectedVoice} onChange={handleVoiceChange} className="mt-1 block w-full bg-transparent py-2 text-sm text-[var(--text-primary)]">
                {VOICES.map((voice) => <option key={voice.id} value={voice.id}>{voice.label}</option>)}
              </select>
            </label>
            <label className="text-xs text-[var(--text-secondary)]">
              语速
              <select value={speed} onChange={handleSpeedChange} className="mt-1 block w-full bg-transparent py-2 text-sm text-[var(--text-primary)]">
                {SPEEDS.map((value) => <option key={value} value={value}>{value}×</option>)}
              </select>
            </label>
            <label className="col-span-2 flex min-h-11 items-center justify-between gap-3 text-sm text-[var(--text-primary)] sm:col-span-1">
              下一章自动播放
              <input type="checkbox" checked={autoRead} onChange={handleAutoReadChange} className="h-5 w-5 accent-[var(--text-primary)]" />
            </label>
          </div>

          {errorMessage ? (
            <p role="status" className={cn("mt-4 text-center text-sm", status === "failed" ? "text-[var(--danger-foreground)]" : "text-[var(--text-secondary)]")}>{errorMessage}</p>
          ) : null}
          {networkRetryRequired ? (
            <Button
              type="button"
              variant="narrative"
              size="touch"
              className="mx-auto mt-4 flex"
              onClick={handleNetworkRetry}
            >
              网络不稳定，继续朗读
            </Button>
          ) : status === "failed" && jobId ? (
            <Button
              type="button"
              variant="narrative"
              size="touch"
              className="mx-auto mt-4 flex"
              onClick={() => setRetryNonce((value) => value + 1)}
            >
              重试高质量语音
            </Button>
          ) : null}
        </div>

        {transcriptOpen ? (
          <section className="mt-10 w-full max-w-2xl border-t border-[var(--border-default)] pt-7" aria-label="故事正文">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-serif text-lg text-[var(--text-primary)]">故事正文</h2>
              <Button type="button" variant="quiet" size="sm" onClick={() => setTranscriptOpen(false)}>
                收起 <ChevronUp className="ml-1 h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-1">
              {paragraphs.map((paragraph, index) => (
                <button
                  key={`${index}-${paragraph.slice(0, 18)}`}
                  type="button"
                  aria-label={`从第 ${index + 1} 段开始朗读`}
                  aria-current={index === activeParagraph ? "true" : undefined}
                  onClick={() => chooseParagraph(index)}
                  className={cn(
                    "w-full border-l-2 px-4 py-4 text-left font-serif text-base leading-8 transition-colors",
                    index === activeParagraph
                      ? "border-[var(--text-primary)] bg-[var(--surface-raised)] text-[var(--text-primary)]"
                      : "border-transparent text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]",
                  )}
                >
                  {paragraph}
                </button>
              ))}
            </div>
          </section>
        ) : (
          <Button type="button" variant="quiet" size="touch" className="mt-8" onClick={() => setTranscriptOpen(true)}>
            查看正文 <ChevronDown className="ml-1 h-4 w-4" />
          </Button>
        )}

        {media ? <div className="mt-8 w-full">{media}</div> : null}

        <section className="sticky bottom-0 z-20 mt-10 w-full max-w-2xl border-t border-[var(--border-strong)] bg-[var(--surface-reading)]/95 pb-[calc(1rem+var(--safe-area-inset-bottom))] pt-5 backdrop-blur">
          <OptionCards
            options={options}
            onSelect={handleChoice}
            allowCustomChoice={false}
            disabled={false}
          />
        </section>
      </div>
    </section>
  );
}
