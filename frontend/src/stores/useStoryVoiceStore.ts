"use client";

import { create } from "zustand";
import { api } from "@/lib/api";
import { storyVoiceTextToHash } from "@/lib/storyVoiceTextHash";
import { useMusicStore } from "@/stores/useMusicStore";
import type { ReadingContext } from "@/lib/types";

export type VoiceReadingState = "idle" | "loading" | "ready" | "playing" | "paused" | "failed";
export type MusicDuckState = "idle" | "playing" | "ducked" | "restored" | "user_paused";
export type StoryVoicePlaybackMode = "none" | "browser_speech" | "audio";

interface StoryVoiceState {
  readingState: VoiceReadingState;
  currentSource: string;
  currentContextLabel: string;
  currentAudioUrl: string;
  currentJobId: number | null;
  currentProvider: string;
  playbackMode: StoryVoicePlaybackMode;
  spokenTextLength: number;
  currentSpeechText: string;
  errorMessage: string;
  queueText: string;
  autoReadEnabled: boolean;
  selectedVoiceId: string;
  ttsProvider: string;
  backendAudioEnabled: boolean;
  musicDuckState: MusicDuckState;
  musicWasPlaying: boolean;
  userChangedMusic: boolean;
  activeReadingContext: ReadingContext | null;
  activeAutoReadText: string;
  activeAutoReadReady: boolean;
  setActiveReadingTarget: (target: {
    context: ReadingContext;
    autoReadText: string;
    autoReadReady: boolean;
  }) => void;
  clearActiveReadingTarget: () => void;
  startReading: (context: ReadingContext, options?: { voiceId?: string }) => Promise<void>;
  pauseReading: () => void;
  stopReading: () => void;
  completeReading: () => void;
  retryReading: () => void;
  markAudioPlaying: () => void;
  markAudioReady: (message?: string) => void;
  failReading: (error?: unknown) => void;
  setAutoReadEnabled: (enabled: boolean) => void;
  setSelectedVoiceId: (voiceId: string) => void;
  setVoiceRuntimeSettings: (settings: {
    ttsProvider?: string | null;
    backendAudioEnabled?: boolean | null;
  }) => void;
  enqueueCompletedAttempt: (text: string) => void;
  simulateMusicPlaying: () => void;
  userPauseMusicDuringReading: () => void;
}

type ApiError = Error & { status?: number };

function contextLabel(context: ReadingContext): string {
  const parts = [];
  if (context.week !== undefined && context.week !== null) parts.push(`week=${context.week}`);
  if (context.round_number !== undefined && context.round_number !== null) {
    parts.push(`round=${context.round_number}`);
  }
  if (context.stage) parts.push(`stage=${context.stage}`);
  return parts.join(" ");
}

function readingRequestKey(context: ReadingContext, voiceId: string): string {
  return [
    voiceId,
    context.source_type,
    context.game_id ?? "",
    context.week ?? "",
    context.round_number ?? "",
    context.stage ?? "",
    context.attempt_id ?? "",
    context.text_hash ?? "",
    context.text,
  ].join("\u001f");
}

async function normalizeTextHash(text: string): Promise<string> {
  return storyVoiceTextToHash(text);
}

let activeUtterance: SpeechSynthesisUtterance | null = null;
let activeReadingAttempt = 0;
const inFlightReadingRequests = new Set<string>();
let activeLoadingRequestKey: string | null = null;
let activeLoadingStartedAt = 0;
let runtimeSettingsRequest: Promise<void> | null = null;
const ACTIVE_READING_DEDUPE_MS = 10_000;

function getSpeechSynthesis(): SpeechSynthesis | null {
  if (typeof window === "undefined") return null;
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) return null;
  return window.speechSynthesis;
}

function detectSpeechLanguage(text: string): string {
  return /[\u3400-\u9fff]/.test(text) ? "zh-CN" : "en-US";
}

const BROWSER_SPEECH_CHUNK_MAX = 200;

function splitBrowserSpeechText(text: string): string[] {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return [];

  const chunks: string[] = [];
  let current = "";
  const sentences = normalized.match(/[^。！？!?；;]+[。！？!?；;]?/g) ?? [normalized];

  for (const sentence of sentences) {
    const trimmed = sentence.trim();
    if (!trimmed) continue;

    if (trimmed.length > BROWSER_SPEECH_CHUNK_MAX) {
      if (current) {
        chunks.push(current);
        current = "";
      }
      for (let index = 0; index < trimmed.length; index += BROWSER_SPEECH_CHUNK_MAX) {
        chunks.push(trimmed.slice(index, index + BROWSER_SPEECH_CHUNK_MAX));
      }
      continue;
    }

    const next = current ? `${current}${trimmed}` : trimmed;
    if (next.length > BROWSER_SPEECH_CHUNK_MAX && current) {
      chunks.push(current);
      current = trimmed;
    } else {
      current = next;
    }
  }

  if (current) chunks.push(current);
  return chunks.length ? chunks : [normalized];
}

const BROWSER_VOICE_CUES: Record<string, string[]> = {
  warm_female: [
    "female",
    "woman",
    "xiaoxiao",
    "xiaoyi",
    "xiaobei",
    "xiaoqiu",
    "xiaoshuang",
    "huihui",
    "yaoyao",
    "tingting",
    "mei",
  ],
  calm_male: [
    "male",
    "man",
    "yunxi",
    "yunjian",
    "kang",
    "hao",
    "kangkang",
  ],
  clear_neutral: [
    "neutral",
    "natural",
    "mandarin",
    "chinese",
    "普通话",
    "中文",
  ],
};

function isChineseVoice(voice: SpeechSynthesisVoice): boolean {
  const haystack = `${voice.lang} ${voice.name} ${voice.voiceURI}`.toLowerCase();
  return (
    haystack.includes("zh") ||
    haystack.includes("cmn") ||
    haystack.includes("mandarin") ||
    haystack.includes("chinese") ||
    haystack.includes("普通话") ||
    haystack.includes("中文")
  );
}

function selectBrowserSpeechVoice(
  speech: SpeechSynthesis,
  voiceId: string,
  language: string
): SpeechSynthesisVoice | null {
  const voices = typeof speech.getVoices === "function" ? speech.getVoices() : [];
  if (!voices.length) return null;

  const languageVoices =
    language.toLowerCase().startsWith("zh")
      ? voices.filter(isChineseVoice)
      : voices.filter((voice) => voice.lang?.toLowerCase().startsWith(language.toLowerCase()));
  const candidates = languageVoices.length ? languageVoices : voices;
  const cues = BROWSER_VOICE_CUES[voiceId] ?? BROWSER_VOICE_CUES.warm_female;
  const matchesCue = (haystack: string, cue: string) => {
    if (cue === "male") return /\bmale\b/.test(haystack) && !/\bfemale\b/.test(haystack);
    if (cue === "man") return /\bman\b/.test(haystack);
    return haystack.includes(cue);
  };
  const matched = candidates.find((voice) => {
    const haystack = `${voice.name} ${voice.voiceURI} ${voice.lang}`.toLowerCase();
    return cues.some((cue) => matchesCue(haystack, cue));
  });
  return matched ?? candidates[0] ?? null;
}

function restoredMusicDuckState(
  musicDuckState: MusicDuckState,
  userChangedMusic: boolean
): MusicDuckState {
  return musicDuckState === "ducked" && !userChangedMusic ? "restored" : musicDuckState;
}

function duckMusicForReading(): boolean {
  return useMusicStore.getState().duckForVoiceReading();
}

function restoreMusicAfterReading(userChangedMusic: boolean): void {
  if (userChangedMusic) {
    return;
  }
  useMusicStore.getState().restoreAfterVoiceReading();
}

function buildReadingRequestKey(
  context: ReadingContext,
  voiceId: string,
  preferredProvider: string | null,
  textHash: string
): string {
  const requestTextHash = context.attempt_id ?? context.text_hash ?? textHash;
  return `${context.game_id}:${context.source_type}:${context.week ?? ""}:${context.round_number ?? ""}:${context.stage ?? ""}:${requestTextHash}:${voiceId}:${preferredProvider ?? "auto"}`;
}

function hashTextForRequest(text: string): string {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
    hash >>>= 0;
  }
  return hash.toString(16);
}

async function ensureRuntimeSettingsLoaded(
  get: () => StoryVoiceState,
  set: (
    partial:
      | Partial<StoryVoiceState>
      | ((state: StoryVoiceState) => Partial<StoryVoiceState>)
  ) => void
): Promise<boolean> {
  if (get().ttsProvider) return true;

  runtimeSettingsRequest ??= api.voice_reading
    .getSettings()
    .then((settings) => {
      set((state) => ({
        ttsProvider: settings.tts_provider ?? state.ttsProvider,
        backendAudioEnabled:
          settings.backend_audio_enabled ?? state.backendAudioEnabled,
      }));
    })
    .catch((error) => {
      console.warn(
        "[StoryVoiceStore] Voice runtime settings unavailable before reading:",
        error
      );
      throw error;
    })
    .finally(() => {
      runtimeSettingsRequest = null;
    });

  try {
    await runtimeSettingsRequest;
    return true;
  } catch {
    return false;
  }
}

export const useStoryVoiceStore = create<StoryVoiceState>((set, get) => ({
  readingState: "idle",
  currentSource: "",
  currentContextLabel: "",
  currentAudioUrl: "",
  currentJobId: null,
  currentProvider: "",
  playbackMode: "none",
  spokenTextLength: 0,
  currentSpeechText: "",
  errorMessage: "",
  queueText: "",
  autoReadEnabled: false,
  selectedVoiceId: "warm_female",
  ttsProvider: "",
  backendAudioEnabled: true,
  musicDuckState: "idle",
  musicWasPlaying: false,
  userChangedMusic: false,
  activeReadingContext: null,
  activeAutoReadText: "",
  activeAutoReadReady: false,

  setActiveReadingTarget: ({ context, autoReadText, autoReadReady }) =>
    set({
      activeReadingContext: context,
      activeAutoReadText: autoReadText,
      activeAutoReadReady: autoReadReady,
    }),
  clearActiveReadingTarget: () =>
    set({
      activeReadingContext: null,
      activeAutoReadText: "",
      activeAutoReadReady: false,
    }),

  startReading: async (context, options) => {
    const selectedVoiceId = options?.voiceId ?? get().selectedVoiceId;
    const preferredProvider =
      typeof window !== "undefined" ? window.localStorage.getItem("story_voice_e2e_provider") : null;
    const requestTextHash = hashTextForRequest(context.text);

    const requestKey = buildReadingRequestKey(
      context,
      selectedVoiceId,
      preferredProvider,
      requestTextHash
    );
    const now = Date.now();
    const matchingRequestIsLoading =
      get().readingState === "loading" && activeLoadingRequestKey === requestKey;
    if (
      matchingRequestIsLoading &&
      inFlightReadingRequests.has(requestKey) &&
      now - activeLoadingStartedAt < ACTIVE_READING_DEDUPE_MS
    ) {
      return;
    }
    inFlightReadingRequests.delete(requestKey);

    const attemptId = activeReadingAttempt + 1;
    activeReadingAttempt = attemptId;
    inFlightReadingRequests.add(requestKey);
    activeLoadingRequestKey = requestKey;
    activeLoadingStartedAt = now;
    const musicWasPlaying = duckMusicForReading() || get().musicWasPlaying;
    const browserSpeech = getSpeechSynthesis();
    browserSpeech?.getVoices?.();
    browserSpeech?.cancel();
    activeUtterance = null;
    set({
      readingState: "loading",
      currentSource: context.source_type,
      currentContextLabel: contextLabel(context),
      currentAudioUrl: "",
      currentJobId: null,
      currentProvider: "",
      currentSpeechText: browserSpeech ? context.text : "",
      playbackMode: browserSpeech ? "browser_speech" : "none",
      spokenTextLength: browserSpeech ? context.text.length : 0,
      errorMessage: "",
      musicDuckState: musicWasPlaying ? "ducked" : get().musicDuckState,
      userChangedMusic: false,
    });

    const startBrowserSpeech = (jobId: number | null) => {
      if (attemptId !== activeReadingAttempt) {
        return;
      }
      const speech = getSpeechSynthesis();
      if (!speech) {
        const { musicDuckState, userChangedMusic } = get();
        restoreMusicAfterReading(userChangedMusic);
        if (attemptId !== activeReadingAttempt) {
          return;
        }
        set({
          readingState: "failed",
          currentJobId: jobId,
          currentProvider: "browser",
          currentAudioUrl: "",
          playbackMode: "browser_speech",
          spokenTextLength: context.text.length,
          currentSpeechText: context.text,
          errorMessage: "Browser speech synthesis is unavailable",
          musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
        });
        activeLoadingRequestKey = null;
        activeLoadingStartedAt = 0;
        return;
      }

      if (attemptId !== activeReadingAttempt) {
        return;
      }
      set({
        readingState: "playing",
        currentAudioUrl: "",
        currentJobId: jobId,
        currentProvider: "browser",
        playbackMode: "browser_speech",
        spokenTextLength: context.text.length,
        currentSpeechText: context.text,
        errorMessage: "",
      });
      activeLoadingRequestKey = null;
      activeLoadingStartedAt = 0;
      speech.cancel();
      const chunks = splitBrowserSpeechText(context.text);
      const language = detectSpeechLanguage(context.text);
      const selectedVoice = selectBrowserSpeechVoice(
        speech,
        selectedVoiceId,
        language
      );
      let chunkIndex = 0;

      const failBrowserSpeech = () => {
        if (attemptId !== activeReadingAttempt) return;
        const { musicDuckState, userChangedMusic } = get();
        restoreMusicAfterReading(userChangedMusic);
        activeUtterance = null;
        set({
          readingState: "failed",
          currentAudioUrl: "",
          errorMessage: "Browser speech synthesis failed",
          playbackMode: "browser_speech",
          musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
        });
        activeLoadingRequestKey = null;
        activeLoadingStartedAt = 0;
      };

      const speakNextChunk = () => {
        if (attemptId !== activeReadingAttempt) return;
        const chunk = chunks[chunkIndex];
        if (!chunk) {
          activeUtterance = null;
          get().completeReading();
          return;
        }

        const utterance = new SpeechSynthesisUtterance(chunk);
        activeUtterance = utterance;
        utterance.lang = language;
        utterance.voice = selectedVoice;
        utterance.rate = 1;
        utterance.onend = () => {
          if (activeUtterance !== utterance || attemptId !== activeReadingAttempt) {
            return;
          }
          chunkIndex += 1;
          speakNextChunk();
        };
        utterance.onerror = () => {
          if (activeUtterance === utterance) {
            failBrowserSpeech();
          }
        };
        speech.speak(utterance);
      };

      speakNextChunk();
    };

    if (!preferredProvider && !get().ttsProvider) {
      const settingsLoaded = await ensureRuntimeSettingsLoaded(get, set);
      if (attemptId !== activeReadingAttempt) {
        inFlightReadingRequests.delete(requestKey);
        return;
      }
      if (!settingsLoaded) {
        inFlightReadingRequests.delete(requestKey);
        startBrowserSpeech(null);
        return;
      }
    }

    try {
      const { ttsProvider, backendAudioEnabled } = get();
      const browserOnlyRuntime =
        !preferredProvider && (ttsProvider === "browser" || backendAudioEnabled === false);
      if (browserOnlyRuntime) {
        startBrowserSpeech(null);
        return;
      }

      const textHash = await normalizeTextHash(context.text);
      const readingRequest = api.voice_reading.requestReading({
        context: { ...context, text_hash: textHash },
        voice_id: selectedVoiceId,
        speed: 1,
        auto_play: true,
        preferred_provider: preferredProvider,
      });
      const explicitBrowserProvider = preferredProvider === "browser";
      if (explicitBrowserProvider) {
        startBrowserSpeech(null);
      }
      const response = await readingRequest;
      if (attemptId !== activeReadingAttempt) {
        return;
      }
      if (explicitBrowserProvider) {
        return;
      }
      const shouldPlayAudio = response.playback_mode === "audio" && Boolean(response.audio_url);
      if (response.status === "failed") {
        const { musicDuckState, userChangedMusic } = get();
        restoreMusicAfterReading(userChangedMusic);
        set({
          readingState: "failed",
          currentJobId: response.job_id,
          currentProvider: response.provider,
          currentAudioUrl: "",
          playbackMode: response.playback_mode,
          errorMessage: response.error_code ?? response.message,
          musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
        });
        activeLoadingRequestKey = null;
        activeLoadingStartedAt = 0;
        return;
      }

      if (shouldPlayAudio) {
        if (attemptId !== activeReadingAttempt) {
          return;
        }
        activeLoadingRequestKey = null;
        activeLoadingStartedAt = 0;
        set({
          readingState: "ready",
          currentAudioUrl: response.audio_url ?? "",
          currentJobId: response.job_id,
          currentProvider: response.provider,
          playbackMode: "audio",
          spokenTextLength: 0,
          currentSpeechText: "",
          errorMessage: "",
        });
        return;
      }

      startBrowserSpeech(response.job_id);
    } catch (error) {
      if (attemptId !== activeReadingAttempt) {
        return;
      }
      if (preferredProvider === "browser" && get().playbackMode === "browser_speech") {
        return;
      }
      if ((error as ApiError).status === 401 || getSpeechSynthesis()) {
        startBrowserSpeech(null);
        return;
      }
      const { musicDuckState, userChangedMusic } = get();
      restoreMusicAfterReading(userChangedMusic);
      activeLoadingRequestKey = null;
      activeLoadingStartedAt = 0;
      set({
        readingState: "failed",
        currentAudioUrl: "",
        currentJobId: null,
        currentProvider: "",
        playbackMode: "none",
        errorMessage: error instanceof Error ? error.message : "Reading request failed",
        musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
      });
    } finally {
      inFlightReadingRequests.delete(requestKey);
    }
  },
  pauseReading: () => {
    getSpeechSynthesis()?.pause();
    set({ readingState: "paused" });
  },
  stopReading: () => {
    const { musicDuckState, userChangedMusic } = get();
    restoreMusicAfterReading(userChangedMusic);
    activeReadingAttempt += 1;
    activeLoadingRequestKey = null;
    activeLoadingStartedAt = 0;
    getSpeechSynthesis()?.cancel();
    activeUtterance = null;
    set({
      readingState: "idle",
      currentAudioUrl: "",
      currentJobId: null,
      currentProvider: "",
      playbackMode: "none",
      spokenTextLength: 0,
      currentSpeechText: "",
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  completeReading: () => {
    const {
      currentSpeechText,
      musicDuckState,
      playbackMode,
      readingState,
      spokenTextLength,
      userChangedMusic,
    } = get();
    if (readingState === "failed") {
      return;
    }
    if (!["ready", "playing", "paused"].includes(readingState)) {
      return;
    }
    const completedBrowserSpeech =
      playbackMode === "browser_speech" && currentSpeechText.length > 0;
    restoreMusicAfterReading(userChangedMusic);
    activeReadingAttempt += 1;
    activeLoadingRequestKey = null;
    activeLoadingStartedAt = 0;
    if (activeUtterance) {
      getSpeechSynthesis()?.cancel();
      activeUtterance = null;
    }
    set({
      readingState: "idle",
      playbackMode: completedBrowserSpeech ? "browser_speech" : "none",
      spokenTextLength: completedBrowserSpeech ? spokenTextLength : 0,
      currentSpeechText: completedBrowserSpeech ? currentSpeechText : "",
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  retryReading: () => {
    getSpeechSynthesis()?.resume();
    set({ readingState: "playing" });
  },
  markAudioPlaying: () => {
    const { playbackMode, currentAudioUrl, readingState } = get();
    if (playbackMode !== "audio" || !currentAudioUrl || readingState === "failed") {
      return;
    }
    set({ readingState: "playing", errorMessage: "" });
  },
  markAudioReady: (message) => {
    const { playbackMode, currentAudioUrl, readingState } = get();
    if (playbackMode !== "audio" || !currentAudioUrl || readingState === "failed") {
      return;
    }
    set({
      readingState: "ready",
      errorMessage: message ?? (readingState === "ready" ? get().errorMessage : ""),
    });
  },
  failReading: (error) => {
    const {
      currentProvider,
      currentSpeechText,
      musicDuckState,
      playbackMode,
      spokenTextLength,
      userChangedMusic,
    } = get();
    const canRetryBrowserSpeech =
      playbackMode === "browser_speech" && currentSpeechText.length > 0;
    activeReadingAttempt += 1;
    activeLoadingRequestKey = null;
    activeLoadingStartedAt = 0;
    getSpeechSynthesis()?.cancel();
    activeUtterance = null;
    const errorMessage =
      error instanceof Error
        ? error.message
        : typeof error === "string"
          ? error
          : "Story voice playback failed";
    restoreMusicAfterReading(userChangedMusic);
    set({
      readingState: "failed",
      currentAudioUrl: "",
      currentJobId: null,
      currentProvider: canRetryBrowserSpeech ? currentProvider || "browser" : currentProvider,
      playbackMode: canRetryBrowserSpeech ? "browser_speech" : "none",
      spokenTextLength: canRetryBrowserSpeech ? spokenTextLength : 0,
      currentSpeechText: canRetryBrowserSpeech ? currentSpeechText : "",
      errorMessage,
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  setAutoReadEnabled: (autoReadEnabled) => set({ autoReadEnabled }),
  setSelectedVoiceId: (selectedVoiceId) => set({ selectedVoiceId }),
  setVoiceRuntimeSettings: ({ ttsProvider, backendAudioEnabled }) =>
    set((state) => ({
      ttsProvider: ttsProvider ?? state.ttsProvider,
      backendAudioEnabled: backendAudioEnabled ?? state.backendAudioEnabled,
    })),
  enqueueCompletedAttempt: (text) => set({ queueText: text }),
  simulateMusicPlaying: () => set({ musicWasPlaying: true, musicDuckState: "playing" }),
  userPauseMusicDuringReading: () =>
    set({ userChangedMusic: true, musicWasPlaying: false, musicDuckState: "user_paused" }),
}));
