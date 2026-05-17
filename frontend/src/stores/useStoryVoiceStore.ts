"use client";

import { create } from "zustand";
import { api } from "@/lib/api";
import type { ReadingContext } from "@/lib/types";

export type VoiceReadingState = "idle" | "loading" | "ready" | "playing" | "paused" | "failed";
export type MusicDuckState = "idle" | "playing" | "ducked" | "restored" | "user_paused";

interface StoryVoiceState {
  readingState: VoiceReadingState;
  currentSource: string;
  currentContextLabel: string;
  currentAudioUrl: string;
  currentJobId: number | null;
  errorMessage: string;
  queueText: string;
  autoReadEnabled: boolean;
  musicDuckState: MusicDuckState;
  musicWasPlaying: boolean;
  userChangedMusic: boolean;
  startReading: (context: ReadingContext) => Promise<void>;
  pauseReading: () => void;
  stopReading: () => void;
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

async function normalizeTextHash(text: string): Promise<string> {
  const normalized = text.split(/\s+/).filter(Boolean).join(" ");
  const bytes = new TextEncoder().encode(normalized);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export const useStoryVoiceStore = create<StoryVoiceState>((set, get) => ({
  readingState: "idle",
  currentSource: "",
  currentContextLabel: "",
  currentAudioUrl: "",
  currentJobId: null,
  errorMessage: "",
  queueText: "",
  autoReadEnabled: false,
  musicDuckState: "idle",
  musicWasPlaying: false,
  userChangedMusic: false,

  startReading: async (context) => {
    const { musicWasPlaying } = get();
    set({
      readingState: "playing",
      currentSource: context.source_type,
      currentContextLabel: contextLabel(context),
      currentAudioUrl: "",
      currentJobId: null,
      errorMessage: "",
      musicDuckState: musicWasPlaying ? "ducked" : get().musicDuckState,
      userChangedMusic: false,
    });
    try {
      const textHash = await normalizeTextHash(context.text);
      const response = await api.voice_reading.requestReading({
        context: { ...context, text_hash: textHash },
        voice_id: "warm_female",
        speed: 1,
        auto_play: true,
      });
      set({
        readingState: response.status === "failed" ? "failed" : "playing",
        currentAudioUrl: response.audio_url ?? "",
        currentJobId: response.job_id,
        errorMessage: response.error_code ?? "",
      });
    } catch (error) {
      set({
        readingState: "failed",
        errorMessage: error instanceof Error ? error.message : "Reading request failed",
      });
    }
  },
  pauseReading: () => set({ readingState: "paused" }),
  stopReading: () => {
    const { musicDuckState, userChangedMusic } = get();
    set({
      readingState: "idle",
      currentAudioUrl: "",
      currentJobId: null,
      musicDuckState:
        musicDuckState === "ducked" && !userChangedMusic ? "restored" : musicDuckState,
    });
  },
  retryReading: () => set({ readingState: "playing" }),
  failReading: () => set({ readingState: "failed" }),
  setAutoReadEnabled: (autoReadEnabled) => set({ autoReadEnabled }),
  enqueueCompletedAttempt: (text) => set({ queueText: text }),
  simulateMusicPlaying: () => set({ musicWasPlaying: true, musicDuckState: "playing" }),
  userPauseMusicDuringReading: () =>
    set({ userChangedMusic: true, musicWasPlaying: false, musicDuckState: "user_paused" }),
}));
