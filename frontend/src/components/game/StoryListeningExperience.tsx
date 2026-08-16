"use client";

import {
  useCallback,
  useEffect,
  useEffectEvent,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react";
import {
  BookOpenText,
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
  const pendingSavedProgressRef = useRef<{
    paragraphIndex: number;
    positionMs: number;
  } | null>(null);
  const lastProgressWriteRef = useRef(0);
  const activeParagraphRef = useRef(0);
  const playbackGenerationRef = useRef(0);
  const recoveryTimerRef = useRef<number | null>(null);
  const recoveryStartPositionMsRef = useRef<number | null>(null);
  const playRequestRef = useRef<{
    id: number;
    audio: HTMLAudioElement;
    source: string;
    generation: number;
  } | null>(null);
  const latestPlayRequestIdRef = useRef(0);
  const playingAudioRef = useRef<{
    audio: HTMLAudioElement;
    source: string;
    generation: number;
  } | null>(null);
  const finalSegmentEndedRef = useRef(false);
  const activeAudioSourceRef = useRef<string | null>(null);
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
  const [chapterMediaDurationMs, setChapterMediaDurationMs] = useState<number | null>(null);
  const [networkRetryRequired, setNetworkRetryRequired] = useState(false);
  const [networkRetryVisible, setNetworkRetryVisible] = useState(false);

  const currentSegment = segments.find(
    (segment) => segment.paragraph_index === activeParagraph,
  );
  const chapterSegment = segments.find((segment) => segment.audio_url);
  const activeAudioSource = chapterSegment?.audio_url ?? null;
  useLayoutEffect(() => {
    activeAudioSourceRef.current = activeAudioSource;
  }, [activeAudioSource]);
  const readySegments = segments.filter((segment) => segment.audio_url);
  const segmentDuration = (segment: VoiceReadingSegment) =>
    segment.start_ms != null && segment.end_ms != null
      ? Math.max(0, segment.end_ms - segment.start_ms)
      : segment.duration_ms ?? 0;
  const declaredDurationMs = Math.max(
    0,
    ...segments.map((segment) => segment.end_ms ?? 0),
    segments.reduce((total, segment) => total + segmentDuration(segment), 0),
  );
  const totalDurationMs = chapterMediaDurationMs ?? declaredDurationMs;
  const elapsedBeforeCurrent = currentSegment?.start_ms
    ?? segments
      .filter((segment) => segment.paragraph_index < activeParagraph)
      .reduce((total, segment) => total + segmentDuration(segment), 0);
  const chapterPositionMs = Math.min(
    totalDurationMs,
    elapsedBeforeCurrent + positionMs,
  );
  const progressRatio = totalDurationMs > 0 ? chapterPositionMs / totalDurationMs : 0;

  const locateChapterPosition = (milliseconds: number) => {
    let locatedSegment: VoiceReadingSegment | undefined;
    for (const segment of segments) {
      if ((segment.start_ms ?? 0) <= milliseconds) locatedSegment = segment;
    }
    const paragraphStartMs = locatedSegment?.start_ms ?? 0;
    return {
      paragraphIndex: locatedSegment?.paragraph_index ?? activeParagraphRef.current,
      paragraphPositionMs: Math.max(0, milliseconds - paragraphStartMs),
    };
  };

  const clearRecoveryWatchdog = () => {
    if (recoveryTimerRef.current !== null) {
      window.clearTimeout(recoveryTimerRef.current);
      recoveryTimerRef.current = null;
    }
    recoveryStartPositionMsRef.current = null;
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
    const audio = audioRef.current;
    if (audio) audio.pause();
    playRequestRef.current = null;
    playingAudioRef.current = null;
  };

  const isCurrentAudio = (audio: HTMLAudioElement, source: string) =>
    audioRef.current === audio &&
    activeAudioSourceRef.current === source &&
    audio.getAttribute("src") === source;

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
      playRequestRef.current = null;
      playingAudioRef.current = null;
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
    pendingSavedProgressRef.current = null;
    recoveredParagraphsRef.current.clear();
    finalSegmentEndedRef.current = false;
    setChapterMediaDurationMs(null);
    setNetworkRetryRequired(false);
    setNetworkRetryVisible(false);

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
          pendingSavedProgressRef.current = {
            paragraphIndex: progress.paragraph_index,
            positionMs: progress.position_ms,
          };
          pendingResumePositionRef.current = null;
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

  const playAudio = (audio: HTMLAudioElement, source: string, force = false) => {
    if (!isCurrentAudio(audio, source)) {
      audio.pause();
      return;
    }
    const playbackGeneration = playbackGenerationRef.current;
    const playingAudio = playingAudioRef.current;
    if (
      !force &&
      playingAudio &&
      playingAudio.audio === audio &&
      playingAudio.source === source &&
      playingAudio.generation === playbackGeneration
    ) {
      return;
    }
    if (!force && !audio.paused) return;
    const pendingRequest = playRequestRef.current;
    if (
      !force &&
      pendingRequest &&
      pendingRequest.audio === audio &&
      pendingRequest.source === source &&
      pendingRequest.generation === playbackGeneration
    ) {
      return;
    }
    const request = {
      id: latestPlayRequestIdRef.current + 1,
      audio,
      source,
      generation: playbackGeneration,
    };
    latestPlayRequestIdRef.current = request.id;
    playRequestRef.current = request;
    void audio.play().then(() => {
      if (playRequestRef.current?.id === request.id) playRequestRef.current = null;
      const ownsLatestRequest = latestPlayRequestIdRef.current === request.id;
      if (
        !isCurrentAudio(audio, source) ||
        (ownsLatestRequest && playbackGeneration !== playbackGenerationRef.current)
      ) {
        audio.pause();
        return;
      }
    }).catch(() => {
      if (playRequestRef.current?.id === request.id) playRequestRef.current = null;
      const ownsLatestRequest = latestPlayRequestIdRef.current === request.id;
      if (
        !isCurrentAudio(audio, source) ||
        (ownsLatestRequest && playbackGeneration !== playbackGenerationRef.current)
      ) {
        audio.pause();
        return;
      }
      if (!ownsLatestRequest) return;
      setStatus("ready");
      setErrorMessage("点击播放，开启自动朗读");
    });
  };

  const activateBufferedAudio = useEffectEvent((
    audio: HTMLAudioElement,
    source: string,
  ) => {
    if (audio.readyState >= HTMLMediaElement.HAVE_METADATA) {
      const durationMs = Math.round(audio.duration * 1000);
      if (Number.isFinite(durationMs) && durationMs > 0) {
        setChapterMediaDurationMs(durationMs);
      }
      if (pendingSavedProgressRef.current !== null) {
        const saved = pendingSavedProgressRef.current;
        const savedSegment = segments.find(
          (segment) => segment.paragraph_index === saved.paragraphIndex,
        );
        if (savedSegment?.start_ms != null) {
          pendingResumePositionRef.current = savedSegment.start_ms + saved.positionMs;
          pendingSavedProgressRef.current = null;
        }
      }
      if (pendingResumePositionRef.current !== null) {
        const resumeMs = Number.isFinite(durationMs) && durationMs > 0
          ? Math.min(Math.max(0, pendingResumePositionRef.current), durationMs)
          : Math.max(0, pendingResumePositionRef.current);
        const resumePosition = locateChapterPosition(resumeMs);
        audio.currentTime = resumeMs / 1000;
        activeParagraphRef.current = resumePosition.paragraphIndex;
        setActiveParagraph(resumePosition.paragraphIndex);
        setPositionMs(resumePosition.paragraphPositionMs);
        pendingResumePositionRef.current = null;
      }
    }
    if (
      audio.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA &&
      autoPlayRequestedRef.current &&
      !networkRetryRequired
    ) {
      playAudio(audio, source);
    }
  });

  useEffect(() => {
    const audio = audioRef.current;
    const source = activeAudioSource;
    if (!audio || !source) return;
    clearRecoveryWatchdog();
    playbackGenerationRef.current += 1;
    activateBufferedAudio(audio, source);
    return () => {
      clearRecoveryWatchdog();
      playbackGenerationRef.current += 1;
      if (playRequestRef.current?.audio === audio) playRequestRef.current = null;
      if (playingAudioRef.current?.audio === audio) playingAudioRef.current = null;
      audio.pause();
    };
  }, [activeAudioSource]);

  const chooseParagraph = (index: number) => {
    const targetSegment = segments.find((segment) => segment.paragraph_index === index);
    const targetPositionMs = targetSegment?.start_ms ?? 0;
    cancelActivePlayback();
    setActiveParagraph(index);
    activeParagraphRef.current = index;
    setPositionMs(0);
    pendingSavedProgressRef.current = null;
    pendingResumePositionRef.current = targetPositionMs;
    autoPlayRequestedRef.current = true;
    finalSegmentEndedRef.current = false;
    setNetworkRetryRequired(false);
    setNetworkRetryVisible(false);
    persistProgress(index, 0);
    const audio = audioRef.current;
    if (
      audio &&
      activeAudioSource &&
      audio.readyState >= HTMLMediaElement.HAVE_METADATA
    ) {
      audio.currentTime = targetPositionMs / 1000;
      pendingResumePositionRef.current = null;
      playAudio(audio, activeAudioSource, true);
    }
  };

  const handleEnded = (audio: HTMLAudioElement, source: string) => {
    if (!isCurrentAudio(audio, source)) {
      audio.pause();
      return;
    }
    clearRecoveryWatchdog();
    recordAudioDiagnostic("ended");
    playRequestRef.current = null;
    playingAudioRef.current = null;
    playbackGenerationRef.current += 1;
    finalSegmentEndedRef.current = true;
    autoPlayRequestedRef.current = false;
    setStatus("ready");
    const finalSegment = segments.at(-1);
    const finalIndex = finalSegment?.paragraph_index ?? activeParagraph;
    const duration = finalSegment ? segmentDuration(finalSegment) : 0;
    setActiveParagraph(finalIndex);
    setPositionMs(duration);
    persistProgress(finalIndex, duration, true);
  };

  const armRecoveryWatchdog = (
    audio: HTMLAudioElement,
    source: string,
    restartDeadline = false,
  ) => {
    if (!isCurrentAudio(audio, source)) {
      audio.pause();
      return;
    }
    if (restartDeadline) clearRecoveryWatchdog();
    if (recoveryTimerRef.current !== null) return;
    const paragraphIndex = activeParagraph;
    const playbackGeneration = playbackGenerationRef.current;
    const resumePositionMs = pendingResumePositionRef.current
      ?? Math.max(0, audio.currentTime * 1000);
    recoveryStartPositionMsRef.current = resumePositionMs;
    recoveryTimerRef.current = window.setTimeout(() => {
      recoveryTimerRef.current = null;
      recoveryStartPositionMsRef.current = null;
      if (
        playbackGeneration !== playbackGenerationRef.current ||
        paragraphIndex !== activeParagraphRef.current ||
        !isCurrentAudio(audio, source)
      ) {
        audio.pause();
        return;
      }
      setNetworkRetryVisible(true);
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
      setErrorMessage("网络不稳定，正在重新连接朗读");
      recordAudioDiagnostic("automatic_recovery");
      if (playRequestRef.current?.audio === audio) playRequestRef.current = null;
      if (playingAudioRef.current?.audio === audio) playingAudioRef.current = null;
      audio.load();
    }, STALL_WATCHDOG_MS);
  };

  const handleTimeUpdate = (audio: HTMLAudioElement, source: string) => {
    if (!isCurrentAudio(audio, source)) return;
    const chapterMilliseconds = audio.currentTime * 1000;
    const timedSegment = segments.find((segment, index) => {
      if (segment.start_ms == null) return false;
      const endMs = segment.end_ms
        ?? segments[index + 1]?.start_ms
        ?? totalDurationMs;
      return chapterMilliseconds >= segment.start_ms && chapterMilliseconds < endMs;
    }) ?? segments.at(-1);
    const paragraphIndex = timedSegment?.paragraph_index ?? activeParagraphRef.current;
    const paragraphStartMs = timedSegment?.start_ms ?? 0;
    const milliseconds = Math.max(0, chapterMilliseconds - paragraphStartMs);
    if (paragraphIndex !== activeParagraphRef.current) {
      activeParagraphRef.current = paragraphIndex;
      setActiveParagraph(paragraphIndex);
    }
    setPositionMs(milliseconds);
    const playbackAdvanced =
      recoveryTimerRef.current !== null &&
      recoveryStartPositionMsRef.current !== null &&
      chapterMilliseconds > recoveryStartPositionMsRef.current;
    if (playbackAdvanced) {
      const playingAudio = playingAudioRef.current;
      if (
        playingAudio?.audio === audio &&
        playingAudio.source === source &&
        playingAudio.generation === playbackGenerationRef.current
      ) {
        armRecoveryWatchdog(audio, source, true);
      } else {
        clearRecoveryWatchdog();
      }
    }
    const now = Date.now();
    if (now - lastProgressWriteRef.current >= 2_000) {
      lastProgressWriteRef.current = now;
      persistProgress(paragraphIndex, milliseconds);
    }
  };

  const handlePrimaryAction = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (status === "playing") {
      cancelActivePlayback();
      autoPlayRequestedRef.current = false;
      setStatus("paused");
      const startMs = currentSegment?.start_ms ?? elapsedBeforeCurrent;
      persistProgress(
        activeParagraph,
        Math.max(0, audio.currentTime * 1000 - startMs),
      );
      return;
    }
    autoPlayRequestedRef.current = true;
    if (finalSegmentEndedRef.current) {
      audio.currentTime = 0;
      pendingResumePositionRef.current = 0;
      setPositionMs(0);
      finalSegmentEndedRef.current = false;
    }
    if (activeAudioSource) playAudio(audio, activeAudioSource, true);
  };

  const handleRestart = () => chooseParagraph(0);

  const handleSeek = (event: ChangeEvent<HTMLInputElement>) => {
    const target = Number(event.target.value);
    const segment = segments.find((candidate, index) => {
      const startMs = candidate.start_ms
        ?? segments
          .slice(0, index)
          .reduce((total, value) => total + segmentDuration(value), 0);
      const endMs = candidate.end_ms ?? startMs + segmentDuration(candidate);
      return target >= startMs && (target < endMs || candidate === segments.at(-1));
    }) ?? segments.at(-1);
    if (!segment) return;
    const startMs = segment.start_ms
      ?? segments
        .filter((candidate) => candidate.paragraph_index < segment.paragraph_index)
        .reduce((total, value) => total + segmentDuration(value), 0);
    const paragraphPositionMs = Math.max(0, target - startMs);
    const wasPlaying = status === "playing";
    const audio = audioRef.current;
    cancelActivePlayback();
    setActiveParagraph(segment.paragraph_index);
    activeParagraphRef.current = segment.paragraph_index;
    setPositionMs(paragraphPositionMs);
    pendingSavedProgressRef.current = null;
    pendingResumePositionRef.current = target;
    autoPlayRequestedRef.current = wasPlaying;
    finalSegmentEndedRef.current = false;
    setNetworkRetryRequired(false);
    setNetworkRetryVisible(false);
    persistProgress(segment.paragraph_index, paragraphPositionMs);
    if (
      audio &&
      activeAudioSource &&
      isCurrentAudio(audio, activeAudioSource) &&
      audio.readyState >= HTMLMediaElement.HAVE_METADATA
    ) {
      audio.currentTime = target / 1000;
      pendingResumePositionRef.current = null;
      if (wasPlaying) playAudio(audio, activeAudioSource, true);
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
    if (audio) {
      const startMs = currentSegment?.start_ms ?? elapsedBeforeCurrent;
      persistProgress(
        activeParagraph,
        Math.max(0, audio.currentTime * 1000 - startMs),
      );
    }
    generationRef.current += 1;
    autoPlayRequestedRef.current = false;
    setStatus("paused");
    return onSelectChoice(index);
  };

  const scheduleRecoveryWatchdog = (
    audio: HTMLAudioElement,
    source: string,
    mediaState: "waiting" | "stalled" | "error",
  ) => {
    if (!isCurrentAudio(audio, source)) {
      audio.pause();
      return;
    }
    recordAudioDiagnostic(mediaState);
    armRecoveryWatchdog(audio, source);
  };

  const handleLoadedMetadata = (audio: HTMLAudioElement, source: string) => {
    if (!isCurrentAudio(audio, source)) {
      audio.pause();
      return;
    }
    const durationMs = Math.round(audio.duration * 1000);
    if (Number.isFinite(durationMs) && durationMs > 0) {
      setChapterMediaDurationMs(durationMs);
    }
    if (pendingSavedProgressRef.current !== null) {
      const saved = pendingSavedProgressRef.current;
      const savedSegment = segments.find(
        (segment) => segment.paragraph_index === saved.paragraphIndex,
      );
      if (savedSegment?.start_ms != null) {
        pendingResumePositionRef.current = savedSegment.start_ms + saved.positionMs;
        pendingSavedProgressRef.current = null;
      }
    }
    if (pendingResumePositionRef.current !== null) {
      const resumeMs = durationMs > 0
        ? Math.min(Math.max(0, pendingResumePositionRef.current), durationMs)
        : Math.max(0, pendingResumePositionRef.current);
      const resumePosition = locateChapterPosition(resumeMs);
      audio.currentTime = resumeMs / 1000;
      activeParagraphRef.current = resumePosition.paragraphIndex;
      setActiveParagraph(resumePosition.paragraphIndex);
      setPositionMs(resumePosition.paragraphPositionMs);
      pendingResumePositionRef.current = null;
    }
    recordAudioDiagnostic("loadedmetadata");
  };

  const handleCanPlay = (audio: HTMLAudioElement, source: string) => {
    if (!isCurrentAudio(audio, source)) {
      audio.pause();
      return;
    }
    recordAudioDiagnostic("canplay");
    if (autoPlayRequestedRef.current && !networkRetryRequired) playAudio(audio, source);
  };

  const handlePlaying = (audio: HTMLAudioElement, source: string) => {
    if (!isCurrentAudio(audio, source)) {
      audio.pause();
      return;
    }
    clearRecoveryWatchdog();
    playRequestRef.current = null;
    playingAudioRef.current = {
      audio,
      source,
      generation: playbackGenerationRef.current,
    };
    recordAudioDiagnostic("playing");
    setStatus("playing");
    setErrorMessage("");
    setNetworkRetryRequired(false);
    setNetworkRetryVisible(false);
    armRecoveryWatchdog(audio, source, true);
  };

  const handleNetworkRetry = () => {
    const audio = audioRef.current;
    const source = activeAudioSource;
    if (!audio || !source) return;
    clearRecoveryWatchdog();
    playbackGenerationRef.current += 1;
    playRequestRef.current = null;
    playingAudioRef.current = null;
    pendingResumePositionRef.current = pendingResumePositionRef.current
      ?? Math.max(0, audio.currentTime * 1000);
    autoPlayRequestedRef.current = true;
    setStatus("ready");
    setErrorMessage("");
    setNetworkRetryRequired(false);
    setNetworkRetryVisible(false);
    recordAudioDiagnostic("manual_recovery");
    audio.load();
    playAudio(audio, source, true);
  };

  const statusLabel =
    status === "preparing"
      ? "准备中"
      : status === "playing"
        ? "朗读中"
        : status === "paused"
          ? "已暂停"
          : status === "failed"
            ? "这一章暂时无法朗读"
            : readySegments.length > 0
              ? "已就绪"
              : "准备中";

  return (
    <section
      data-testid="story-listening-experience"
      className="relative -mx-4 min-h-[calc(100svh-9rem)] overflow-hidden border-y border-[var(--border-default)] bg-[var(--surface-reading)] px-4 py-8 sm:-mx-8 sm:px-8"
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center">
        <header className="w-full text-center">
          <h1 className="font-serif text-3xl font-semibold tracking-[0.12em] text-[var(--text-primary)] sm:text-4xl">
            听故事
          </h1>
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

        {activeAudioSource ? (
          <audio
            key={activeAudioSource}
            ref={(node) => {
              audioRef.current = node;
            }}
            src={activeAudioSource}
            preload="auto"
            aria-hidden="true"
            data-active="true"
            onLoadedMetadata={(event) => handleLoadedMetadata(event.currentTarget, activeAudioSource)}
            onCanPlay={(event) => handleCanPlay(event.currentTarget, activeAudioSource)}
            onPlaying={(event) => handlePlaying(event.currentTarget, activeAudioSource)}
            onWaiting={(event) => scheduleRecoveryWatchdog(event.currentTarget, activeAudioSource, "waiting")}
            onStalled={(event) => scheduleRecoveryWatchdog(event.currentTarget, activeAudioSource, "stalled")}
            onEnded={(event) => handleEnded(event.currentTarget, activeAudioSource)}
            onTimeUpdate={(event) => handleTimeUpdate(event.currentTarget, activeAudioSource)}
            onError={(event) => scheduleRecoveryWatchdog(event.currentTarget, activeAudioSource, "error")}
          />
        ) : null}

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
            {!transcriptOpen ? (
              <Button
                type="button"
                variant="quiet"
                size="touch"
                onClick={() => setTranscriptOpen(true)}
              >
                <BookOpenText className="mr-2 h-4 w-4" />
                查看正文
              </Button>
            ) : null}
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
          {networkRetryVisible ? (
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
                收起正文 <ChevronUp className="ml-1 h-4 w-4" />
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
        ) : null}

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
