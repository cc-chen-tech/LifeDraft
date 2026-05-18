"use client";

import { create } from "zustand";
import type { ReadingContext } from "@/lib/types";

export type VoiceReadingState = "idle" | "loading" | "ready" | "playing" | "paused" | "failed";
export type MusicDuckState = "idle" | "playing" | "ducked" | "restored" | "user_paused";
export type VoicePlaybackMode = "none" | "browser_speech" | "audio_asset";

interface StoryVoiceState {
  readingState: VoiceReadingState;
  currentSource: string;
  currentContextLabel: string;
  currentAudioUrl: string;
  currentJobId: number | null;
  playbackMode: VoicePlaybackMode;
  spokenTextLength: number;
  errorMessage: string;
  queueText: string;
  autoReadEnabled: boolean;
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
  enqueueCompletedAttempt: (text: string) => void;
  simulateMusicPlaying: () => void;
  userPauseMusicDuringReading: () => void;
}

function contextLabel(context: ReadingContext): string {
  const parts = [];
  if (context.week !== undefined && context.week !== null) parts.push(`week=${context.week}`);
  if (context.round_number !== undefined && context.round_number !== null) {
    parts.push(`round=${context.round_number}`);
  }
  if (context.stage) parts.push(`stage=${context.stage}`);
  return parts.join(" ");
}

let activeUtterance: SpeechSynthesisUtterance | null = null;

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
  playbackMode: "none",
  spokenTextLength: 0,
  errorMessage: "",
  queueText: "",
  autoReadEnabled: false,
  musicDuckState: "idle",
  musicWasPlaying: false,
  userChangedMusic: false,

  startReading: async (context) => {
    const { musicWasPlaying } = get();
    const speech = getSpeechSynthesis();
    if (!speech) {
      set({
        readingState: "failed",
        currentSource: context.source_type,
        currentContextLabel: contextLabel(context),
        currentAudioUrl: "",
        currentJobId: null,
        playbackMode: "none",
        spokenTextLength: context.text.length,
        errorMessage: "Browser speech synthesis is unavailable",
      });
      return;
    }

    speech.cancel();
    const utterance = new SpeechSynthesisUtterance(context.text);
    activeUtterance = utterance;
    utterance.lang = detectSpeechLanguage(context.text);
    utterance.rate = 1;
    utterance.onend = () => {
      if (activeUtterance === utterance) {
        activeUtterance = null;
        get().completeReading();
      }
    };
    utterance.onerror = () => {
      if (activeUtterance === utterance) {
        const { musicDuckState, userChangedMusic } = get();
        activeUtterance = null;
        set({
          readingState: "failed",
          errorMessage: "Browser speech synthesis failed",
          playbackMode: "browser_speech",
          musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
        });
      }
    };

    set({
      readingState: "playing",
      currentSource: context.source_type,
      currentContextLabel: contextLabel(context),
      currentAudioUrl: "",
      currentJobId: null,
      playbackMode: "browser_speech",
      spokenTextLength: context.text.length,
      errorMessage: "",
      musicDuckState: musicWasPlaying ? "ducked" : get().musicDuckState,
      userChangedMusic: false,
    });
    speech.speak(utterance);
  },
  pauseReading: () => {
    getSpeechSynthesis()?.pause();
    set({ readingState: "paused" });
  },
  stopReading: () => {
    const { musicDuckState, userChangedMusic } = get();
    getSpeechSynthesis()?.cancel();
    activeUtterance = null;
    set({
      readingState: "idle",
      currentAudioUrl: "",
      currentJobId: null,
      playbackMode: "none",
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  completeReading: () => {
    const { musicDuckState, userChangedMusic } = get();
    if (activeUtterance) {
      getSpeechSynthesis()?.cancel();
      activeUtterance = null;
    }
    set({
      readingState: "idle",
      playbackMode: "none",
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  retryReading: () => {
    getSpeechSynthesis()?.resume();
    set({ readingState: "playing" });
  },
  failReading: () => {
    const { musicDuckState, userChangedMusic } = get();
    getSpeechSynthesis()?.cancel();
    activeUtterance = null;
    set({
      readingState: "failed",
      musicDuckState: restoredMusicDuckState(musicDuckState, userChangedMusic),
    });
  },
  setAutoReadEnabled: (autoReadEnabled) => set({ autoReadEnabled }),
  enqueueCompletedAttempt: (text) => set({ queueText: text }),
  simulateMusicPlaying: () => set({ musicWasPlaying: true, musicDuckState: "playing" }),
  userPauseMusicDuringReading: () =>
    set({ userChangedMusic: true, musicWasPlaying: false, musicDuckState: "user_paused" }),
}));
