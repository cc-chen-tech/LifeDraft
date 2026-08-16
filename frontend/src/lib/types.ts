/**
 * Common type definitions for the game
 */

// User types
export interface UserInfo {
  user_id: number;
  public_id: string;
  display_name: string;
  private_id: string;
}

export interface PhoneLoginRequest {
  phone_number: string;
  verification_code?: string | null;
}

export interface VoiceReadingSettingsResponse {
  member_required: boolean;
  enabled: boolean;
  available_voice_colors: string[];
  selected_voice_color: string | null;
  uploaded_voice_available: boolean;
  auto_read_enabled: boolean;
  selected_speed: number;
  tts_provider: string;
  tts_model: string;
  tts_provider_available: boolean;
  backend_audio_enabled: boolean;
  playback_mode: "audio" | "unavailable";
}

export interface VoiceReadingSettingsUpdateRequest {
  selected_voice_color?: string | null;
  auto_read_enabled?: boolean | null;
  selected_speed?: number | null;
}

export interface VoiceUploadConsentRequest {
  consent_confirmed: boolean;
  sample_name?: string | null;
}

export interface ReadingContext {
  source_type: "current_story" | "history_round" | "summary" | "ending";
  game_id: number;
  week?: number | null;
  round_number?: number | null;
  stage?: string | null;
  attempt_id?: string | null;
  day_index?: number | null;
  story_date?: string | null;
  text_hash: string;
  text: string;
}

export interface StoryVoiceReadingRequest {
  context: ReadingContext;
  voice_id: string;
  speed: number;
  auto_play: boolean;
  preferred_provider?: string | null;
}

export interface StoryVoiceReadingResponse {
  job_id: number;
  status: string;
  audio_url?: string | null;
  asset_id?: number | null;
  duration_ms?: number | null;
  playback_mode: "audio" | "unavailable";
  provider: string;
  model: string;
  media_type?: string | null;
  error_code?: string | null;
  message: string;
  segments: VoiceReadingSegment[];
}

export interface VoiceReadingJobResponse {
  job_id: number;
  status: string;
  audio_url?: string | null;
  asset_id?: number | null;
  duration_ms?: number | null;
  playback_mode: "audio" | "unavailable";
  provider: string;
  model: string;
  media_type?: string | null;
  error_code?: string | null;
  message: string;
  segments: VoiceReadingSegment[];
}

export interface VoiceReadingSegment {
  paragraph_index: number;
  status: string;
  audio_url?: string | null;
  asset_id?: number | null;
  duration_ms?: number | null;
  media_type?: string | null;
  error_code?: string | null;
}

export interface VoiceReadingProgress {
  game_id: number;
  day_index: number;
  story_date?: string | null;
  text_hash: string;
  voice_id: string;
  speed: number;
  paragraph_index: number;
  position_ms: number;
  completed: boolean;
  updated_at?: string | null;
}

export interface VoiceAssetResponse {
  asset_id: number;
  source_type: string;
  text_hash: string;
  voice_id: string;
  provider: string;
  model: string;
  storage_path: string;
  duration_ms: number;
  status: string;
}

export interface StoryVoiceErrorResponse {
  error_code: string;
  message: string;
  field?: string | null;
}

// ==================== Core Game Types ====================

/**
 * Era setting for character creation
 */
export interface EraSetting {
  era?: string;
  year?: number;
  era_name?: string;
  era_description?: string;
  world_context?: string;
}

export interface StoryOrigin {
  revision: number;
  start_date: string;
  starting_age: number;
  era_description: string;
  life_stage_description: string;
  world_context: string;
}

/**
 * Key person in the game (NPC)
 */
export interface KeyPerson {
  name: string;
  relationship: string;
  description?: string;
}

/**
 * Character settings from character creation
 * Contains era, key people, and other story settings
 */
export interface CharacterSettings {
  story_origin?: StoryOrigin;
  story_origin_needs_review?: boolean;
  start_date?: string;
  era?: EraSetting;
  key_people?: KeyPerson[];
  relationships_description?: string;
  [key: string]: unknown; // Allow additional settings
}

/**
 * Core player state from backend
 * This reflects the PlayerDataMixin structure
 */
export interface PlayerState {
  // Player identity
  player_name: string;
  life_vision: string;
  
  // Core attributes (0-100 scale)
  energy: number;
  mood: number;
  knowledge: number;
  
  // Time tracking
  age: number;
  week: number;
  timeline?: DailyTimeline | null;
  timeline_version?: number | null;
  day_history?: DayHistoryEntry[];
  
  // Multi-round system
  current_round: number;
  rounds_per_week: number;
  
  // Character settings
  character_settings: CharacterSettings;
  
  // Story state
  last_round_full_story?: string;
  last_event_concluded?: boolean;
  current_event_data?: CurrentEventData | null;
  resume_view?: SavedResumeView | null;
  
  // History
  round_history?: RoundHistoryEntry[];
  weekly_summaries?: WeeklySummary[];
  decision_history?: DecisionHistoryEntry[];
  story_history?: string[];
  
  // Relationships and NPCs
  relationships?: Record<string, number>;
  characters?: Record<string, CharacterState>;
  items?: Record<string, ItemState>;
  landmarks?: Record<string, LandmarkState>;
  
  // Additional fields
  [key: string]: unknown;
}

export interface SavedResumeView {
  phase: "result" | "summary" | "ending" | "generating" | "failed";
  story_text?: string;
  round_summary?: string;
  summary_text?: string;
  resource_warnings?: Array<Record<string, unknown>>;
  error?: string;
  failure?: {
    code?: string;
    summary?: string;
    detail?: string;
    retryable?: boolean;
    attempts_used?: number;
    quality_level?: string;
    operation_id?: string;
  };
  completed_week?: number;
  completed_round?: number;
}

/**
 * Current event data stored in player state
 */
export interface CurrentEventData {
  event_id?: string;
  revision?: number;
  story_date?: string;
  event_description?: string;
  story_text?: string;
  options?: EventOption[];
}

export interface DailyTimeline {
  version: 2;
  start_date: string;
  current_date: string;
  day_index: number;
  day_number: number;
  completed_days: number;
  week_number: number;
  weekday: number;
  total_days: number;
  game_over?: boolean;
}

export interface DayHistoryEntry {
  event_id: string;
  revision: number;
  day_index: number;
  story_date: string;
  event_description: string;
  options: EventOption[];
  choice: string;
  choice_option_index?: number;
  transition_text?: string;
  effects_requested?: EffectValues;
  effects_applied?: EffectValues;
  resource_warnings?: Array<Record<string, unknown>>;
  postprocessing_status?: "pending" | "complete" | "failed";
}

/**
 * Round history entry
 */
export interface RoundHistoryEntry {
  week: number;
  round: number;
  summary?: string;
  event_description?: string;
  story_continuation?: string;
  choice?: string;
  effects?: EffectValues;
}

/**
 * Weekly summary entry
 */
export interface WeeklySummary {
  week: number;
  summary: string;
  bonus_effects?: EffectValues;
}

/**
 * Decision history entry
 */
export interface DecisionHistoryEntry {
  week: number;
  round?: number;
  decision: string;
  effects?: EffectValues;
}

/**
 * Character state (NPC)
 */
export interface CharacterState {
  name: string;
  relationship: string;
  affinity?: number;
  description?: string;
  [key: string]: unknown;
}

/**
 * Item state
 */
export interface ItemState {
  name: string;
  description?: string;
  importance?: string;
  [key: string]: unknown;
}

/**
 * Landmark state
 */
export interface LandmarkState {
  name: string;
  description?: string;
  [key: string]: unknown;
}

/**
 * Effect values from choices
 */
export interface EffectValues {
  energy?: number;
  mood?: number;
  knowledge?: number;
  [key: string]: unknown;
}

/**
 * Game progress tracking
 */
export interface GameProgress {
  week: number;
  current_round: number;
  rounds_per_week: number;
  [key: string]: unknown;
}

/**
 * Round info
 */
export interface RoundInfo {
  week: number;
  current_round: number;
  [key: string]: unknown;
}

// Game types
export interface GameListItem {
  game_id: number;
  player_name: string;
  age?: number;
  week?: number;
  updated_at?: string;
  created_at?: string;
}

export interface PresetInfo {
  preset_id: number;
  preset_name?: string;
  player_name: string;
  life_vision?: string;
  created_at?: string;
  character_settings: CharacterSettings;
}

export interface GameEvent {
  story: string;
  options: EventOption[];
  event_id?: string;
  revision?: number;
  story_date?: string;
}

export interface EventOption {
  text: string;
  effects?: EffectValues;
  transition_text?: string;
  likely_choice?: boolean;
}

export interface GameStateResponse {
  game_id: number;
  player_state: PlayerState;
  progress: GameProgress;
  round_info: RoundInfo;
  current_event: CurrentEventData | null;
  constraint_level: "fast" | "expert" | "master";
  narrative_style_id?: string | null;
  narrative_style_name?: string | null;
}

// ==================== Test Utility Types ====================
// For testing purposes, allow partial objects
export type PartialPlayerState = Partial<PlayerState>;
export type PartialGameProgress = Partial<GameProgress>;
export type PartialRoundInfo = Partial<RoundInfo>;

// Image types
export interface ImageResponse {
  image_id: number;
  image_url: string;
  image_type?: string;
}

export interface OpeningIllustrationResponse {
  image_id: number;
  image_url: string;
  image_type: string;
  scene_description: string;
}

export interface RoundSceneImage {
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
}

// Collection types
export interface CollectionCharacter {
  character_id: number;
  character_name: string;
  character_type: string;
  relationship: string;
  first_meet_week: number;
  first_meet_round: number;
  image_url?: string;
  is_collected: boolean;
}

export interface CollectionStatus {
  characters: CollectionCharacter[];
  total: number;
  collected: number;
}

// Character collection item
export interface CharacterCollectionItem {
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
}

// Item collection item
export interface ItemCollectionItem {
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
  metadata: Record<string, unknown>; // Intentionally flexible for metadata
}

// Landmark collection item
export interface LandmarkCollectionItem {
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
  metadata: Record<string, unknown>; // Intentionally flexible for metadata
}

// Recognized entity for AI recognition
export interface RecognizedEntity {
  name: string;
  description: string;
  category: string;
  importance: "critical" | "important" | "normal";
  appear_count: number;
  appear_contexts: string[];
}

// Collection response from API
export interface CollectionResponse {
  characters: CharacterCollectionItem[];
  items: ItemCollectionItem[];
  landmarks: LandmarkCollectionItem[];
}

// Entity recognition response
export interface EntityRecognitionResponse {
  items: RecognizedEntity[];
  characters: RecognizedEntity[];
  landmarks: RecognizedEntity[];
}
