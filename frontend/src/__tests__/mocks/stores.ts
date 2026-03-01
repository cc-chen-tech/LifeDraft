/**
 * Mock stores for testing
 */
import { create } from 'zustand';

// Mock user store state
export const mockUserStoreState = {
  user: null as { user_id: number; display_name: string; public_id: string; private_id?: string } | null,
  token: null as string | null,
  isAuthenticated: false,
  friends: [] as { user_id: number; display_name: string; public_id: string }[],
  pendingRequests: [] as { request_id: number; from_user: { display_name: string; public_id: string } }[],
  register: jest.fn(),
  login: jest.fn(),
  logout: jest.fn(),
  fetchMe: jest.fn(),
  fetchFriends: jest.fn(),
  fetchPendingRequests: jest.fn(),
  sendFriendRequest: jest.fn(),
  respondToRequest: jest.fn(),
  removeFriend: jest.fn(),
  setUser: jest.fn(),
};

// Mock game store state
export const mockGameStoreState = {
  gameId: null as number | null,
  sessionId: null as string | null,
  playerState: null as Record<string, unknown> | null,
  progress: null as Record<string, unknown> | null,
  roundInfo: null as Record<string, unknown> | null,
  currentEvent: null as { story: string; options: { text: string }[] } | null,
  storyText: '',
  isGameOver: false,
  savedGames: [] as { game_id: number; player_name: string; age: number; week: number; updated_at: string }[],
  presets: [] as { preset_id: number; preset_name: string; player_name: string; life_vision?: string; character_settings: Record<string, unknown>; created_at?: string }[],
  creationStep: 0,
  characterSettings: {} as Record<string, unknown>,
  playerName: '',
  lifeVision: '',
  openingStory: '',
  isPresetLoaded: false,
  lastSummary: null as Record<string, unknown> | null,
  setGameSession: jest.fn(),
  loadGameState: jest.fn(),
  syncState: jest.fn(),
  saveGame: jest.fn(),
  resetGame: jest.fn(),
  setCurrentEvent: jest.fn(),
  appendStoryText: jest.fn(),
  setStoryText: jest.fn(),
  clearCurrentEvent: jest.fn(),
  setGameOver: jest.fn(),
  generateSummary: jest.fn(),
  clearSummary: jest.fn(),
  fetchSavedGames: jest.fn().mockResolvedValue(undefined),
  fetchPresets: jest.fn().mockResolvedValue(undefined),
  deleteGame: jest.fn(),
  deletePreset: jest.fn(),
  setCreationStep: jest.fn(),
  nextCreationStep: jest.fn(),
  prevCreationStep: jest.fn(),
  updateCharacterSetting: jest.fn(),
  setPlayerName: jest.fn(),
  setLifeVision: jest.fn(),
  setOpeningStory: jest.fn(),
  resetCreation: jest.fn(),
  loadPreset: jest.fn(),
};

// Mock UI store state
export const mockUIStoreState = {
  language: 'zh',
  setLanguage: jest.fn(),
};

// Helper to create authenticated user state
export const createAuthenticatedUserState = (overrides = {}) => ({
  ...mockUserStoreState,
  isAuthenticated: true,
  user: {
    user_id: 1,
    display_name: 'Test User',
    public_id: 'pub-123',
  },
  token: 'test-token',
  ...overrides,
});

// Helper to create game in progress state
export const createGameInProgressState = (overrides = {}) => ({
  ...mockGameStoreState,
  gameId: 1,
  sessionId: 'session-1',
  playerState: {
    player_name: 'Test Player',
    energy: 100,
    mood: 80,
  },
  progress: { week: 5 },
  roundInfo: { current_round: 1, rounds_per_week: 3 },
  ...overrides,
});

// Reset all store mocks
export const resetStoreMocks = () => {
  Object.keys(mockUserStoreState).forEach((key) => {
    const value = mockUserStoreState[key as keyof typeof mockUserStoreState];
    if (typeof value === 'function' && 'mockClear' in value) {
      (value as jest.Mock).mockClear();
    }
  });
  Object.keys(mockGameStoreState).forEach((key) => {
    const value = mockGameStoreState[key as keyof typeof mockGameStoreState];
    if (typeof value === 'function' && 'mockClear' in value) {
      (value as jest.Mock).mockClear();
    }
  });
  Object.keys(mockUIStoreState).forEach((key) => {
    const value = mockUIStoreState[key as keyof typeof mockUIStoreState];
    if (typeof value === 'function' && 'mockClear' in value) {
      (value as jest.Mock).mockClear();
    }
  });
};
