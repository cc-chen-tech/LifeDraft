/**
 * API Types Contract Tests
 *
 * These tests provide runtime schema validation to catch type mismatches
 * between frontend and backend early. They use Zod for runtime validation
 * of API responses against expected schemas.
 */

import { z } from 'zod';

// ==================== Schema Definitions ====================

/**
 * Constraint level enum - validates only allowed values
 */
export const ConstraintLevelSchema = z.enum(['fast', 'expert', 'master']);

/**
 * GameListItem schema matching backend API contract
 * Based on OpenAPI schema from backend
 */
export const GameListItemSchema = z.object({
  game_id: z.number(),
  player_name: z.string(),
  week: z.number(),
  age: z.number(),
  created_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
  has_progress: z.boolean().default(false),
});

/**
 * GameStateResponse schema for runtime validation
 * Using loose object schema to allow additional properties
 */
export const GameStateResponseSchema = z.object({
  game_id: z.number(),
  player_state: z.object({}).passthrough(),
  progress: z.object({}).passthrough(),
  round_info: z.object({}).passthrough(),
  current_event: z.object({}).passthrough().nullable(),
  constraint_level: ConstraintLevelSchema.default('expert'),
});

/**
 * UserInfo schema
 */
export const UserInfoSchema = z.object({
  user_id: z.number(),
  public_id: z.string(),
  display_name: z.string(),
  private_id: z.string(),
});

/**
 * FriendInfo schema
 */
export const FriendInfoSchema = z.object({
  user_id: z.number(),
  public_id: z.string(),
  display_name: z.string(),
});

/**
 * FriendRequestInfo schema
 */
export const FriendRequestInfoSchema = z.object({
  request_id: z.number(),
  from_user: FriendInfoSchema,
  created_at: z.string(),
});

/**
 * EventOption schema
 * Using passthrough for effects to allow flexible effect values
 */
export const EventOptionSchema = z.object({
  text: z.string(),
  effects: z.object({}).passthrough().optional(),
});

/**
 * GameEvent schema
 */
export const GameEventSchema = z.object({
  story: z.string(),
  options: z.array(EventOptionSchema),
});

/**
 * CharacterCollectionItem schema
 */
export const CharacterCollectionItemSchema = z.object({
  name: z.string(),
  role: z.string(),
  description: z.string(),
  affinity: z.number(),
  age: z.number().nullable(),
  gender: z.string().nullable(),
  occupation: z.string().nullable(),
  personality_traits: z.array(z.string()),
  image_url: z.string().nullable(),
  image_generated: z.boolean(),
  description_generated: z.boolean(),
});

/**
 * ItemCollectionItem schema
 */
export const ItemCollectionItemSchema = z.object({
  name: z.string(),
  description: z.string(),
  importance: z.enum(['critical', 'important', 'normal']),
  category: z.enum(['weapon', 'tool', 'keepsake', 'treasure', 'document', 'other']),
  acquired_week: z.number(),
  acquired_context: z.string(),
  is_key_item: z.boolean(),
  image_url: z.string().nullable(),
  image_generated: z.boolean(),
  description_generated: z.boolean(),
  metadata: z.object({}).passthrough(),
});

/**
 * LandmarkCollectionItem schema
 */
export const LandmarkCollectionItemSchema = z.object({
  name: z.string(),
  description: z.string(),
  category: z.enum(['building', 'nature', 'room', 'area', 'other']),
  importance: z.enum(['critical', 'important', 'normal']),
  first_appear_week: z.number(),
  appear_count: z.number(),
  last_appear_week: z.number(),
  context: z.string(),
  is_key_location: z.boolean(),
  image_url: z.string().nullable(),
  image_generated: z.boolean(),
  metadata: z.object({}).passthrough(),
});

/**
 * RecognizedEntity schema
 */
export const RecognizedEntitySchema = z.object({
  name: z.string(),
  description: z.string(),
  category: z.string(),
  importance: z.enum(['critical', 'important', 'normal']),
  appear_count: z.number(),
  appear_contexts: z.array(z.string()),
});

/**
 * CollectionResponse schema
 */
export const CollectionResponseSchema = z.object({
  characters: z.array(CharacterCollectionItemSchema),
  items: z.array(ItemCollectionItemSchema),
  landmarks: z.array(LandmarkCollectionItemSchema),
});

/**
 * EntityRecognitionResponse schema
 */
export const EntityRecognitionResponseSchema = z.object({
  items: z.array(RecognizedEntitySchema),
  characters: z.array(RecognizedEntitySchema),
  landmarks: z.array(RecognizedEntitySchema),
});

// ==================== Type Exports ====================

export type GameListItemValidated = z.infer<typeof GameListItemSchema>;
export type ConstraintLevelValidated = z.infer<typeof ConstraintLevelSchema>;
export type GameStateResponseValidated = z.infer<typeof GameStateResponseSchema>;

// ==================== Test Suite ====================

describe('API Types Contract Tests', () => {

  describe('Runtime Schema Validation', () => {

    describe('GameListItem', () => {
      it('validates valid GameListItem from backend', () => {
        const backendResponse = {
          game_id: 1,
          player_name: 'Test Player',
          week: 10,
          age: 25,
        };
        const result = GameListItemSchema.safeParse(backendResponse);
        expect(result.success).toBe(true);
      });

      it('validates GameListItem with all optional fields', () => {
        const backendResponse = {
          game_id: 1,
          player_name: 'Test Player',
          week: 10,
          age: 25,
          created_at: '2024-01-15T10:30:00Z',
          updated_at: '2024-01-20T14:45:00Z',
          has_progress: true,
        };
        const result = GameListItemSchema.safeParse(backendResponse);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.has_progress).toBe(true);
        }
      });

      it('fails on missing required field game_id', () => {
        const invalid = {
          player_name: 'Test',
          week: 10,
          age: 25,
        };
        const result = GameListItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('fails on missing required field player_name', () => {
        const invalid = {
          game_id: 1,
          week: 10,
          age: 25,
        };
        const result = GameListItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('fails on missing required field week', () => {
        const invalid = {
          game_id: 1,
          player_name: 'Test',
          age: 25,
        };
        const result = GameListItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('fails on missing required field age', () => {
        const invalid = {
          game_id: 1,
          player_name: 'Test',
          week: 10,
        };
        const result = GameListItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('fails on wrong type for game_id', () => {
        const invalid = {
          game_id: 'not-a-number',
          player_name: 'Test',
          week: 10,
          age: 25,
        };
        const result = GameListItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('fails on wrong type for player_name', () => {
        const invalid = {
          game_id: 1,
          player_name: 123,
          week: 10,
          age: 25,
        };
        const result = GameListItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('applies default value for has_progress when not provided', () => {
        const partial = {
          game_id: 1,
          player_name: 'Test',
          week: 10,
          age: 25,
        };
        const result = GameListItemSchema.safeParse(partial);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.has_progress).toBe(false);
        }
      });
    });

    describe('ConstraintLevel', () => {
      it('validates "fast" as valid constraint_level', () => {
        const valid = { constraint_level: 'fast' };
        const result = ConstraintLevelSchema.safeParse(valid.constraint_level);
        expect(result.success).toBe(true);
      });

      it('validates "expert" as valid constraint_level', () => {
        const valid = { constraint_level: 'expert' };
        const result = ConstraintLevelSchema.safeParse(valid.constraint_level);
        expect(result.success).toBe(true);
      });

      it('validates "master" as valid constraint_level', () => {
        const valid = { constraint_level: 'master' };
        const result = ConstraintLevelSchema.safeParse(valid.constraint_level);
        expect(result.success).toBe(true);
      });

      it('fails on invalid constraint_level value', () => {
        const invalid = { constraint_level: 'invalid_value' };
        const result = ConstraintLevelSchema.safeParse(invalid.constraint_level);
        expect(result.success).toBe(false);
      });

      it('fails on empty string constraint_level', () => {
        const invalid = { constraint_level: '' };
        const result = ConstraintLevelSchema.safeParse(invalid.constraint_level);
        expect(result.success).toBe(false);
      });

      it('fails on numeric constraint_level', () => {
        const invalid = { constraint_level: 123 };
        const result = ConstraintLevelSchema.safeParse(invalid.constraint_level);
        expect(result.success).toBe(false);
      });
    });

    describe('GameStateResponse', () => {
      it('validates valid GameStateResponse with all required fields', () => {
        const validResponse = {
          game_id: 1,
          player_state: { name: 'Test' },
          progress: { week: 1 },
          round_info: { round: 1 },
          current_event: null,
          constraint_level: 'expert',
        };
        const result = GameStateResponseSchema.safeParse(validResponse);
        expect(result.success).toBe(true);
      });

      it('validates GameStateResponse with current_event data', () => {
        const validResponse = {
          game_id: 1,
          player_state: {},
          progress: {},
          round_info: {},
          current_event: { description: 'Test event' },
          constraint_level: 'fast',
        };
        const result = GameStateResponseSchema.safeParse(validResponse);
        expect(result.success).toBe(true);
      });

      it('applies default constraint_level when not provided', () => {
        const partialResponse = {
          game_id: 1,
          player_state: {},
          progress: {},
          round_info: {},
          current_event: null,
        };
        const result = GameStateResponseSchema.safeParse(partialResponse);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.constraint_level).toBe('expert');
        }
      });

      it('fails on invalid constraint_level in GameStateResponse', () => {
        const invalidResponse = {
          game_id: 1,
          player_state: {},
          progress: {},
          round_info: {},
          current_event: null,
          constraint_level: 'invalid',
        };
        const result = GameStateResponseSchema.safeParse(invalidResponse);
        expect(result.success).toBe(false);
      });
    });

    describe('UserInfo', () => {
      it('validates valid UserInfo', () => {
        const valid = {
          user_id: 1,
          public_id: 'abc123',
          display_name: 'Test User',
          private_id: 'private456',
        };
        const result = UserInfoSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('fails on missing user_id', () => {
        const invalid = {
          public_id: 'abc123',
          display_name: 'Test User',
          private_id: 'private456',
        };
        const result = UserInfoSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('FriendInfo', () => {
      it('validates valid FriendInfo', () => {
        const valid = {
          user_id: 1,
          public_id: 'abc123',
          display_name: 'Friend Name',
        };
        const result = FriendInfoSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });
    });

    describe('EventOption', () => {
      it('validates valid EventOption with only text', () => {
        const valid = { text: 'Choose this option' };
        const result = EventOptionSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('validates EventOption with effects', () => {
        const valid = {
          text: 'Choose this',
          effects: { mood: 10, energy: -5 },
        };
        const result = EventOptionSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('fails on missing text field', () => {
        const invalid = { effects: { mood: 10 } };
        const result = EventOptionSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('GameEvent', () => {
      it('validates valid GameEvent', () => {
        const valid = {
          story: 'Once upon a time...',
          options: [{ text: 'Option 1' }, { text: 'Option 2' }],
        };
        const result = GameEventSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('fails on missing story field', () => {
        const invalid = {
          options: [{ text: 'Option 1' }],
        };
        const result = GameEventSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('fails on non-array options', () => {
        const invalid = {
          story: 'Test',
          options: 'not-an-array',
        };
        const result = GameEventSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('CharacterCollectionItem', () => {
      it('validates valid CharacterCollectionItem', () => {
        const valid = {
          name: 'Test Character',
          role: 'NPC',
          description: 'A helpful NPC',
          affinity: 50,
          age: 25,
          gender: 'male',
          occupation: 'merchant',
          personality_traits: ['friendly', 'helpful'],
          image_url: 'https://example.com/image.png',
          image_generated: true,
          description_generated: true,
        };
        const result = CharacterCollectionItemSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('validates with null values for optional fields', () => {
        const valid = {
          name: 'Test Character',
          role: 'NPC',
          description: 'A mysterious figure',
          affinity: 0,
          age: null,
          gender: null,
          occupation: null,
          personality_traits: [],
          image_url: null,
          image_generated: false,
          description_generated: false,
        };
        const result = CharacterCollectionItemSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });
    });

    describe('ItemCollectionItem', () => {
      it('validates valid ItemCollectionItem', () => {
        const valid = {
          name: 'Magic Sword',
          description: 'A powerful weapon',
          importance: 'critical',
          category: 'weapon',
          acquired_week: 5,
          acquired_context: 'Found in a dungeon',
          is_key_item: true,
          image_url: 'https://example.com/sword.png',
          image_generated: true,
          description_generated: true,
          metadata: { damage: 50 },
        };
        const result = ItemCollectionItemSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('fails on invalid importance value', () => {
        const invalid = {
          name: 'Item',
          description: 'Test',
          importance: 'very_important', // Invalid
          category: 'tool',
          acquired_week: 1,
          acquired_context: '',
          is_key_item: false,
          image_url: null,
          image_generated: false,
          description_generated: false,
          metadata: {},
        };
        const result = ItemCollectionItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });

      it('fails on invalid category value', () => {
        const invalid = {
          name: 'Item',
          description: 'Test',
          importance: 'normal',
          category: 'magic_item', // Invalid
          acquired_week: 1,
          acquired_context: '',
          is_key_item: false,
          image_url: null,
          image_generated: false,
          description_generated: false,
          metadata: {},
        };
        const result = ItemCollectionItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('LandmarkCollectionItem', () => {
      it('validates valid LandmarkCollectionItem', () => {
        const valid = {
          name: 'Old Castle',
          description: 'A ancient fortress',
          category: 'building',
          importance: 'important',
          first_appear_week: 3,
          appear_count: 5,
          last_appear_week: 10,
          context: 'Main quest location',
          is_key_location: true,
          image_url: null,
          image_generated: false,
          metadata: {},
        };
        const result = LandmarkCollectionItemSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('fails on invalid category value', () => {
        const invalid = {
          name: 'Place',
          description: 'Test',
          category: 'dimension', // Invalid
          importance: 'normal',
          first_appear_week: 1,
          appear_count: 1,
          last_appear_week: 1,
          context: '',
          is_key_location: false,
          image_url: null,
          image_generated: false,
          metadata: {},
        };
        const result = LandmarkCollectionItemSchema.safeParse(invalid);
        expect(result.success).toBe(false);
      });
    });

    describe('RecognizedEntity', () => {
      it('validates valid RecognizedEntity', () => {
        const valid = {
          name: 'Entity Name',
          description: 'Entity description',
          category: 'character',
          importance: 'important',
          appear_count: 3,
          appear_contexts: ['scene 1', 'scene 2'],
        };
        const result = RecognizedEntitySchema.safeParse(valid);
        expect(result.success).toBe(true);
      });
    });

    describe('CollectionResponse', () => {
      it('validates valid CollectionResponse with empty arrays', () => {
        const valid = {
          characters: [],
          items: [],
          landmarks: [],
        };
        const result = CollectionResponseSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });

      it('validates CollectionResponse with data', () => {
        const valid = {
          characters: [{
            name: 'Character',
            role: 'NPC',
            description: 'Test',
            affinity: 50,
            age: null,
            gender: null,
            occupation: null,
            personality_traits: [],
            image_url: null,
            image_generated: false,
            description_generated: false,
          }],
          items: [],
          landmarks: [],
        };
        const result = CollectionResponseSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });
    });

    describe('EntityRecognitionResponse', () => {
      it('validates valid EntityRecognitionResponse', () => {
        const valid = {
          items: [],
          characters: [],
          landmarks: [],
        };
        const result = EntityRecognitionResponseSchema.safeParse(valid);
        expect(result.success).toBe(true);
      });
    });
  });

  describe('Type Consistency Checks', () => {

    describe('GameListItem field optionality', () => {
      it('confirms game_id is required (not optional)', () => {
        // This test documents that game_id should never be undefined
        const parseResult = GameListItemSchema.safeParse({
          player_name: 'Test',
          week: 1,
          age: 18,
        });
        expect(parseResult.success).toBe(false);
      });

      it('confirms player_name is required (not optional)', () => {
        const parseResult = GameListItemSchema.safeParse({
          game_id: 1,
          week: 1,
          age: 18,
        });
        expect(parseResult.success).toBe(false);
      });

      it('confirms week is required (not optional)', () => {
        const parseResult = GameListItemSchema.safeParse({
          game_id: 1,
          player_name: 'Test',
          age: 18,
        });
        expect(parseResult.success).toBe(false);
      });

      it('confirms age is required (not optional)', () => {
        const parseResult = GameListItemSchema.safeParse({
          game_id: 1,
          player_name: 'Test',
          week: 1,
        });
        expect(parseResult.success).toBe(false);
      });

      it('confirms created_at is optional', () => {
        const parseResult = GameListItemSchema.safeParse({
          game_id: 1,
          player_name: 'Test',
          week: 1,
          age: 18,
        });
        expect(parseResult.success).toBe(true);
      });

      it('confirms updated_at is optional', () => {
        const parseResult = GameListItemSchema.safeParse({
          game_id: 1,
          player_name: 'Test',
          week: 1,
          age: 18,
        });
        expect(parseResult.success).toBe(true);
      });

      it('confirms has_progress has default value', () => {
        const parseResult = GameListItemSchema.safeParse({
          game_id: 1,
          player_name: 'Test',
          week: 1,
          age: 18,
        });
        expect(parseResult.success).toBe(true);
        if (parseResult.success) {
          expect(parseResult.data.has_progress).toBeDefined();
          expect(parseResult.data.has_progress).toBe(false);
        }
      });
    });

    describe('constraint_level enum validation', () => {
      it('accepts all valid constraint_level values', () => {
        const validValues = ['fast', 'expert', 'master'];
        validValues.forEach(value => {
          const result = ConstraintLevelSchema.safeParse(value);
          expect(result.success).toBe(true);
        });
      });

      it('rejects all invalid constraint_level values', () => {
        const invalidValues = ['', 'easy', 'hard', 'beginner', 'advanced', 123, null, undefined];
        invalidValues.forEach(value => {
          const result = ConstraintLevelSchema.safeParse(value);
          expect(result.success).toBe(false);
        });
      });
    });

    describe('New fields have default values', () => {
      it('has_progress defaults to false when not provided', () => {
        const result = GameListItemSchema.safeParse({
          game_id: 1,
          player_name: 'Test',
          week: 1,
          age: 18,
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.has_progress).toBe(false);
        }
      });

      it('constraint_level defaults to expert in GameStateResponse', () => {
        const result = GameStateResponseSchema.safeParse({
          game_id: 1,
          player_state: {},
          progress: {},
          round_info: {},
          current_event: null,
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.constraint_level).toBe('expert');
        }
      });
    });
  });

  describe('Backend Response Simulation', () => {

    it('validates realistic backend GameListItem response', () => {
      // Simulates actual response from GET /api/games
      const backendResponse = {
        game_id: 42,
        player_name: 'Alice',
        week: 15,
        age: 22,
        created_at: '2024-01-10T08:00:00Z',
        updated_at: '2024-01-20T16:30:00Z',
        has_progress: true,
      };
      const result = GameListItemSchema.safeParse(backendResponse);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.game_id).toBe(42);
        expect(result.data.player_name).toBe('Alice');
        expect(result.data.week).toBe(15);
        expect(result.data.age).toBe(22);
        expect(result.data.has_progress).toBe(true);
      }
    });

    it('validates realistic backend GameStateResponse', () => {
      // Simulates actual response from GET /api/games/{game_id}
      const backendResponse = {
        game_id: 42,
        player_state: {
          player_name: 'Alice',
          life_vision: 'Become a master wizard',
          energy: 80,
          mood: 90,
          knowledge: 75,
          wealth: 50,
          age: 22,
          week: 15,
          current_round: 3,
          rounds_per_week: 3,
          character_settings: {
            era: { era: 'fantasy', era_name: 'High Fantasy' },
          },
        },
        progress: { week: 15, current_round: 3, rounds_per_week: 3 },
        round_info: { week: 15, current_round: 3 },
        current_event: {
          event_description: 'A dragon appears!',
          story_text: 'The massive beast lands before you...',
          options: [
            { text: 'Fight the dragon', effects: { energy: -20 } },
            { text: 'Flee', effects: { mood: -10 } },
          ],
        },
        constraint_level: 'expert',
      };
      const result = GameStateResponseSchema.safeParse(backendResponse);
      expect(result.success).toBe(true);
    });

    it('validates backend response with null current_event', () => {
      const backendResponse = {
        game_id: 42,
        player_state: {},
        progress: {},
        round_info: {},
        current_event: null,
        constraint_level: 'fast',
      };
      const result = GameStateResponseSchema.safeParse(backendResponse);
      expect(result.success).toBe(true);
    });
  });
});

// ==================== Helper Functions for Runtime Validation ====================

/**
 * Validates a GameListItem at runtime
 * @param data - Unknown data to validate
 * @returns Validated GameListItem or throws error
 */
export function validateGameListItem(data: unknown): GameListItemValidated {
  return GameListItemSchema.parse(data);
}

/**
 * Validates a GameStateResponse at runtime
 * @param data - Unknown data to validate
 * @returns Validated GameStateResponse or throws error
 */
export function validateGameStateResponse(data: unknown): GameStateResponseValidated {
  return GameStateResponseSchema.parse(data);
}

/**
 * Validates a ConstraintLevel at runtime
 * @param data - Unknown data to validate
 * @returns Validated ConstraintLevel or throws error
 */
export function validateConstraintLevel(data: unknown): ConstraintLevelValidated {
  return ConstraintLevelSchema.parse(data);
}

/**
 * Safe validation helpers that return null instead of throwing
 */
export function safeValidateGameListItem(data: unknown): GameListItemValidated | null {
  const result = GameListItemSchema.safeParse(data);
  return result.success ? result.data : null;
}

export function safeValidateGameStateResponse(data: unknown): GameStateResponseValidated | null {
  const result = GameStateResponseSchema.safeParse(data);
  return result.success ? result.data : null;
}
