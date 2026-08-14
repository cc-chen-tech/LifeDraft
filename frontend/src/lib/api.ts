/**
 * API client for the game backend
 */

import type {
  PlayerState,
  GameProgress,
  RoundInfo,
  CurrentEventData,
  CharacterSettings,
  StoryOrigin,
  EffectValues,
  StoryVoiceReadingRequest,
  StoryVoiceReadingResponse,
  VoiceReadingProgress,
  VoiceReadingJobResponse,
  VoiceReadingSettingsResponse,
  VoiceReadingSettingsUpdateRequest,
  VoiceUploadConsentRequest,
  GameStateResponse,
} from './types';
import { resolveApiBase } from './apiBase';

const API_BASE = resolveApiBase();
export const LIFE_SUMMARY_REQUEST_TIMEOUT_MS = 30_000;

export interface PortraitImageGenerationJob {
  job_id: number;
  game_id: number;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  image_id: number | null;
  attempt_count: number;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/**
 * 401 重定向防抖：防止并发请求竞态导致多次重定向
 * 一旦触发登出，后续 401 不再重复处理
 */
let isRedirectingTo401 = false;

function handle401Redirect() {
  // 清除 localStorage 中的游戏状态
  localStorage.removeItem('gameId');
  localStorage.removeItem('gameState');

  if (isRedirectingTo401) return; // 已在处理中，只跳过重复跳转
  isRedirectingTo401 = true;

  console.warn('[API] Session expired or invalid, redirecting to home...');
  // 跳转到首页（如果不是已经在首页）
  if (typeof window !== 'undefined' && window.location.pathname !== '/') {
    window.location.href = '/';
  }
  
  // 3 秒后重置标志，允许后续重新触发（以防跳转失败）
  setTimeout(() => { isRedirectingTo401 = false; }, 3000);
}

export function shouldRetryApiResponse(status: number, url: string, attemptIndex: number): boolean {
  if (url.includes('/voice-reading/')) return false;
  if (isChoiceMutation(url)) return false;
  if (isImageGenerationMutation(url)) return false;
  if (status === 502 || status === 504) return true;
  if (status >= 500) return true;
  if (status !== 401) return false;
  return attemptIndex === 0;
}

export function shouldRetryApiError(url: string, attemptIndex: number, retries: number): boolean {
  if (url.includes('/voice-reading/')) return false;
  if (isChoiceMutation(url)) return false;
  if (isImageGenerationMutation(url)) return false;
  return attemptIndex < retries - 1;
}

function isChoiceMutation(url: string): boolean {
  return url.endsWith('/choice-sync') || url.endsWith('/custom-choice-sync');
}

function isImageGenerationMutation(url: string): boolean {
  if (url.includes('/collection/')) {
    return url.includes('/generate-image') || url.includes('/regenerate-image');
  }

  if (!url.includes('/images/')) return false;
  if (url.includes('/images/scene/')) return true;

  return [
    '/images/generate',
    '/images/character/generate-async',
    '/images/player',
    '/images/regenerate',
    '/images/regenerate-fresh',
    '/images/opening-illustration',
    '/images/scene/generate',
    '/images/scene/regenerate',
  ].some((path) => url === path || url.startsWith(`${path}?`) || url.startsWith(`${path}/`));
}

function sleepWithSignal(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.reject(new DOMException('The operation was aborted.', 'AbortError'));
  }

  return new Promise<void>((resolve, reject) => {
    const handleAbort = () => {
      clearTimeout(timeoutId);
      reject(new DOMException('The operation was aborted.', 'AbortError'));
    };
    const timeoutId = setTimeout(() => {
      signal?.removeEventListener('abort', handleAbort);
      resolve();
    }, ms);
    signal?.addEventListener('abort', handleAbort, { once: true });
  });
}

/**
 * L-03: Fetch with retry mechanism for transient failures
 * Implements exponential backoff for server errors (5xx)
 */
async function fetchWithRetry(
  url: string, 
  options: RequestInit & { timeout?: number }, 
  retries = 3
): Promise<{ response: Response; cleanup: () => void }> {
  const { timeout, ...fetchOptions } = options;
  const externalSignal = fetchOptions.signal;
  let lastError: Error | null = null;
  
  for (let i = 0; i < retries; i++) {
    if (externalSignal?.aborted) {
      throw new DOMException('The operation was aborted.', 'AbortError');
    }
    const controller = new AbortController();
    const timeoutId = timeout ? setTimeout(() => controller.abort(), timeout) : null;
    const abortFromExternalSignal = () => controller.abort();
    externalSignal?.addEventListener('abort', abortFromExternalSignal, { once: true });
    let cleanedUp = false;
    const cleanup = () => {
      if (cleanedUp) return;
      cleanedUp = true;
      if (timeoutId) clearTimeout(timeoutId);
      externalSignal?.removeEventListener('abort', abortFromExternalSignal);
    };
    
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
      
      if (response.ok || !shouldRetryApiResponse(response.status, url, i)) {
        // Keep the timeout and caller signal linked until fetchJson finishes
        // consuming the body. Aborting only the header fetch is insufficient.
        return { response, cleanup };
      }

      // Server error - will retry
      cleanup();
      lastError = new Error(`Server error: ${response.status}`);
      console.warn(`[API] Server error (${response.status}), attempt ${i + 1}/${retries}`);
    } catch (error) {
      cleanup();
      
      // Don't retry on abort
      if (error instanceof Error && error.name === 'AbortError') {
        throw error;
      }
      
      lastError = error instanceof Error ? error : new Error(String(error));
      console.warn(`[API] Request failed, attempt ${i + 1}/${retries}:`, error);
      
      // On last retry, or for endpoints that need immediate fallback, throw immediately.
      if (!shouldRetryApiError(url, i, retries)) {
        throw lastError;
      }
    }
    
    // Exponential backoff: 1s, 2s, 4s, ...
    await sleepWithSignal(Math.pow(2, i) * 1000, externalSignal || undefined);
  }
  
  throw lastError || new Error('Max retries exceeded');
}

async function fetchJson<T>(url: string, options?: RequestInit & { timeout?: number }): Promise<T> {
  const { response, cleanup } = await fetchWithRetry(url, options || {});

  try {
    if (!response.ok) {
      const error = await response.json().catch((bodyError: unknown) => {
        if (
          options?.signal?.aborted ||
          (bodyError instanceof Error && bodyError.name === 'AbortError')
        ) {
          throw bodyError;
        }
        return { message: response.statusText };
      });
      const detail = error.detail;
      let errorMessage = error.message || response.statusText || 'Request failed';
      let errorCode: string | undefined;
      let retryable: boolean | undefined;
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (detail && typeof detail === 'object') {
        const detailRecord = detail as Record<string, unknown>;
        errorCode = typeof detailRecord.code === 'string' ? detailRecord.code : undefined;
        retryable = typeof detailRecord.retryable === 'boolean' ? detailRecord.retryable : undefined;
        const detailParts = [detailRecord.error, detailRecord.message]
          .filter((part): part is string => typeof part === 'string' && part.trim().length > 0);
        if (detailParts.length > 0) {
          errorMessage = detailParts.join(': ');
        }
      }

      // ★ 401 未授权 - 对于 /auth/me 这是正常的未登录状态，不显示错误日志
      if (response.status === 401 && url === '/auth/me') {
        // 静默处理，不显示错误日志
        throw Object.assign(new Error(errorMessage), {
          status: response.status,
          code: errorCode,
          retryable,
        });
      }

      // ★ 401 未授权 - 收集面板请求静默处理，不触发重定向
      if (response.status === 401 && url.includes('/collection/')) {
        console.warn(`[API] Collection API 401 — cookie may not have been forwarded: ${url}`);
        throw Object.assign(new Error(errorMessage || 'Authentication required'), {
          status: response.status,
          code: errorCode,
          retryable,
        });
      }

      if (response.status === 401 && url.includes('/voice-reading/')) {
        console.warn(`[API] Voice reading API 401 — falling back without redirect: ${url}`);
        throw Object.assign(new Error(error.message || 'Authentication required'), {
          status: response.status,
          code: errorCode,
          retryable,
        });
      }

      // ★ 404 未找到 - 对于场景图片查询，这是正常的未生成状态，不显示错误日志
      if (response.status === 404 && url.includes('/images/scene/')) {
        // 静默处理，前端会轮询直到图片生成完成
        throw Object.assign(new Error(errorMessage), {
          status: response.status,
          code: errorCode,
          retryable,
        });
      }

      console.error(`[API Error] ${url} failed with ${response.status}:`, errorMessage);

      // ★ 401 未授权 - 使用防竞态的重定向处理
      if (response.status === 401) {
        handle401Redirect();
      }

      throw Object.assign(new Error(errorMessage), {
        status: response.status,
        code: errorCode,
        retryable,
      });
    }

    return await response.json();
  } finally {
    cleanup();
  }
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
      fetchJson<GameStateResponse>('/games', {
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
    getActive: (signal?: AbortSignal) =>
      fetchJson<{
        game_id: number;
        player_state: PlayerState;
        progress: GameProgress;
        round_info: RoundInfo;
        current_event: CurrentEventData | null;
        constraint_level: "fast" | "expert" | "master";
      }>('/games/active', { signal }),
    updateSettings: (gameId: number, data: { constraint_level?: string }) =>
      fetchJson<{ success: boolean; message: string }>(`/games/${gameId}/settings`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    patchCharacterSettings: (
      gameId: number,
      characterSettings: CharacterSettings,
      identity?: { player_name?: string; life_vision?: string },
    ) =>
      fetchJson<{ success: boolean; message: string }>(`/games/${gameId}/character-settings`, {
        method: 'PATCH',
        body: JSON.stringify({ character_settings: characterSettings, ...identity }),
      }),
    replaceStoryOrigin: (
      gameId: number,
      data: { expected_revision: number; story_origin: StoryOrigin },
    ) =>
      fetchJson<{
        success: boolean;
        story_origin: StoryOrigin;
        timeline: import('./types').DailyTimeline;
        character_settings: CharacterSettings;
      }>(`/games/${gameId}/story-origin`, {
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
    getState: (gameId: number, signal?: AbortSignal) =>
      fetchJson<{
        player_state: PlayerState;
        progress: GameProgress;
        round_info: RoundInfo;
        current_event: CurrentEventData | null;
        constraint_level: "fast" | "expert" | "master";
        narrative_style_id?: string | null;
        narrative_style_name?: string | null;
      }>(`/games/${gameId}`, { signal }),
    generateEvent: (gameId: number, data?: { custom_choices?: string[] }) =>
      fetchJson<{
        story: string;
        options: Array<{ text: string; effects?: EffectValues }>;
      }>(`/games/${gameId}/event-sync`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      }),
    acknowledgeResumeView: (gameId: number) =>
      fetchJson<{ acknowledged: boolean }>(`/games/${gameId}/resume-view/acknowledge`, {
        method: 'POST',
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
        timeout: LIFE_SUMMARY_REQUEST_TIMEOUT_MS,
      }),
    // Synchronous choice methods (non-streaming)
    makeChoiceSync: (gameId: number, data: { option_index: number; event_id?: string; revision?: number }, signal?: AbortSignal) =>
      fetchJson<{
        story_continuation: string;
        summary: string;
        effects_applied: Record<string, number>;
        effects_requested?: Record<string, number>;
        resource_warnings?: Array<Record<string, unknown>>;
        need_weekly_summary: boolean;
        weekly_summary?: string;
        game_over?: boolean;
        next_timeline?: import("./types").DailyTimeline;
      }>(`/games/${gameId}/choice-sync`, {
        method: 'POST',
        body: JSON.stringify(data),
        signal,
      }),
    makeCustomChoiceSync: (gameId: number, data: { custom_text: string }, signal?: AbortSignal) =>
      fetchJson<{
        story_continuation: string;
        summary: string;
        effects_applied: Record<string, number>;
        effects_requested?: Record<string, number>;
        resource_warnings?: Array<Record<string, unknown>>;
        need_weekly_summary: boolean;
        weekly_summary?: string;
        game_over?: boolean;
      }>(`/games/${gameId}/custom-choice-sync`, {
        method: 'POST',
        body: JSON.stringify(data),
        signal,
      }),
  },

  // Character
  character: {
    generateStoryOrigin: (data: {
      player_name: string;
      life_vision?: string;
      previous_settings?: CharacterSettings;
      feedback?: string | null;
      language?: string;
    }) =>
      fetchJson<StoryOrigin>('/character/story-origin', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    generateSetting: (data: {
      setting_type: string;
      player_name?: string;
      life_vision?: string;
      previous_settings?: CharacterSettings;
      feedback?: string | null;
      language?: string;
      character_settings?: CharacterSettings
    }) =>
      fetchJson<Record<string, unknown>>('/character/setting', {
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

  // Story voice reading
  voice_reading: {
    getSettings: () =>
      fetchJson<VoiceReadingSettingsResponse>('/voice-reading/settings'),
    updateSettings: (data: VoiceReadingSettingsUpdateRequest) =>
      fetchJson<VoiceReadingSettingsResponse>('/voice-reading/settings', {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    requestReading: (data: StoryVoiceReadingRequest) =>
      fetchJson<StoryVoiceReadingResponse>('/voice-reading/read', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getJob: (jobId: number) =>
      fetchJson<VoiceReadingJobResponse>(`/voice-reading/jobs/${jobId}`),
    getProgress: (identity: Pick<VoiceReadingProgress, 'game_id' | 'day_index' | 'text_hash' | 'voice_id' | 'speed'>) => {
      const query = new URLSearchParams({
        game_id: String(identity.game_id),
        day_index: String(identity.day_index),
        text_hash: identity.text_hash,
        voice_id: identity.voice_id,
        speed: String(identity.speed),
      });
      return fetchJson<VoiceReadingProgress>(`/voice-reading/progress?${query.toString()}`);
    },
    updateProgress: (data: VoiceReadingProgress) =>
      fetchJson<VoiceReadingProgress>('/voice-reading/progress', {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    uploadConsent: (data: VoiceUploadConsentRequest) =>
      fetchJson<{ success: boolean; message: string }>('/voice-reading/upload-consent', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
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
    enqueueCharacterPortrait: (data: {
      game_id: number;
      image_type: 'character';
      entity_name: string;
      description: string;
      entity_key: 'player_main';
      era?: string;
      extra_context?: Record<string, unknown>;
      feedback?: string;
    }) =>
      fetchJson<PortraitImageGenerationJob>('/images/character/generate-async', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getCharacterPortraitJob: (jobId: number) =>
      fetchJson<PortraitImageGenerationJob>(`/images/character/jobs/${jobId}`),
    getLatestCharacterPortraitJob: (gameId: number) =>
      fetchJson<PortraitImageGenerationJob | null>(`/images/character/jobs/latest?game_id=${gameId}`),
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
      fetchJson<{ image_id: number; image_url: string; image_type: string; scene_description: string }>('/images/opening-illustration', {
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
      fetchJson<{ image_id: number; image_url: string; image_type: string; scene_description: string }>('/images/opening-illustration/regenerate', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getRoundSceneImage: (
      gameId: number,
      roundNumber: number,
      week?: number,
      options?: { retry?: boolean }
    ) =>
      fetchJson<{
        scene_id: number;
        week: number;
        round_number: number;
        story_date?: string;
        day_index?: number;
        stage: string;
        image_url: string;
        scene_description: string;
        referenced_images?: number[];
        created_at: string;
      }>(
        `/images/scene/${gameId}/${roundNumber}` +
        `${week !== undefined ? `?week=${week}` : ''}` +
        `${options?.retry ? `${week !== undefined ? '&' : '?'}retry=true` : ''}`
      ),
    getRoundSceneImageByStage: (
      gameId: number,
      roundNumber: number,
      stage: string,
      week?: number,
      options?: { retry?: boolean }
    ) =>
      fetchJson<{
        scene_id: number;
        week: number;
        round_number: number;
        story_date?: string;
        day_index?: number;
        stage: string;
        image_url: string;
        scene_description: string;
        referenced_images?: number[];
        created_at: string;
      }>(
        `/images/scene/${gameId}/${roundNumber}?stage=${encodeURIComponent(stage)}` +
        `${week !== undefined ? `&week=${week}` : ''}` +
        `${options?.retry ? '&retry=true' : ''}`
      ),
    getAllRoundSceneImages: (gameId: number) =>
      fetchJson<{
        scenes: Array<{
          scene_id: number;
          week: number;
          round_number: number;
          story_date?: string;
          day_index?: number;
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
      story_date?: string;
      day_index?: number;
    }) =>
      fetchJson<{
        scene_id: number;
        week: number;
        round_number: number;
        story_date?: string;
        day_index?: number;
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
