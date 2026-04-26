/**
 * API client for the game backend
 */

import type {
  PlayerState,
  GameProgress,
  RoundInfo,
  CurrentEventData,
  CharacterSettings,
  EffectValues,
  EventOption,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';

/**
 * 401 重定向防抖：防止并发请求竞态导致多次重定向
 * 一旦触发登出，后续 401 不再重复处理
 */
let isRedirectingTo401 = false;

function handle401Redirect() {
  if (isRedirectingTo401) return; // 已在处理中，跳过
  isRedirectingTo401 = true;
  
  console.warn('[API] Session expired or invalid, redirecting to home...');
  // 清除 localStorage 中的游戏状态
  localStorage.removeItem('gameId');
  localStorage.removeItem('gameState');
  // 跳转到首页（如果不是已经在首页）
  if (typeof window !== 'undefined' && window.location.pathname !== '/') {
    window.location.href = '/';
  }
  
  // 3 秒后重置标志，允许后续重新触发（以防跳转失败）
  setTimeout(() => { isRedirectingTo401 = false; }, 3000);
}

/**
 * L-03: Fetch with retry mechanism for transient failures
 * Implements exponential backoff for server errors (5xx)
 */
async function fetchWithRetry(
  url: string, 
  options: RequestInit & { timeout?: number }, 
  retries = 3
): Promise<Response> {
  const { timeout, ...fetchOptions } = options;
  let lastError: Error | null = null;
  
  for (let i = 0; i < retries; i++) {
    const controller = new AbortController();
    const timeoutId = timeout ? setTimeout(() => controller.abort(), timeout) : null;
    
    try {
      const response = await fetch(`${API_BASE}${url}`, {
        ...fetchOptions,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions?.headers,
        },
        credentials: 'include',
      });
      
      if (timeoutId) clearTimeout(timeoutId);
      
      // Only retry on server errors (5xx) or transient 401 (cookie forwarding race)
      if (response.ok || (response.status < 500 && response.status !== 401)) {
        return response;
      }
      
      // 401 只重试一次（第一次可能是 cookie 转发竞态）
      if (response.status === 401 && i > 0) {
        return response;
      }
      
      // Server error - will retry
      lastError = new Error(`Server error: ${response.status}`);
      console.warn(`[API] Server error (${response.status}), attempt ${i + 1}/${retries}`);
    } catch (error) {
      if (timeoutId) clearTimeout(timeoutId);
      
      // Don't retry on abort
      if (error instanceof Error && error.name === 'AbortError') {
        throw error;
      }
      
      lastError = error instanceof Error ? error : new Error(String(error));
      console.warn(`[API] Request failed, attempt ${i + 1}/${retries}:`, error);
      
      // On last retry, throw immediately
      if (i === retries - 1) {
        throw lastError;
      }
    }
    
    // Exponential backoff: 1s, 2s, 4s, ...
    await new Promise(r => setTimeout(r, Math.pow(2, i) * 1000));
  }
  
  throw lastError || new Error('Max retries exceeded');
}

async function fetchJson<T>(url: string, options?: RequestInit & { timeout?: number }): Promise<T> {
  const response = await fetchWithRetry(url, options || {});

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));

    // ★ 401 未授权 - 对于 /auth/me 这是正常的未登录状态，不显示错误日志
    if (response.status === 401 && url === '/auth/me') {
      // 静默处理，不显示错误日志
      throw Object.assign(new Error(error.message || 'Request failed'), { status: response.status });
    }

    // ★ 401 未授权 - 收集面板请求静默处理，不触发重定向
    if (response.status === 401 && url.includes('/collection/')) {
      console.warn(`[API] Collection API 401 — cookie may not have been forwarded: ${url}`);
      throw Object.assign(new Error(error.message || 'Authentication required'), { status: response.status });
    }

    // ★ 404 未找到 - 对于场景图片查询，这是正常的未生成状态，不显示错误日志
    if (response.status === 404 && url.includes('/images/scene/')) {
      // 静默处理，前端会轮询直到图片生成完成
      throw Object.assign(new Error(error.message || 'Request failed'), { status: response.status });
    }

    console.error(`[API Error] ${url} failed with ${response.status}:`, error.message || response.statusText);
    
    // ★ 401 未授权 - 使用防竞态的重定向处理
    if (response.status === 401) {
      handle401Redirect();
    }
    
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
    create: (data: { player_name: string; life_vision?: string; character_settings?: CharacterSettings; language?: string; constraint_level?: string }) =>
      fetchJson<{ game_id: number }>('/games', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    load: (gameId: number) =>
      fetchJson<{
        game_id: number;
        player_state: PlayerState;
        progress: GameProgress;
        round_info: RoundInfo;
        current_event: CurrentEventData | null;
        constraint_level: "fast" | "expert" | "master";
      }>(`/games/${gameId}`),
    save: (gameId: number) =>
      fetchJson<{ success: boolean }>(`/games/${gameId}/save`, { method: 'POST' }),
    delete: (gameId: number) =>
      fetchJson<{ success: boolean }>(`/games/${gameId}`, { method: 'DELETE' }),
    getActive: () =>
      fetchJson<{
        game_id: number;
        player_state: PlayerState;
        progress: GameProgress;
        round_info: RoundInfo;
        current_event: CurrentEventData | null;
        constraint_level: "fast" | "expert" | "master";
      }>('/games/active'),
    updateSettings: (gameId: number, data: { constraint_level?: string }) =>
      fetchJson<{ success: boolean; message: string }>(`/games/${gameId}/settings`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    // Narrative style
    listNarrativeStyles: (gameId: number) =>
      fetchJson<Array<{ style_id: string; style_name: string; description: string }>>(`/games/${gameId}/narrative-style-options`),
    getNarrativeStyle: (gameId: number) =>
      fetchJson<{ style_id: string; style_name: string }>(`/games/${gameId}/narrative-style`),
    updateNarrativeStyle: (gameId: number, styleId: string) =>
      fetchJson<{ success: boolean; message: string }>(`/games/${gameId}/narrative-style`, {
        method: 'PUT',
        body: JSON.stringify({ style_id: styleId }),
      }),
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
        character_settings: CharacterSettings;
      }>>('/presets'),
    create: (data: { preset_name: string; player_name: string; life_vision?: string; character_settings?: CharacterSettings }) =>
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
        player_state: PlayerState;
        progress: GameProgress;
        round_info: RoundInfo;
        current_event: CurrentEventData | null;
        constraint_level: "fast" | "expert" | "master";
      }>(`/games/${gameId}`),
    generateEvent: (gameId: number, data?: { custom_choices?: string[] }) =>
      fetchJson<{
        story: string;
        options: Array<{ text: string; effects?: EffectValues }>;
      }>(`/games/${gameId}/events`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      }),
    submitChoice: (gameId: number, data: { choice_index: number; custom_choice?: string }) =>
      fetchJson<{
        result: string;
        new_event: CurrentEventData | null;
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
        player_state: PlayerState;
        summary?: string;
        need_weekly_summary?: boolean;
        weekly_summary?: string;
        game_over?: boolean;
      }>(`/games/${gameId}/choice-sync`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    makeCustomChoiceSync: (gameId: number, data: { custom_text: string }) =>
      fetchJson<{
        result: string;
        story: string;
        current_round: number;
        current_week: number;
        player_state: PlayerState;
        summary?: string;
        need_weekly_summary?: boolean;
        weekly_summary?: string;
        game_over?: boolean;
      }>(`/games/${gameId}/custom-choice-sync`, {
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
      previous_settings?: CharacterSettings;
      feedback?: string | null;
      language?: string;
      character_settings?: CharacterSettings
    }) =>
      fetchJson<{ era: string; era_description: string }>('/character/setting', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateRelationship: (data: {
      relationship_type?: string;
      player_name?: string;
      life_vision?: string;
      previous_settings?: CharacterSettings;
      existing_people?: Array<Record<string, unknown>>;
      person_index?: number;
      total_needed?: number;
      feedback?: string | null;
      language?: string;
      character_settings?: CharacterSettings
    }) =>
      fetchJson<{ name: string; relationship: string }>('/character/relationship', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateRelationshipsSummary: (data: {
      character_settings?: CharacterSettings;
      player_name?: string;
      life_vision?: string;
      previous_settings?: CharacterSettings;
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
      extra_context?: Record<string, unknown>; // Intentionally flexible
      feedback?: string;
    }) =>
      fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>('/images/generate', {
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
      character_settings: CharacterSettings;
      player_name: string;
      life_vision?: string;
    }) =>
      fetchJson<{ image_id: number; image_url: string; image_type: string }>('/images/player', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateOpeningIllustration: (data: {
      game_id: number;
      character_settings: CharacterSettings;
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
      character_settings: CharacterSettings;
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
      character_settings: CharacterSettings;
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
      character_settings: CharacterSettings;
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
          metadata: Record<string, unknown>; // Intentionally flexible for item metadata
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
          metadata: Record<string, unknown>; // Intentionally flexible for item metadata
        }>;
      }>(`/collection/${gameId}/details`),
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
      }>(`/collection/${gameId}`),
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
      fetchJson<{ image_url: string; success: boolean }>(`/collection/${gameId}/characters/${encodeURIComponent(name)}/generate-image`, {
        method: 'POST',
      }),
    regenerateCharacterImage: (gameId: number, name: string, feedback?: string, imageId?: number) =>
      fetchJson<{ image_url: string; success: boolean }>(`/collection/${gameId}/characters/${encodeURIComponent(name)}/regenerate-image`, {
        method: 'POST',
        body: JSON.stringify({ feedback, image_id: imageId }),
      }),
    // Character description generation
    generateCharacterDescription: (gameId: number, name: string) =>
      fetchJson<{ description: string; success: boolean }>(`/collection/${gameId}/characters/${encodeURIComponent(name)}/generate-description`, {
        method: 'POST',
      }),
    // Item image generation
    generateItemImage: (gameId: number, itemName: string) =>
      fetchJson<{ image_url: string; success: boolean }>(`/collection/${gameId}/items/${encodeURIComponent(itemName)}/generate-image`, {
        method: 'POST',
      }),
    regenerateItemImage: (gameId: number, itemName: string, feedback?: string) =>
      fetchJson<{ image_url: string; success: boolean }>(`/collection/${gameId}/items/${encodeURIComponent(itemName)}/regenerate-image`, {
        method: 'POST',
        body: JSON.stringify({ feedback }),
      }),
    // Item description generation
    generateItemDescription: (gameId: number, itemName: string) =>
      fetchJson<{ description: string; success: boolean }>(`/collection/${gameId}/items/${encodeURIComponent(itemName)}/generate-description`, {
        method: 'POST',
      }),
    // Landmark image generation
    generateLandmarkImage: (gameId: number, landmarkName: string) =>
      fetchJson<{ image_url: string; success: boolean }>(`/collection/${gameId}/landmarks/${encodeURIComponent(landmarkName)}/generate-image`, {
        method: 'POST',
      }),
    // Landmark description generation
    generateLandmarkDescription: (gameId: number, landmarkName: string) =>
      fetchJson<{ description: string; success: boolean }>(`/collection/${gameId}/landmarks/${encodeURIComponent(landmarkName)}/generate-description`, {
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
      }>(`/collection/${gameId}/recognize-entities`, {
        method: 'POST',
        body: JSON.stringify(data),
        timeout: 180000, // 3分钟超时，实体识别可能需要较长时间
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
      }>(`/collection/${gameId}/add-entities`, {
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
          metadata: Record<string, unknown>; // Intentionally flexible for item metadata
        };
      }>(`/collection/${gameId}/items/create`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    // Delete entities
    deleteItem: (gameId: number, itemName: string) =>
      fetchJson<{ message: string; success: boolean }>(`/collection/${gameId}/items/${encodeURIComponent(itemName)}`, {
        method: 'DELETE',
      }),
    deleteCharacter: (gameId: number, characterName: string) =>
      fetchJson<{ message: string; success: boolean }>(`/collection/${gameId}/characters/${encodeURIComponent(characterName)}`, {
        method: 'DELETE',
      }),
    deleteLandmark: (gameId: number, landmarkName: string) =>
      fetchJson<{ message: string; success: boolean }>(`/collection/${gameId}/landmarks/${encodeURIComponent(landmarkName)}`, {
        method: 'DELETE',
      }),
  },
};

export default api;

// Named exports for convenience
export const { gameplay, games } = api;
