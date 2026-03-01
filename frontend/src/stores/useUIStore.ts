/**
 * useUIStore — UI 状态：modals, processing flags, streaming text
 */
import { create } from "zustand";

type ModalType =
  | "login"
  | "register"
  | "save-preset"
  | "load-preset"
  | "confirm-delete"
  | "story-adjuster"
  | "game-menu"
  | null;

interface UIState {
  // Modal
  activeModal: ModalType;
  modalData: Record<string, unknown>;

  // Processing states
  isProcessing: boolean;
  processingMessage: string;
  isStreaming: boolean;

  // Language
  language: "zh" | "en";

  // Navigation
  sidebarOpen: boolean;

  // Actions
  openModal: (modal: ModalType, data?: Record<string, unknown>) => void;
  closeModal: () => void;
  setProcessing: (processing: boolean, message?: string) => void;
  setStreaming: (streaming: boolean) => void;
  setLanguage: (lang: "zh" | "en") => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>()((set) => ({
  activeModal: null,
  modalData: {},
  isProcessing: false,
  processingMessage: "",
  isStreaming: false,
  language: "zh",
  sidebarOpen: false,

  openModal: (modal, data = {}) =>
    set({ activeModal: modal, modalData: data }),

  closeModal: () => set({ activeModal: null, modalData: {} }),

  setProcessing: (processing, message = "") =>
    set({ isProcessing: processing, processingMessage: message }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setLanguage: (lang) => set({ language: lang }),

  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
