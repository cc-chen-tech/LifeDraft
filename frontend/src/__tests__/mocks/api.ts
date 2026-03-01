/**
 * Mock API module for testing
 */

export const mockApi = {
  auth: {
    register: jest.fn().mockResolvedValue({
      user: {
        user_id: 1,
        display_name: 'Test User',
        public_id: 'pub-123',
        private_id: 'priv-456-789-012',
      },
      token: 'test-token-123',
    }),
    login: jest.fn().mockResolvedValue({
      user: {
        user_id: 1,
        display_name: 'Test User',
        public_id: 'pub-123',
      },
      token: 'test-token-123',
    }),
    logout: jest.fn(),
    me: jest.fn().mockResolvedValue({
      user_id: 1,
      display_name: 'Test User',
      public_id: 'pub-123',
    }),
  },
  games: {
    list: jest.fn().mockResolvedValue([
      {
        game_id: 1,
        player_name: 'Test Player',
        age: 20,
        week: 5,
        updated_at: new Date().toISOString(),
      },
    ]),
    create: jest.fn().mockResolvedValue({ game_id: 1 }),
    load: jest.fn().mockResolvedValue({
      game_id: 1,
      player_state: { player_name: 'Test Player' },
      progress: { week: 1 },
      round_info: { current_round: 1, rounds_per_week: 3 },
      current_event: null,
    }),
    save: jest.fn().mockResolvedValue({ success: true }),
    delete: jest.fn().mockResolvedValue({ success: true }),
  },
  presets: {
    list: jest.fn().mockResolvedValue([
      {
        preset_id: 1,
        preset_name: 'Test Preset',
        player_name: 'Test Player',
        life_vision: 'Test vision',
        created_at: new Date().toISOString(),
        character_settings: {},
      },
    ]),
    create: jest.fn().mockResolvedValue({ preset_id: 1 }),
    delete: jest.fn().mockResolvedValue({ success: true }),
  },
  gameplay: {
    getState: jest.fn().mockResolvedValue({
      player_state: { player_name: 'Test Player' },
      progress: { week: 1 },
      round_info: { current_round: 1, rounds_per_week: 3 },
      current_event: null,
    }),
    generateEvent: jest.fn().mockResolvedValue({
      story: 'Test story',
      options: [{ text: 'Option 1' }, { text: 'Option 2' }],
    }),
    submitChoice: jest.fn().mockResolvedValue({
      result: 'Test result',
      new_event: null,
    }),
    getEnding: jest.fn().mockResolvedValue({
      ending_name: 'Test Ending',
      summary: 'Test summary',
      achievements: { list: ['Achievement 1'] },
      final_stats: { energy: 80, mood: 70 },
    }),
    generateSummary: jest.fn().mockResolvedValue({
      summary_text: 'Test summary',
      start_week: 1,
      end_week: 4,
    }),
  },
  character: {
    generateSetting: jest.fn().mockResolvedValue({
      era: 'modern',
      era_description: 'Modern era',
    }),
    generateRelationship: jest.fn().mockResolvedValue({
      name: 'Test Person',
      relationship: 'friend',
    }),
    generateRelationshipsSummary: jest.fn().mockResolvedValue({
      relationships_description: 'Test relationships',
    }),
  },
  story: {
    chat: jest.fn().mockResolvedValue({ reply: 'Test reply' }),
    rewrite: jest.fn().mockResolvedValue({ data: { new_story: 'New story' } }),
    regenerate: jest.fn().mockResolvedValue({
      data: {
        new_story: 'Regenerated story',
        event: {
          event_description: 'Regenerated story',
          options: [{ text: 'Option 1' }, { text: 'Option 2' }],
        },
      },
    }),
  },
  friends: {
    list: jest.fn().mockResolvedValue([
      {
        user_id: 2,
        display_name: 'Friend User',
        public_id: 'friend-123',
      },
    ]),
    pendingRequests: jest.fn().mockResolvedValue([]),
    sendRequest: jest.fn().mockResolvedValue({ success: true }),
    respond: jest.fn().mockResolvedValue({ success: true }),
    remove: jest.fn().mockResolvedValue({ success: true }),
  },
};

export default mockApi;

// Reset all mocks helper
export const resetApiMocks = () => {
  Object.values(mockApi).forEach((module) => {
    Object.values(module).forEach((fn) => {
      if (typeof fn === 'function' && 'mockClear' in fn) {
        (fn as jest.Mock).mockClear();
      }
    });
  });
};
