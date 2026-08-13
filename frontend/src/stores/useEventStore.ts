/**
 * useEventStore — 事件和故事状态
 * 
 * 管理游戏事件、故事文本和总结相关状态
 */
import { create } from "zustand";
import type { GameEvent, EventOption } from "@/lib/types";
import api from "@/lib/api";

interface EventState {
  // Current event
  currentEvent: GameEvent | null;
  storyText: string; // Accumulated streaming text
  lastSummary: Record<string, unknown> | null; // 年度总结数据

  // Actions
  setCurrentEvent: (event: GameEvent | null) => void;
  appendStoryText: (text: string) => void;
  setStoryText: (text: string) => void;
  clearCurrentEvent: () => void;
  
  // Summary
  generateSummary: (gameId: number, weeks?: number) => Promise<void>;
  clearSummary: () => void;
}

export const useEventStore = create<EventState>((set, get) => ({
  currentEvent: null,
  storyText: "",
  lastSummary: null,

  setCurrentEvent: (event) => {
    if (event === null) {
      set({ currentEvent: null });
      return;
    }
    
    // 优先保留前端流式累积的 storyText
    const currentStory = get().storyText;
    const newStory = currentStory || event.story || "";
    const newEvent: GameEvent = { 
      ...event,
      story: newStory, 
      options: event.options || [] 
    };
    
    // 只在值变化时才更新
    const currentEvent = get().currentEvent;
    if (JSON.stringify(newEvent) !== JSON.stringify(currentEvent) || newStory !== currentStory) {
      set({ currentEvent: newEvent, storyText: newStory });
    }
  },

  appendStoryText: (text) => {
    const prev = get().storyText;
    const next = prev + text;
    console.log(`[STORY] append +${text.length} chars (total: ${prev.length} → ${next.length})`);
    set({ storyText: next });
  },

  setStoryText: (text) => {
    const prev = get().storyText;
    if (text !== prev) {
      const action = text.length === 0 ? 'CLEAR' : (text.length < prev.length ? 'TRUNCATE' : 'SET');
      console.log(`[STORY] ${action}: ${prev.length} → ${text.length} chars`);
      set({ storyText: text });
    }
  },

  clearCurrentEvent: () => set({ currentEvent: null, storyText: "" }),

  generateSummary: async (gameId: number, weeks = 52) => {
    try {
      const result = await api.gameplay.generateSummary(gameId, { weeks });
      set({ lastSummary: result as unknown as Record<string, unknown> });
    } catch (err) {
      console.error("[generateSummary] Failed:", err);
      throw err;
    }
  },

  clearSummary: () => set({ lastSummary: null }),
}));
