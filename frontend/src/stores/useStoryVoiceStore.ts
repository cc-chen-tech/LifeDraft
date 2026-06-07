"use client";

import { create } from "zustand";
import { api } from "@/lib/api";
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
  musicDuckState: MusicDuckState;
  musicWasPlaying: boolean;
  userChangedMusic: boolean;
  startReading: (context: ReadingContext) => Promise<void>;
  pauseReading: () => void;
  stopReading: () => void;
  completeReading: () => void;
  retryReading: () => void;
  failReading: () => void;
  setAutoReadEnabled: (enabled: boolean) => void;
  setSelectedVoiceId: (voiceId: string) => void;
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

async function normalizeTextHash(text: string): Promise<string> {
  const normalized = text.split(/\s+/).filter(Boolean).join(" ");
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalized));
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

let activeUtterance: SpeechSynthesisUtterance | null = null;
let activeReadingAttempt = 0;

function getSpeechSynthesis(): SpeechSynthesis | null {
  if (typeof window === "undefined") return null;
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) return null;
  return window.speechSynthesis;
}

function detectSpeechLanguage(text: string): string {
  return /[\u3400-\u9fff]/.test(text) ? "zh-CN" : "en-US";
}

function restoredMusicDuckState(
  musicDuckState: MusicDuckState,
  userChangedMusic: boolean
): MusicDuckState {
  return musicDuckState === "ducked" && !userChangedMusic ? "restored" : musicDuckState;
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
  musicDuckState: "idle",
  musicWasPlaying: false,
  userChangedMusic: false,

  startReading: async (context) => {
    const attemptId = activeReadingAttempt + 1;
    activeReadingAttempt = attemptId;
    const { musicWasPlaying } = get();
    getSpeechSynthesis()?.cancel();
    activeUtterance = null;
    set({
      readingState: "loading",
      currentSource: context.source_type,
      currentContextLabel: contextLabel(context),
      currentAudioUrl: "",
      currentJobId: null,
      currentProvider: "",
      currentSpeechText: "",
      playbackMode: "none",
      spokenTextLength: 0,
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
        return;
      }

      const utterance = new SpeechSynthesisUtterance(context.text);
      activeUtterance = utterance;
      utterance.lang = detectSpeechLanguage(context.text);
      utterance.rate = 1;
      utterance.onend = () => {
        if (activeUtterance === utterance && attemptId === activeReadingAttempt) {
          activeUtterance = null;
          get().completeReading();
        }
      };
      utterance.onerror = () => {
        if (activeUtterance === utterance && attemptId === activeReadingAttempt) {
          const { musicDuckState, userChangedMusic } = get();
          activeUtterance = null;
          set({
            readingState: "failed",
            currentAudioUrl: "",
            errorMessage: "Browser speech synthesis failed",
            playbackMode: "browser_speech",
            musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
          });
        }
      };
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
      speech.cancel();
      speech.speak(utterance);
    };

    try {
      const textHash = await normalizeTextHash(context.text);
      const response = await api.voice_reading.requestReading({
        context: { ...context, text_hash: textHash },
        voice_id: get().selectedVoiceId,
        speed: 1,
        auto_play: true,
        preferred_provider:
          typeof window !== "undefined"
            ? window.localStorage.getItem("story_voice_e2e_provider")
            : null,
      });
      if (attemptId !== activeReadingAttempt) {
        return;
      }
      const shouldPlayAudio = response.playback_mode === "audio" && Boolean(response.audio_url);
      if (response.status === "failed") {
        const { musicDuckState, userChangedMusic } = get();
        set({
          readingState: "failed",
          currentJobId: response.job_id,
          currentProvider: response.provider,
          currentAudioUrl: "",
          playbackMode: response.playback_mode,
          errorMessage: response.error_code ?? response.message,
          musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
        });
        return;
      }

      if (shouldPlayAudio) {
        if (attemptId !== activeReadingAttempt) {
          return;
        }
        set({
          readingState: "playing",
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
      if ((error as ApiError).status === 401) {
        startBrowserSpeech(null);
        return;
      }
      const { musicDuckState, userChangedMusic } = get();
      set({
        readingState: "failed",
        currentAudioUrl: "",
        currentJobId: null,
        currentProvider: "",
        playbackMode: "none",
        errorMessage: error instanceof Error ? error.message : "Reading request failed",
        musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
      });
    }
  },
  pauseReading: () => {
    getSpeechSynthesis()?.pause();
    set({ readingState: "paused" });
  },
  stopReading: () => {
    const { musicDuckState, userChangedMusic } = get();
    activeReadingAttempt += 1;
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
    const { musicDuckState, readingState, userChangedMusic } = get();
    if (readingState === "failed") {
      return;
    }
    activeReadingAttempt += 1;
    if (activeUtterance) {
      getSpeechSynthesis()?.cancel();
      activeUtterance = null;
    }
    set({
      readingState: "idle",
      playbackMode: "none",
      spokenTextLength: 0,
      currentSpeechText: "",
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  retryReading: () => {
    getSpeechSynthesis()?.resume();
    set({ readingState: "playing" });
  },
  failReading: () => {
    const { musicDuckState, userChangedMusic } = get();
    activeReadingAttempt += 1;
    getSpeechSynthesis()?.cancel();
    activeUtterance = null;
    set({
      readingState: "failed",
      currentAudioUrl: "",
      currentJobId: null,
      playbackMode: "none",
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  setAutoReadEnabled: (autoReadEnabled) => set({ autoReadEnabled }),
  setSelectedVoiceId: (selectedVoiceId) => set({ selectedVoiceId }),
  enqueueCompletedAttempt: (text) => set({ queueText: text }),
  simulateMusicPlaying: () => set({ musicWasPlaying: true, musicDuckState: "playing" }),
  userPauseMusicDuringReading: () =>
    set({ userChangedMusic: true, musicWasPlaying: false, musicDuckState: "user_paused" }),
}));
