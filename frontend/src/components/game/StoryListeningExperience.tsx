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
import { pollStoryVoiceJob } from "@/lib/storyVoicePolling";
import { createStoryVoiceProgressSession } from "@/lib/storyVoiceProgress";
import { storyVoiceTextToHash } from "@/lib/storyVoiceTextHash";
import type {
  EventOption,
  ReadingContext,
  VoiceReadingJobResponse,
  VoiceReadingProgress,
  VoiceReadingSegment,
  MiniMaxVoiceOption,
} from "@/lib/types";
import { cn } from "@/lib/utils";

import { OptionCards } from "./OptionCards";
import { VoicePicker } from "./VoicePicker";

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

const SPEEDS = [0.75, 1, 1.25, 1.5];
const DEFAULT_VOICE_ID = "female-shaonv";
const LEGACY_VOICE_IDS: Record<string, string> = {
  warm_female: "female-shaonv",
  calm_male: "male-qn-qingse",
  clear_neutral: "female-yujie",
};
const FALLBACK_VOICE_IDS = new Set([
  "female-shaonv",
  "male-qn-qingse",
  "female-yujie",
  "female-chengshu",
]);
const STALL_WATCHDOG_MS = 8_000;

function splitParagraphs(text: string): string[] {
  return text
    .replace(/\r\n?/g, "\n")
    .trim()
    .split(/\n\s*\n+/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

function browserSpeechAvailable(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.speechSynthesis !== "undefined" &&
    typeof window.SpeechSynthesisUtterance !== "undefined"
  );
}

function buildBrowserSpeechSegments(
  paragraphs: string[],
  speed: number,
): VoiceReadingSegment[] {
  const durations = paragraphs.map((paragraph) =>
    Math.max(1_000, Math.round((paragraph.length * 70) / Math.max(speed, 0.1))),
  );
  let startMs = 0;
  return paragraphs.map((_, paragraphIndex) => {
    const durationMs = durations[paragraphIndex];
    const segment = {
      paragraph_index: paragraphIndex,
      status: "ready",
      audio_url: null,
      asset_id: null,
      duration_ms: durationMs,
      start_ms: startMs,
      end_ms: startMs + durationMs,
      media_type: "text/speech",
    } satisfies VoiceReadingSegment;
    startMs += durationMs;
    return segment;
  });
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
  const browserUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const browserFallbackRef = useRef(false);
  const previousIdentityRef = useRef("");
  const [providerChapterSource, setProviderChapterSource] = useState<string | null>(null);
  const providerSegmentsRef = useRef<VoiceReadingSegment[]>([]);
  const replacementPendingScenesRef = useRef(new Set<number>());
  const restoreProviderRef = useRef(false);
  const pollControllerRef = useRef<AbortController | null>(null);
  const progressSessionRef = useRef<ReturnType<typeof createStoryVoiceProgressSession> | null>(null);
  const finalSegmentEndedRef = useRef(false);
  const activeAudioSourceRef = useRef<string | null>(null);
  const mediaIsChapterRef = useRef(true);
  const recoveredParagraphsRef = useRef(new Set<number>());

  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [textHash, setTextHash] = useState("");
  const [hashedStory, setHashedStory] = useState<string | null>(null);
  const [segments, setSegments] = useState<VoiceReadingSegment[]>([]);
  const [jobId, setJobId] = useState<number | null>(null);
  const [status, setStatus] = useState<ListeningStatus>("preparing");
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedVoice, setSelectedVoice] = useState(DEFAULT_VOICE_ID);
  const [voiceCatalog, setVoiceCatalog] = useState<MiniMaxVoiceOption[]>([]);
  const [previewingVoice, setPreviewingVoice] = useState<string | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const [speed, setSpeed] = useState(1);
  const [autoRead, setAutoRead] = useState(true);
  const [activeParagraph, setActiveParagraph] = useState(0);
  const [positionMs, setPositionMs] = useState(0);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const [chapterMediaDurationMs, setChapterMediaDurationMs] = useState<number | null>(null);
  const [networkRetryRequired, setNetworkRetryRequired] = useState(false);
  const [networkRetryVisible, setNetworkRetryVisible] = useState(false);
  const [browserFallback, setBrowserFallback] = useState(false);
  const [providerFailed, setProviderFailed] = useState(false);
  const [connectionRetrying, setConnectionRetrying] = useState(false);
  const [providerReady, setProviderReady] = useState(false);
  const [queueAdvancePending, setQueueAdvancePending] = useState(false);

  const currentSegment = segments.find(
    (segment) => segment.paragraph_index === activeParagraph,
  );
  const previewVoice = async (voiceId: string) => {
    previewAudioRef.current?.pause();
    setPreviewingVoice(voiceId);
    try {
      const preview = await api.voice_reading.preview(voiceId);
      const audio = new Audio(preview.audio_url);
      previewAudioRef.current = audio;
      audio.onended = () => setPreviewingVoice(null);
      await audio.play();
    } catch (error) {
      setPreviewingVoice(null);
      setErrorMessage(error instanceof Error ? error.message : "音色试听失败");
    }
  };
  const chapterSegment = segments.find((segment) => segment.audio_url);
  const sceneQueueMode = !browserFallback && segments.some((segment) => segment.audio_url) && (segments.some((segment) => !segment.audio_url) || new Set(segments.map((segment) => segment.audio_url)).size > 1);
  const activeSegment = segments.find((segment) => segment.paragraph_index === activeParagraph);
  const activeAudioSource = hashedStory !== storyText ? null : sceneQueueMode
    ? activeSegment?.audio_url ?? null
    : chapterSegment?.audio_url ?? null;
  const mediaIsChapter = !sceneQueueMode || activeAudioSource === providerChapterSource;
  useLayoutEffect(() => {
    activeAudioSourceRef.current = activeAudioSource;
    mediaIsChapterRef.current = mediaIsChapter;
  }, [activeAudioSource, mediaIsChapter]);
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
  const totalDurationMs = chapterMediaDurationMs ?? (
    sceneQueueMode
      ? segments.reduce((total, segment) => total + segmentDuration(segment), 0)
      : declaredDurationMs
  );
  const elapsedBeforeCurrent = sceneQueueMode
    ? segments
      .filter((segment) => segment.paragraph_index < activeParagraph)
      .reduce((total, segment) => total + segmentDuration(segment), 0)
    : currentSegment?.start_ms
      ?? segments
        .filter((segment) => segment.paragraph_index < activeParagraph)
        .reduce((total, segment) => total + segmentDuration(segment), 0);
  const chapterPositionMs = Math.min(
    totalDurationMs,
    elapsedBeforeCurrent + positionMs,
  );
  const progressRatio = totalDurationMs > 0 ? chapterPositionMs / totalDurationMs : 0;

  const locateChapterPosition = (milliseconds: number) => {
    if (!mediaIsChapter) return { paragraphIndex: activeParagraphRef.current, paragraphPositionMs: milliseconds };
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
    if (browserSpeechAvailable()) window.speechSynthesis.cancel();
    browserUtteranceRef.current = null;
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
    let active = true;
    const audio = audioRef.current;
    void Promise.all([api.voice_reading.getSettings(), storyVoiceTextToHash(storyText)])
      .then(([settings, hash]) => {
        if (!active) return;
        const catalog = (settings.voice_catalog || []).filter((voice) =>
          voice.language === "普通话" || voice.language === "粤语",
        );
        const canonicalVoice = LEGACY_VOICE_IDS[settings.selected_voice_color || ""]
          || settings.selected_voice_color
          || DEFAULT_VOICE_ID;
        const availableVoiceIds = catalog.length > 0
          ? new Set(catalog.map((voice) => voice.voice_id))
          : FALLBACK_VOICE_IDS;
        setSelectedVoice(availableVoiceIds.has(canonicalVoice) ? canonicalVoice : DEFAULT_VOICE_ID);
        setVoiceCatalog(catalog);
        setSpeed(settings.selected_speed || 1);
        setAutoRead(settings.auto_read_enabled);
        autoReadRef.current = settings.auto_read_enabled;
        autoPlayRequestedRef.current = settings.auto_read_enabled;
        setTextHash(hash);
        setHashedStory(storyText);
        setSettingsLoaded(true);
      })
      .catch((error) => {
        if (!active) return;
        setStatus("failed");
        setErrorMessage(error instanceof Error ? error.message : "无法读取朗读设置");
      });
    return () => {
      active = false;
      generationRef.current += 1;
      clearRecoveryWatchdog();
      playbackGenerationRef.current += 1;
      playRequestRef.current = null;
      playingAudioRef.current = null;
      if (audio) audio.pause();
      if (browserSpeechAvailable()) window.speechSynthesis.cancel();
      browserUtteranceRef.current = null;
    };
  }, [storyText]);

  const enableBrowserFallback = () => {
    if (!browserSpeechAvailable()) {
      setStatus("failed");
      setErrorMessage("高质量语音生成失败，当前浏览器也不支持语音朗读");
      return;
    }
    cancelActivePlayback();
    browserFallbackRef.current = true;
    setBrowserFallback(true);
    setSegments(buildBrowserSpeechSegments(paragraphs, speed));
    setChapterMediaDurationMs(null);
    setStatus("ready");
    setErrorMessage("高质量语音暂时不可用，已切换浏览器朗读");
  };

  const applyJob = useCallback((job: VoiceReadingJobResponse) => {
    const sharedAudioUrl = job.segments.length > 1 && job.segments.every((segment) => segment.audio_url === job.segments[0].audio_url)
      ? job.segments[0].audio_url : null;
    const chapterAudioUrl = job.status === "ready" ? job.audio_url ?? sharedAudioUrl : null;
    if (chapterAudioUrl) setProviderChapterSource(chapterAudioUrl);
    const previous = providerSegmentsRef.current;
    let chapterPlaybackStarted = false;
    const normalizedSegments = job.segments.map((segment) => {
      const buffered = previous.find((value) => value.paragraph_index === segment.paragraph_index && value.audio_url);
      if (buffered && !segment.audio_url && segment.status !== "ready") {
        replacementPendingScenesRef.current.add(segment.paragraph_index);
      }
      // Retain the current buffer while its replacement is absent. Once ready,
      // accept a regenerated scene or the completed chapter from a retry.
      // Once playback enters the chapter, all later paragraphs must share its
      // clock. A retained scene after a chapter cue would reintroduce local
      // start_ms=0 and could switch the source while crossing a chapter cue.
      const replacement = chapterAudioUrl && (chapterPlaybackStarted || replacementPendingScenesRef.current.has(segment.paragraph_index))
        ? { ...segment, audio_url: chapterAudioUrl }
        : segment.audio_url && segment.audio_url !== chapterAudioUrl
          ? segment
          : null;
      if (replacement) {
        if (replacement.audio_url === chapterAudioUrl) chapterPlaybackStarted = true;
        if (replacement.audio_url !== buffered?.audio_url) {
          replacementPendingScenesRef.current.delete(segment.paragraph_index);
        }
        if (
          buffered && buffered.audio_url !== replacement.audio_url &&
          segment.paragraph_index === activeParagraphRef.current &&
          buffered.audio_url === activeAudioSourceRef.current &&
          !browserFallbackRef.current && audioRef.current &&
          pendingSavedProgressRef.current === null
        ) {
          // A pending seek/recovery still uses the old source's clock. Preserve
          // that intent as paragraph-local progress before loading new cues.
          const resumeMs = pendingResumePositionRef.current ?? audioRef.current.currentTime * 1000;
          pendingSavedProgressRef.current = {
            paragraphIndex: segment.paragraph_index,
            positionMs: Math.max(0, resumeMs - (mediaIsChapterRef.current ? buffered.start_ms ?? 0 : 0)),
          };
          pendingResumePositionRef.current = null;
          setChapterMediaDurationMs(null);
        }
        return replacement;
      }
      const retained = buffered ?? (segment.audio_url || !chapterAudioUrl ? segment : { ...segment, audio_url: chapterAudioUrl });
      if (chapterAudioUrl && retained.audio_url === chapterAudioUrl) chapterPlaybackStarted = true;
      return retained;
    });
    providerSegmentsRef.current = normalizedSegments;
    setProviderFailed(job.status === "failed");
    setProviderReady(job.status === "ready");
    if (browserFallbackRef.current) return;
    setSegments(normalizedSegments);
    const playable = normalizedSegments.some((segment) => segment.audio_url);
    if (job.status === "failed") setErrorMessage(job.message || "部分语音生成失败，可重试或使用系统朗读");
    setStatus((current) => {
      if (current === "playing" || current === "paused") return current;
      return playable ? "ready" : job.status === "failed" ? "failed" : "preparing";
    });
  }, []);

  useEffect(() => {
    if (!settingsLoaded || !textHash || hashedStory !== storyText || context.source_type !== "current_story") return;
    const generation = ++generationRef.current;
    let active = true;
    const controller = new AbortController();
    pollControllerRef.current = controller;
    const identity = {
      game_id: context.game_id,
      day_index: context.day_index ?? 0,
      text_hash: textHash,
      voice_id: selectedVoice,
      speed,
    };
    const identityKey = JSON.stringify([identity, context.attempt_id, context.stage, context.week, context.round_number, context.story_date]);
    const continuing = previousIdentityRef.current === identityKey;
    previousIdentityRef.current = identityKey;
    setProviderFailed(false);
    setConnectionRetrying(false);
    if (!continuing) {
      providerSegmentsRef.current = [];
      replacementPendingScenesRef.current.clear();
      setProviderChapterSource(null);
      restoreProviderRef.current = false;
      setProviderReady(false);
      setJobId(null);
      setStatus("preparing");
      setErrorMessage("");
      browserFallbackRef.current = false;
      setBrowserFallback(false);
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
      setQueueAdvancePending(false);
    } else if (retryNonce > 0) {
      // The worker may invalidate and rebuild a cached scene between polls.
      // Keep it playable for now, but accept the retry's final chapter even
      // when no intermediate response exposed that invalidation.
      for (const segment of providerSegmentsRef.current) {
        if (segment.audio_url) replacementPendingScenesRef.current.add(segment.paragraph_index);
      }
    }

    const run = async () => {
      try {
        if (!continuing) {
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
        }

        if (!active || generation !== generationRef.current) return;
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
          force_retry: retryNonce > 0,
        }, controller.signal);
        if (!active || generation !== generationRef.current) return;
        setJobId(response.job_id);
        applyJob(response);

        await pollStoryVoiceJob(response, controller.signal, (job) => {
          if (active && generation === generationRef.current) applyJob(job);
        }, (retrying) => {
          if (active && generation === generationRef.current) setConnectionRetrying(retrying);
        }, () => browserFallbackRef.current);
      } catch (error) {
        if (!active || generation !== generationRef.current) return;
        setProviderFailed(true);
        setStatus((current) => providerSegmentsRef.current.some((segment) => segment.audio_url) ? current : "failed");
        setErrorMessage(error instanceof Error ? error.message : "高质量语音生成失败");
      }
    };
    void run();
    return () => {
      active = false;
      controller.abort();
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
    hashedStory,
    speed,
    storyText,
    textHash,
  ]);

  useLayoutEffect(() => {
    const session = createStoryVoiceProgressSession();
    progressSessionRef.current = session;
    return () => {
      session.release();
      progressSessionRef.current = null;
    };
  }, [context.attempt_id, context.day_index, context.game_id, context.round_number, context.source_type, context.stage, context.story_date, context.week, selectedVoice, speed, storyText, textHash]);

  const persistProgress = useCallback(
    (paragraphIndex: number, milliseconds: number, completed = false, retainAfterRelease = false) => {
      if (!textHash || hashedStory !== storyText) return;
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
      progressSessionRef.current?.write(progress, retainAfterRelease);
    },
    [context.day_index, context.game_id, context.story_date, hashedStory, selectedVoice, speed, storyText, textHash],
  );

  const restoreProvider = (paragraphIndex: number) => {
    const complete = paragraphIndex >= paragraphs.length;
    const nextIndex = Math.min(paragraphIndex, paragraphs.length - 1);
    const providerSegments = providerSegmentsRef.current;
    browserFallbackRef.current = false;
    setBrowserFallback(false);
    browserUtteranceRef.current = null;
    setSegments(providerSegments);
    setChapterMediaDurationMs(null);
    setActiveParagraph(nextIndex);
    activeParagraphRef.current = nextIndex;
    setPositionMs(0);
    pendingSavedProgressRef.current = { paragraphIndex: nextIndex, positionMs: 0 };
    pendingResumePositionRef.current = null;
    finalSegmentEndedRef.current = complete;
    if (complete) autoPlayRequestedRef.current = false;
    setStatus(autoPlayRequestedRef.current ? "ready" : "paused");
    setErrorMessage("");
  };

  const speakBrowserParagraph = (paragraphIndex: number) => {
    if (!browserFallbackRef.current || !browserSpeechAvailable()) return;
    const text = paragraphs[paragraphIndex];
    if (!text) return;
    const generation = ++playbackGenerationRef.current;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = speed;
    const chineseVoice = window.speechSynthesis
      .getVoices()
      .find((voice) => voice.lang.toLowerCase().startsWith("zh"));
    if (chineseVoice) utterance.voice = chineseVoice;
    utterance.onstart = () => {
      if (generation !== playbackGenerationRef.current) return;
      setActiveParagraph(paragraphIndex);
      activeParagraphRef.current = paragraphIndex;
      setPositionMs(0);
      setStatus("playing");
      setErrorMessage("");
    };
    utterance.onend = () => {
      if (generation !== playbackGenerationRef.current) return;
      const duration = segments.find((segment) => segment.paragraph_index === paragraphIndex)?.duration_ms ?? 0;
      persistProgress(paragraphIndex, duration, paragraphIndex === paragraphs.length - 1);
      if (restoreProviderRef.current) {
        restoreProviderRef.current = false;
        restoreProvider(paragraphIndex + 1);
        return;
      }
      if (paragraphIndex < paragraphs.length - 1 && autoPlayRequestedRef.current) {
        const nextParagraph = paragraphIndex + 1;
        setActiveParagraph(nextParagraph);
        activeParagraphRef.current = nextParagraph;
        setPositionMs(0);
        speakBrowserParagraph(nextParagraph);
        return;
      }
      autoPlayRequestedRef.current = false;
      setPositionMs(duration);
      setStatus("ready");
    };
    utterance.onerror = (event) => {
      if (generation !== playbackGenerationRef.current) return;
      if (event.error === "canceled" || event.error === "interrupted") return;
      setStatus("failed");
      setErrorMessage("浏览器语音朗读失败，请点击重试");
    };
    browserUtteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  };

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
        if (mediaIsChapter) setChapterMediaDurationMs(durationMs);
      }
      if (pendingSavedProgressRef.current !== null) {
        const saved = pendingSavedProgressRef.current;
        const savedSegment = segments.find(
          (segment) => segment.paragraph_index === saved.paragraphIndex,
        );
        if (savedSegment?.start_ms != null) {
          pendingResumePositionRef.current = (mediaIsChapter ? savedSegment.start_ms : 0) + saved.positionMs;
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

  useEffect(() => {
    if (!queueAdvancePending || !sceneQueueMode) return;
    const nextSegment = segments
      .filter((segment) => segment.paragraph_index === activeParagraph + 1 && segment.audio_url)
      .sort((left, right) => left.paragraph_index - right.paragraph_index)[0];
    if (!nextSegment) return;
    setQueueAdvancePending(false);
    pendingSavedProgressRef.current = { paragraphIndex: nextSegment.paragraph_index, positionMs: 0 };
    pendingResumePositionRef.current = null;
    setActiveParagraph(nextSegment.paragraph_index);
    activeParagraphRef.current = nextSegment.paragraph_index;
    setPositionMs(0);
    autoPlayRequestedRef.current = true;
    finalSegmentEndedRef.current = false;
    persistProgress(nextSegment.paragraph_index, 0);
  }, [activeParagraph, persistProgress, queueAdvancePending, sceneQueueMode, segments]);

  const chooseParagraph = (index: number) => {
    const targetSegment = segments.find((segment) => segment.paragraph_index === index);
    const targetPositionMs = sceneQueueMode && targetSegment?.audio_url !== providerChapterSource ? 0 : targetSegment?.start_ms;
    cancelActivePlayback();
    setActiveParagraph(index);
    activeParagraphRef.current = index;
    setPositionMs(0);
    pendingSavedProgressRef.current = targetPositionMs == null
      ? { paragraphIndex: index, positionMs: 0 }
      : null;
    pendingResumePositionRef.current = targetPositionMs ?? null;
    autoPlayRequestedRef.current = true;
    finalSegmentEndedRef.current = false;
    setNetworkRetryRequired(false);
    setNetworkRetryVisible(false);
    persistProgress(index, 0);
    if (browserFallback) {
      speakBrowserParagraph(index);
      return;
    }
    const audio = audioRef.current;
    if (
      audio &&
      activeAudioSource &&
      targetSegment?.audio_url === activeAudioSource &&
      targetPositionMs != null &&
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
    if (!mediaIsChapter && activeParagraph < paragraphs.length - 1) {
      const nextSegment = segments
        .filter((segment) => segment.paragraph_index > activeParagraph)
        .sort((left, right) => left.paragraph_index - right.paragraph_index)[0];
      if (nextSegment?.audio_url) {
        pendingSavedProgressRef.current = { paragraphIndex: nextSegment.paragraph_index, positionMs: 0 };
        pendingResumePositionRef.current = null;
        setActiveParagraph(nextSegment.paragraph_index);
        activeParagraphRef.current = nextSegment.paragraph_index;
        setPositionMs(0);
        autoPlayRequestedRef.current = true;
        finalSegmentEndedRef.current = false;
        persistProgress(nextSegment.paragraph_index, 0);
        return;
      }
      setQueueAdvancePending(true);
      setStatus("preparing");
      autoPlayRequestedRef.current = true;
      return;
    }
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
    const paragraphIndex = activeParagraphRef.current;
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
    const firstSegment = segments.at(0);
    const timedSegment = segments.find((segment, index) => {
      if (segment.start_ms == null) return false;
      const endMs = segment.end_ms
        ?? segments[index + 1]?.start_ms
        ?? totalDurationMs;
      return chapterMilliseconds >= segment.start_ms && chapterMilliseconds < endMs;
    }) ?? (
      firstSegment?.start_ms != null && chapterMilliseconds < firstSegment.start_ms
        ? firstSegment
        : segments.at(-1)
    );
    const paragraphIndex = !mediaIsChapter ? activeParagraphRef.current : timedSegment?.paragraph_index ?? activeParagraphRef.current;
    const paragraphStartMs = !mediaIsChapter ? 0 : timedSegment?.start_ms ?? 0;
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
    if (now - lastProgressWriteRef.current >= 5_000) {
      lastProgressWriteRef.current = now;
      persistProgress(paragraphIndex, milliseconds);
    }
  };

  const handlePrimaryAction = () => {
    if (browserFallback) {
      if (status === "playing") {
        cancelActivePlayback();
        autoPlayRequestedRef.current = false;
        setStatus("paused");
        const duration = currentSegment?.duration_ms ?? 0;
        persistProgress(activeParagraph, duration);
        return;
      }
      autoPlayRequestedRef.current = true;
      if (finalSegmentEndedRef.current) {
        setActiveParagraph(0);
        activeParagraphRef.current = 0;
        setPositionMs(0);
        finalSegmentEndedRef.current = false;
        speakBrowserParagraph(0);
      } else {
        speakBrowserParagraph(activeParagraph);
      }
      return;
    }
    const audio = audioRef.current;
    if (!audio) return;
    if (status === "playing") {
      cancelActivePlayback();
      autoPlayRequestedRef.current = false;
      setStatus("paused");
      const startMs = !mediaIsChapter ? 0 : currentSegment?.start_ms ?? elapsedBeforeCurrent;
      persistProgress(
        activeParagraph,
        Math.max(0, audio.currentTime * 1000 - startMs),
      );
      return;
    }
    autoPlayRequestedRef.current = true;
    if (finalSegmentEndedRef.current) {
      if (sceneQueueMode) {
        chooseParagraph(0);
        return;
      }
      audio.currentTime = 0;
      pendingResumePositionRef.current = 0;
      setPositionMs(0);
      finalSegmentEndedRef.current = false;
    }
    if (activeAudioSource) playAudio(audio, activeAudioSource, true);
  };

  const handleRestart = () => {
    if (browserFallback) {
      cancelActivePlayback();
      setActiveParagraph(0);
      activeParagraphRef.current = 0;
      setPositionMs(0);
      autoPlayRequestedRef.current = true;
      finalSegmentEndedRef.current = false;
      setStatus("ready");
      speakBrowserParagraph(0);
      return;
    }
    chooseParagraph(0);
  };

  const handleSeek = (event: ChangeEvent<HTMLInputElement>) => {
    const target = Number(event.target.value);
    const segment = segments.find((candidate, index) => {
      const startMs = (sceneQueueMode ? undefined : candidate.start_ms)
        ?? segments
          .slice(0, index)
          .reduce((total, value) => total + segmentDuration(value), 0);
      const endMs = (sceneQueueMode ? undefined : candidate.end_ms) ?? startMs + segmentDuration(candidate);
      return target >= startMs && (target < endMs || candidate === segments.at(-1));
    }) ?? segments.at(-1);
    if (!segment) return;
    const startMs = (sceneQueueMode ? undefined : segment.start_ms)
      ?? segments
        .filter((candidate) => candidate.paragraph_index < segment.paragraph_index)
        .reduce((total, value) => total + segmentDuration(value), 0);
    const paragraphPositionMs = Math.max(0, target - startMs);
    const wasPlaying = status === "playing";
    if (browserFallback) {
      cancelActivePlayback();
      setActiveParagraph(segment.paragraph_index);
      activeParagraphRef.current = segment.paragraph_index;
      setPositionMs(0);
      pendingResumePositionRef.current = null;
      autoPlayRequestedRef.current = wasPlaying;
      setStatus(wasPlaying ? "playing" : "paused");
      persistProgress(segment.paragraph_index, 0);
      if (wasPlaying) speakBrowserParagraph(segment.paragraph_index);
      return;
    }
    const audio = audioRef.current;
    cancelActivePlayback();
    setActiveParagraph(segment.paragraph_index);
    activeParagraphRef.current = segment.paragraph_index;
    setPositionMs(paragraphPositionMs);
    pendingSavedProgressRef.current = null;
    const targetIsChapter = !sceneQueueMode || segment.audio_url === providerChapterSource;
    pendingResumePositionRef.current = targetIsChapter ? target : paragraphPositionMs;
    autoPlayRequestedRef.current = wasPlaying;
    finalSegmentEndedRef.current = false;
    setNetworkRetryRequired(false);
    setNetworkRetryVisible(false);
    persistProgress(segment.paragraph_index, paragraphPositionMs);
    if (
      audio &&
      activeAudioSource &&
      segment.audio_url === activeAudioSource &&
      isCurrentAudio(audio, activeAudioSource) &&
      audio.readyState >= HTMLMediaElement.HAVE_METADATA
    ) {
      audio.currentTime = (targetIsChapter ? target : paragraphPositionMs) / 1000;
      pendingResumePositionRef.current = null;
      if (wasPlaying) playAudio(audio, activeAudioSource, true);
    }
  };

  const handleVoiceSelect = (value: string) => {
    cancelActivePlayback();
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
      const startMs = !mediaIsChapter ? 0 : currentSegment?.start_ms ?? elapsedBeforeCurrent;
      persistProgress(
        activeParagraph,
        Math.max(0, audio.currentTime * 1000 - startMs),
        false,
        true,
      );
    }
    generationRef.current += 1;
    pollControllerRef.current?.abort();
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
      if (mediaIsChapter) setChapterMediaDurationMs(durationMs);
    }
    if (pendingSavedProgressRef.current !== null) {
      const saved = pendingSavedProgressRef.current;
      const savedSegment = segments.find(
        (segment) => segment.paragraph_index === saved.paragraphIndex,
      );
      if (savedSegment?.start_ms != null) {
        pendingResumePositionRef.current = (mediaIsChapter ? savedSegment.start_ms : 0) + saved.positionMs;
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
            : browserFallback
              ? "浏览器朗读可用"
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
              disabled={status === "preparing" || (!currentSegment?.audio_url && !browserFallback)}
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

          <VoicePicker
            voices={voiceCatalog}
            selectedVoiceId={selectedVoice}
            previewingVoice={previewingVoice}
            onSelectVoice={handleVoiceSelect}
            onPreviewVoice={(voiceId) => void previewVoice(voiceId)}
          />

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
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
          {connectionRetrying ? <p role="status" className="mt-4 text-center text-sm">连接较慢，正在重试；已缓存的语音仍可播放</p> : null}
          {!browserFallback && (providerFailed || connectionRetrying || (status === "preparing" && jobId !== null)) && browserSpeechAvailable() ? (
            <Button type="button" variant="quiet" onClick={enableBrowserFallback}>使用系统朗读</Button>
          ) : null}
          {browserFallback && providerReady ? (
            <Button type="button" variant="quiet" onClick={() => {
              if (status === "playing" && browserUtteranceRef.current) {
                restoreProviderRef.current = true;
                setErrorMessage("将在当前段落结束后恢复原音色");
              } else restoreProvider(activeParagraphRef.current);
            }}>恢复原音色</Button>
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
          ) : providerFailed ? (
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
