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
    create: (data: { player_name: string; life_vision?: string; character_settings?: Record<string, unknown>; language?: string }) =>
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
    create: (data: { preset_name: string; player_name: string; life_vision?: string; character_settings?: Record<string, unknown> }) =>
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
    generateSetting: (data: {
      setting_type: string;
      player_name?: string;
      life_vision?: string;
      previous_settings?: Record<string, unknown>;
      feedback?: string | null;
      language?: string;
      character_settings?: Record<string, unknown>
    }) =>
      fetchJson<{ era: string; era_description: string }>('/character/setting', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateRelationship: (data: {
      relationship_type?: string;
      player_name?: string;
      life_vision?: string;
      previous_settings?: Record<string, unknown>;
      existing_people?: Array<Record<string, unknown>>;
      person_index?: number;
      total_needed?: number;
      feedback?: string | null;
      language?: string;
      character_settings?: Record<string, unknown>
    }) =>
      fetchJson<{ name: string; relationship: string }>('/character/relationship', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateRelationshipsSummary: (data: {
      character_settings?: Record<string, unknown>;
      player_name?: string;
      life_vision?: string;
      previous_settings?: Record<string, unknown>;
      key_people?: Array<Record<string, unknown>>;
      language?: string;
    }) =>
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
      fetchJson<{ images: Array<{ image_id: number; image_url: string; image_type: string; entity_key?: string; entity_name?: string }>; total: number }>(
        `/images/game/${gameId}${imageType ? `?image_type=${imageType}` : ''}`
      ),
    generate: (data: {
      game_id: number;
      image_type: string;
      prompt?: string;
      entity_name?: string;
      description?: string;
      entity_key?: string;
      era?: string;
      extra_context?: Record<string, unknown>;
      feedback?: string;
    }) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>('/images', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    regenerate: (imageId: number, data?: { prompt?: string; feedback?: string }) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>(`/images/regenerate`, {
        method: 'POST',
        body: JSON.stringify({ image_id: imageId, ...data }),
      }),
    regenerateFresh: (imageId: number, data?: { prompt?: string }) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>(`/images/regenerate-fresh`, {
        method: 'POST',
        body: JSON.stringify({ image_id: imageId, ...data }),
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
      opening_story?: string;
      story_text?: string;
      player_image_id?: number;
    }) =>
      fetchJson<{ image_id: number; image_url: string; image_type: string; scene_description: string }>('/images/opening', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    regenerateOpeningIllustration: (data: {
      game_id: number;
      current_scene_id?: number;
      current_illustration_id?: number;
      story_text: string;
      character_settings: Record<string, unknown>;
      player_name: string;
      user_prompt: string;
      player_image_id?: number;
    }) =>
      fetchJson<{ image_id: number; image_url: string; image_type: string; scene_description: string }>('/images/opening/regenerate', {
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
      }>(`/images/scene/${gameId}/${roundNumber}${week !== undefined ? `?week=${week}` : ''}`),
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
      }>(`/images/scene/${gameId}/${roundNumber}?stage=${encodeURIComponent(stage)}${week !== undefined ? `&week=${week}` : ''}`),
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
      }>(`/images/scenes/${gameId}`),
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
      }>('/images/scene/generate', {
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
      }>('/images/scene/regenerate', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Collection
  collection: {
    get: (gameId: number) =>
      fetchJson<{
        characters: Array<{
          name: string;
          role: string;
          description: string;
          affinity: number;
          age: number | null;
          gender: string | null;
          occupation: string | null;
          personality_traits: string[];
          image_url: string | null;
          image_generated: boolean;
          description_generated: boolean;
        }>;
        items: Array<{
          name: string;
          description: string;
          importance: "critical" | "important" | "normal";
          category: "weapon" | "tool" | "keepsake" | "treasure" | "document" | "other";
          acquired_week: number;
          acquired_context: string;
          is_key_item: boolean;
          image_url: string | null;
          image_generated: boolean;
          description_generated: boolean;
          metadata: Record<string, unknown>;
        }>;
        landmarks: Array<{
          name: string;
          description: string;
          category: "building" | "nature" | "room" | "area" | "other";
          importance: "critical" | "important" | "normal";
          first_appear_week: number;
          appear_count: number;
          last_appear_week: number;
          context: string;
          is_key_location: boolean;
          image_url: string | null;
          image_generated: boolean;
          metadata: Record<string, unknown>;
        }>;
      }>(`/games/${gameId}/collection/details`),
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
    // Character image generation
    generateCharacterImage: (gameId: number, name: string) =>
      fetchJson<{ image_url: string; success: boolean }>(`/games/${gameId}/collection/characters/${encodeURIComponent(name)}/generate-image`, {
        method: 'POST',
      }),
    regenerateCharacterImage: (gameId: number, name: string, feedback?: string, imageId?: number) =>
      fetchJson<{ image_url: string; success: boolean }>(`/games/${gameId}/collection/characters/${encodeURIComponent(name)}/regenerate-image`, {
        method: 'POST',
        body: JSON.stringify({ feedback, image_id: imageId }),
      }),
    // Character description generation
    generateCharacterDescription: (gameId: number, name: string) =>
      fetchJson<{ description: string; success: boolean }>(`/games/${gameId}/collection/characters/${encodeURIComponent(name)}/generate-description`, {
        method: 'POST',
      }),
    // Item image generation
    generateItemImage: (gameId: number, itemName: string) =>
      fetchJson<{ image_url: string; success: boolean }>(`/games/${gameId}/collection/items/${encodeURIComponent(itemName)}/generate-image`, {
        method: 'POST',
      }),
    regenerateItemImage: (gameId: number, itemName: string, feedback?: string) =>
      fetchJson<{ image_url: string; success: boolean }>(`/games/${gameId}/collection/items/${encodeURIComponent(itemName)}/regenerate-image`, {
        method: 'POST',
        body: JSON.stringify({ feedback }),
      }),
    // Item description generation
    generateItemDescription: (gameId: number, itemName: string) =>
      fetchJson<{ description: string; success: boolean }>(`/games/${gameId}/collection/items/${encodeURIComponent(itemName)}/generate-description`, {
        method: 'POST',
      }),
    // Landmark image generation
    generateLandmarkImage: (gameId: number, landmarkName: string) =>
      fetchJson<{ image_url: string; success: boolean }>(`/games/${gameId}/collection/landmarks/${encodeURIComponent(landmarkName)}/generate-image`, {
        method: 'POST',
      }),
    // Landmark description generation
    generateLandmarkDescription: (gameId: number, landmarkName: string) =>
      fetchJson<{ description: string; success: boolean }>(`/games/${gameId}/collection/landmarks/${encodeURIComponent(landmarkName)}/generate-description`, {
        method: 'POST',
      }),
    // Entity recognition
    recognizeEntities: (gameId: number, data: { entity_types?: string[]; min_appearances?: number }) =>
      fetchJson<{
        items: Array<{
          name: string;
          description: string;
          category: string;
          importance: "critical" | "important" | "normal";
          appear_count: number;
          appear_contexts: string[];
        }>;
        characters: Array<{
          name: string;
          description: string;
          category: string;
          importance: "critical" | "important" | "normal";
          appear_count: number;
          appear_contexts: string[];
        }>;
        landmarks: Array<{
          name: string;
          description: string;
          category: string;
          importance: "critical" | "important" | "normal";
          appear_count: number;
          appear_contexts: string[];
        }>;
      }>(`/games/${gameId}/collection/recognize-entities`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    // Add recognized entities
    addEntities: (gameId: number, data: {
      items?: Array<{ name: string; description: string; category: string; importance: string }>;
      characters?: Array<{ name: string; description: string; category: string; importance: string }>;
      landmarks?: Array<{ name: string; description: string; category: string; importance: string }>;
    }) =>
      fetchJson<{
        message: string;
        added_items: string[];
        added_characters: string[];
        added_landmarks: string[];
      }>(`/games/${gameId}/collection/add-entities`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    // Create item manually
    createItem: (gameId: number, data: { name: string; generate_description?: boolean }) =>
      fetchJson<{
        message: string;
        item: {
          name: string;
          description: string;
          importance: "critical" | "important" | "normal";
          category: "weapon" | "tool" | "keepsake" | "treasure" | "document" | "other";
          acquired_week: number;
          acquired_context: string;
          is_key_item: boolean;
          image_url: string | null;
          image_generated: boolean;
          description_generated: boolean;
          metadata: Record<string, unknown>;
        };
      }>(`/games/${gameId}/collection/items`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    // Delete entities
    deleteItem: (gameId: number, itemName: string) =>
      fetchJson<{ message: string; success: boolean }>(`/games/${gameId}/collection/items/${encodeURIComponent(itemName)}`, {
        method: 'DELETE',
      }),
    deleteCharacter: (gameId: number, characterName: string) =>
      fetchJson<{ message: string; success: boolean }>(`/games/${gameId}/collection/characters/${encodeURIComponent(characterName)}`, {
        method: 'DELETE',
      }),
    deleteLandmark: (gameId: number, landmarkName: string) =>
      fetchJson<{ message: string; success: boolean }>(`/games/${gameId}/collection/landmarks/${encodeURIComponent(landmarkName)}`, {
        method: 'DELETE',
      }),
  },
};

export default api;

// Named exports for convenience
export const { gameplay, games } = api;
