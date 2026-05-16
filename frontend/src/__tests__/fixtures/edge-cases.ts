/**
 * Edge case fixtures for testing boundary conditions
 * Used to catch boundary condition issues early
 */

export const edgeCaseFixtures = {
  // Empty arrays
  emptyCollection: { characters: [], items: [], landmarks: [] },

  // Null optional fields
  nullOptionals: {
    image_url: null,
    description: null,
    updated_at: null,
  },

  // Empty strings
  emptyStrings: {
    player_name: '',
    image_url: '',
    description: '  ',
  },

  // Array boundaries
  emptyRoundHistory: { round_history: [] },
  singleRound: { round_history: [{ round: 1 }] },
  maxRounds: { round_history: Array(300).fill({}) },

  // Numeric boundaries
  zeroValues: { week: 0, age: 0, energy: 0 },
  negativeValues: { wealth: -100 },

  // Malformed data
  malformedDates: { created_at: 'invalid-date' },
  nestedNulls: { character_settings: { era: null } },
};

// Type definitions for edge case fixtures
export type EdgeCaseFixtures = typeof edgeCaseFixtures;
