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

export interface FriendInfo {
  user_id: number;
  public_id: string;
  display_name: string;
}

export interface FriendRequestInfo {
  request_id: number;
  from_user: FriendInfo;
  created_at: string;
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
  character_settings: Record<string, unknown>;
}

export interface GameEvent {
  story: string;
  options: EventOption[];
}

export interface EventOption {
  text: string;
  effects?: Record<string, unknown>;
}

export interface GameStateResponse {
  game_id: number;
  player_state: Record<string, unknown>;
  progress: Record<string, unknown>;
  round_info: Record<string, unknown>;
  current_event: Record<string, unknown> | null;
}

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
  metadata: Record<string, unknown>;
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
  metadata: Record<string, unknown>;
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
