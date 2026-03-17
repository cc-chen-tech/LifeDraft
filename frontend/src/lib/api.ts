/**
 * API client for the game backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw Object.assign(new Error(error.message || 'Request failed'), { status: response.status });
  }

  return response.json();
}

export const api = {
  // Auth
  auth: {
    register: (data: { display_name: string }) =>
      fetchJson<{ user: { user_id: number; public_id: string; display_name: string; private_id: string }; token: string }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    login: (data: { private_id: string }) =>
      fetchJson<{ user: { user_id: number; public_id: string; display_name: string; private_id: string }; token: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    logout: () =>
      fetchJson<void>('/auth/logout', { method: 'POST' }),
    me: () =>
      fetchJson<{ user_id: number; public_id: string; display_name: string; private_id: string }>('/auth/me'),
  },

  // Games
  games: {
    list: () =>
      fetchJson<Array<{ game_id: number; player_name: string; age: number; week: number; updated_at: string }>>('/games'),
    create: (data: { player_name: string; life_vision?: string; character_settings?: Record<string, unknown> }) =>
      fetchJson<{ game_id: number }>('/games', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    load: (gameId: number) =>
      fetchJson<{
        game_id: number;
        player_state: Record<string, unknown>;
        progress: Record<string, unknown>;
        round_info: Record<string, unknown>;
        current_event: Record<string, unknown> | null;
      }>(`/games/${gameId}`),
    save: (gameId: number) =>
      fetchJson<{ success: boolean }>(`/games/${gameId}/save`, { method: 'POST' }),
    delete: (gameId: number) =>
      fetchJson<{ success: boolean }>(`/games/${gameId}`, { method: 'DELETE' }),
    getActive: () =>
      fetchJson<{
        game_id: number;
        player_state: Record<string, unknown>;
        progress: Record<string, unknown>;
        round_info: Record<string, unknown>;
        current_event: Record<string, unknown> | null;
      }>('/games/active'),
    getEnding: (gameId: number) =>
      fetchJson<{
        ending_name: string;
        summary: string;
        achievements: { list: string[] };
        final_stats: { energy: number; mood: number };
      }>(`/games/${gameId}/ending`),
  },

  // Presets
  presets: {
    list: () =>
      fetchJson<Array<{
        preset_id: number;
        preset_name: string;
        player_name: string;
        life_vision: string;
        created_at: string;
        character_settings: Record<string, unknown>;
      }>>('/presets'),
    create: (data: { player_name: string; life_vision?: string; character_settings?: Record<string, unknown> }) =>
      fetchJson<{ preset_id: number }>('/presets', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    delete: (presetId: number) =>
      fetchJson<{ success: boolean }>(`/presets/${presetId}`, { method: 'DELETE' }),
  },

  // Gameplay
  gameplay: {
    getState: (gameId: number) =>
      fetchJson<{
        player_state: Record<string, unknown>;
        progress: Record<string, unknown>;
        round_info: Record<string, unknown>;
        current_event: Record<string, unknown> | null;
      }>(`/games/${gameId}/state`),
    generateEvent: (gameId: number, data?: { custom_choices?: string[] }) =>
      fetchJson<{
        story: string;
        options: Array<{ text: string; effects?: Record<string, unknown> }>;
      }>(`/games/${gameId}/events`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      }),
    submitChoice: (gameId: number, data: { choice_index: number; custom_choice?: string }) =>
      fetchJson<{
        result: string;
        new_event: Record<string, unknown> | null;
      }>(`/games/${gameId}/choices`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getEnding: (gameId: number) =>
      fetchJson<{
        ending_name: string;
        summary: string;
        achievements: { list: string[] };
        final_stats: { energy: number; mood: number };
      }>(`/games/${gameId}/ending`),
    generateSummary: (gameId: number, data: { weeks?: number }) =>
      fetchJson<{
        summary_text: string;
        start_week: number;
        end_week: number;
      }>(`/games/${gameId}/summary`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    // Synchronous choice methods (non-streaming)
    makeChoiceSync: (gameId: number, data: { option_index: number }) =>
      fetchJson<{
        result: string;
        story: string;
        current_round: number;
        current_week: number;
        player_state: Record<string, unknown>;
        summary?: string;
        need_weekly_summary?: boolean;
        weekly_summary?: string;
        game_over?: boolean;
      }>(`/games/${gameId}/choices/sync`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    makeCustomChoiceSync: (gameId: number, data: { custom_text: string }) =>
      fetchJson<{
        result: string;
        story: string;
        current_round: number;
        current_week: number;
        player_state: Record<string, unknown>;
        summary?: string;
        need_weekly_summary?: boolean;
        weekly_summary?: string;
        game_over?: boolean;
      }>(`/games/${gameId}/choices/custom-sync`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Character
  character: {
    generateSetting: (data: { setting_type: string; character_settings?: Record<string, unknown> }) =>
      fetchJson<{ era: string; era_description: string }>('/character/setting', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateRelationship: (data: { relationship_type: string; character_settings?: Record<string, unknown> }) =>
      fetchJson<{ name: string; relationship: string }>('/character/relationship', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateRelationshipsSummary: (data: { character_settings?: Record<string, unknown> }) =>
      fetchJson<{ relationships_description: string }>('/character/relationships-summary', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Story
  story: {
    chat: (gameId: number, data: { message: string }) =>
      fetchJson<{ reply: string }>(`/games/${gameId}/chat`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    rewrite: (gameId: number, data: { story_text: string; adjustment: string }) =>
      fetchJson<{ data: { new_story: string } }>(`/games/${gameId}/rewrite`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    regenerate: (gameId: number, data: { story_context?: string; adjustment?: string }) =>
      fetchJson<{
        data: {
          new_story: string;
          event: {
            event_description: string;
            options: Array<{ text: string }>;
          };
        };
      }>(`/games/${gameId}/regenerate`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Friends
  friends: {
    list: () =>
      fetchJson<Array<{ user_id: number; display_name: string; public_id: string }>>('/friends'),
    pendingRequests: () =>
      fetchJson<Array<{
        request_id: number;
        from_user: { user_id: number; public_id: string; display_name: string };
        created_at: string;
      }>>('/friends/requests'),
    sendRequest: (data: { to_public_id: string }) =>
      fetchJson<{ success: boolean }>('/friends/requests', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    respond: (data: { request_id: number; accept: boolean }) =>
      fetchJson<{ success: boolean }>(`/friends/requests/${data.request_id}`, {
        method: 'PUT',
        body: JSON.stringify({ accept: data.accept }),
      }),
    remove: (userId: number) =>
      fetchJson<{ success: boolean }>(`/friends/${userId}`, { method: 'DELETE' }),
  },

  // Images
  images: {
    listByGame: (gameId: number, imageType?: string) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string; image_type: string }>; total: number }>(
        `/games/${gameId}/images${imageType ? `?type=${imageType}` : ''}`
      ),
    generate: (data: { game_id: number; image_type: string; prompt?: string }) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>('/images', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    regenerate: (imageId: number, data?: { prompt?: string }) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>(`/images/${imageId}/regenerate`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      }),
    regenerateFresh: (imageId: number, data?: { prompt?: string }) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>(`/images/${imageId}/regenerate-fresh`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      }),
    get: (imageId: number) =>
      fetchJson<{ image_id: number; image_url: string; image_type: string }>(`/images/${imageId}`),
    generatePlayerImage: (data: {
      game_id: number;
      character_settings: Record<string, unknown>;
      player_name: string;
      life_vision?: string;
    }) =>
      fetchJson<{ image_id: number; image_url: string; image_type: string }>('/images/player', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateOpeningIllustration: (data: {
      game_id: number;
      character_settings: Record<string, unknown>;
      player_name: string;
      opening_story: string;
    }) =>
      fetchJson<{ image_id: number; image_url: string; image_type: string; scene_description: string }>('/images/opening', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getRoundSceneImage: (gameId: number, roundNumber: number, week?: number) =>
      fetchJson<{
        scene_id: number;
        week: number;
        round_number: number;
        stage: string;
        image_url: string;
        scene_description: string;
        referenced_images?: number[];
        created_at: string;
      }>(`/games/${gameId}/round-scenes/${roundNumber}${week !== undefined ? `?week=${week}` : ''}`),
    getRoundSceneImageByStage: (gameId: number, roundNumber: number, stage: string, week?: number) =>
      fetchJson<{
        scene_id: number;
        week: number;
        round_number: number;
        stage: string;
        image_url: string;
        scene_description: string;
        referenced_images?: number[];
        created_at: string;
      }>(`/games/${gameId}/round-scenes/${roundNumber}/${stage}${week !== undefined ? `?week=${week}` : ''}`),
    getAllRoundSceneImages: (gameId: number) =>
      fetchJson<{
        scenes: Array<{
          scene_id: number;
          week: number;
          round_number: number;
          stage: string;
          image_url: string;
          scene_description: string;
          referenced_images?: number[];
          created_at: string;
        }>;
      }>(`/games/${gameId}/round-scenes`),
    generateRoundSceneImage: (data: {
      game_id: number;
      round_number: number;
      story_text: string;
      character_settings: Record<string, unknown>;
      player_name: string;
      player_image_id?: number;
      stage?: string;
      week?: number;
    }) =>
      fetchJson<{
        scene_id: number;
        week: number;
        round_number: number;
        stage: string;
        image_url: string;
        scene_description: string;
        created_at: string;
      }>('/images/round-scene', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    regenerateRoundSceneImage: (data: {
      game_id: number;
      round_number: number;
      story_text: string;
      character_settings: Record<string, unknown>;
      player_name: string;
      user_prompt: string;
      current_scene_id: number;
      player_image_id?: number;
    }) =>
      fetchJson<{
        scene_id: number;
        week: number;
        round_number: number;
        stage: string;
        image_url: string;
        scene_description: string;
        created_at: string;
      }>('/images/round-scene/regenerate', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Collection
  collection: {
    getStatus: (gameId: number) =>
      fetchJson<{
        characters: Array<{
          character_id: number;
          character_name: string;
          character_type: string;
          relationship: string;
          first_meet_week: number;
          first_meet_round: number;
          image_url?: string;
          is_collected: boolean;
        }>;
        total: number;
        collected: number;
      }>(`/games/${gameId}/collection`),
    updateCharacterImage: (characterId: number, data: { image_url: string }) =>
      fetchJson<{ success: boolean }>(`/collection/characters/${characterId}/image`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    getCharacterDetail: (characterId: number) =>
      fetchJson<{
        character_id: number;
        character_name: string;
        character_type: string;
        relationship: string;
        first_meet_week: number;
        first_meet_round: number;
        image_url?: string;
        is_collected: boolean;
        events: Array<{
          event_id: number;
          week: number;
          round: number;
          description: string;
        }>;
      }>(`/collection/characters/${characterId}`),
  },
};

export default api;

// Named exports for convenience
export const { gameplay } = api;
