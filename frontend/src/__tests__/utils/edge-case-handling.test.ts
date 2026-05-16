/**
 * Edge case handling tests
 * Tests boundary conditions and error handling
 */

import { edgeCaseFixtures } from '../fixtures/edge-cases';

describe('Edge Case Handling', () => {
  describe('Empty Array Access Protection', () => {
    it('handles empty collection arrays safely', () => {
      const { emptyCollection } = edgeCaseFixtures;

      expect(emptyCollection.characters).toHaveLength(0);
      expect(emptyCollection.items).toHaveLength(0);
      expect(emptyCollection.landmarks).toHaveLength(0);

      // Ensure safe access patterns work
      const firstCharacter = emptyCollection.characters[0];
      expect(firstCharacter).toBeUndefined();

      // Safe iteration
      let count = 0;
      emptyCollection.characters.forEach(() => count++);
      expect(count).toBe(0);
    });

    it('handles empty round_history without crashing', () => {
      const { emptyRoundHistory } = edgeCaseFixtures;

      expect(emptyRoundHistory.round_history).toHaveLength(0);
      expect(emptyRoundHistory.round_history[0]).toBeUndefined();

      // Common operations on empty arrays
      const hasHistory = emptyRoundHistory.round_history.length > 0;
      expect(hasHistory).toBe(false);

      const lastRound = emptyRoundHistory.round_history[emptyRoundHistory.round_history.length - 1];
      expect(lastRound).toBeUndefined();
    });

    it('handles single item arrays correctly', () => {
      const { singleRound } = edgeCaseFixtures;

      expect(singleRound.round_history).toHaveLength(1);
      expect(singleRound.round_history[0]).toEqual({ round: 1 });

      const first = singleRound.round_history[0];
      expect(first?.round).toBe(1);
    });

    it('handles large arrays efficiently', () => {
      const { maxRounds } = edgeCaseFixtures;

      expect(maxRounds.round_history).toHaveLength(300);

      // Access at boundaries
      expect(maxRounds.round_history[0]).toEqual({});
      expect(maxRounds.round_history[299]).toEqual({});
      expect(maxRounds.round_history[300]).toBeUndefined();
    });
  });

  describe('Null/undefined/Empty String Consistency', () => {
    it('treats null optional fields as falsy', () => {
      const { nullOptionals } = edgeCaseFixtures;

      expect(nullOptionals.image_url).toBeNull();
      expect(nullOptionals.description).toBeNull();
      expect(nullOptionals.updated_at).toBeNull();

      // Falsy checks
      expect(!nullOptionals.image_url).toBe(true);
      expect(!nullOptionals.description).toBe(true);
      expect(!nullOptionals.updated_at).toBe(true);
    });

    it('treats empty strings as falsy', () => {
      const { emptyStrings } = edgeCaseFixtures;

      expect(emptyStrings.player_name).toBe('');
      expect(emptyStrings.image_url).toBe('');

      // Falsy checks
      expect(!emptyStrings.player_name).toBe(true);
      expect(!emptyStrings.image_url).toBe(true);
    });

    it('handles whitespace-only strings appropriately', () => {
      const { emptyStrings } = edgeCaseFixtures;

      // Whitespace string is truthy in boolean context
      expect(!!emptyStrings.description).toBe(true);
      // But should be trimmed for validation
      expect(emptyStrings.description.trim()).toBe('');
    });

    it('distinguishes between null, undefined, and empty string', () => {
      const values = {
        null: null,
        undefined: undefined,
        empty: '',
        whitespace: '  ',
      };

      // Strict equality checks
      expect(values.null).toBeNull();
      expect(values.undefined).toBeUndefined();
      expect(values.empty).toBe('');

      // Type checks
      expect(typeof values.null).toBe('object');
      expect(typeof values.undefined).toBe('undefined');
      expect(typeof values.empty).toBe('string');
    });
  });

  describe('Numeric Boundaries', () => {
    it('handles zero values correctly', () => {
      const { zeroValues } = edgeCaseFixtures;

      expect(zeroValues.week).toBe(0);
      expect(zeroValues.age).toBe(0);
      expect(zeroValues.energy).toBe(0);

      // Zero is falsy but valid
      expect(!zeroValues.week).toBe(true);
      expect(zeroValues.week === 0).toBe(true);
    });

    it('handles negative values appropriately', () => {
      const { negativeValues } = edgeCaseFixtures;

      expect(negativeValues.wealth).toBe(-100);
      expect(negativeValues.wealth < 0).toBe(true);
    });

    it('validates numeric ranges', () => {
      const testValue = (value: number, min: number, max: number) => {
        return value >= min && value <= max;
      };

      expect(testValue(0, 0, 100)).toBe(true);
      expect(testValue(-1, 0, 100)).toBe(false);
      expect(testValue(101, 0, 100)).toBe(false);
    });
  });

  describe('Date Parse Error Handling', () => {
    it('handles malformed dates gracefully', () => {
      const { malformedDates } = edgeCaseFixtures;

      const date = new Date(malformedDates.created_at);
      // Invalid date should result in NaN
      expect(isNaN(date.getTime())).toBe(true);
    });

    it('returns null or default for invalid dates', () => {
      const parseDate = (value: string | null | undefined): Date | null => {
        if (!value) return null;
        const date = new Date(value);
        return isNaN(date.getTime()) ? null : date;
      };

      expect(parseDate('invalid-date')).toBeNull();
      expect(parseDate(null)).toBeNull();
      expect(parseDate(undefined)).toBeNull();
      expect(parseDate('2024-01-15')).not.toBeNull();
    });

    it('formats dates safely with fallback', () => {
      const formatDate = (value: string | null | undefined, fallback = '未知时间'): string => {
        if (!value) return fallback;
        const date = new Date(value);
        return isNaN(date.getTime()) ? fallback : date.toISOString();
      };

      expect(formatDate('invalid-date')).toBe('未知时间');
      expect(formatDate(null)).toBe('未知时间');
      expect(formatDate('2024-01-15T00:00:00Z')).toBe('2024-01-15T00:00:00.000Z');
    });
  });

  describe('Nested Object Access Protection', () => {
    it('handles nested null values safely', () => {
      const { nestedNulls } = edgeCaseFixtures;

      expect(nestedNulls.character_settings).toBeDefined();
      expect(nestedNulls.character_settings.era).toBeNull();
    });

    it('uses optional chaining for safe access', () => {
      const data = {
        settings: {
          theme: null as string | null,
          nested: {
            value: 'test',
          },
        },
      };

      // Safe access patterns
      expect(data.settings?.theme).toBeNull();
      expect(data.settings?.nested?.value).toBe('test');
    });

    it('provides defaults for missing nested values', () => {
      const getNestedValue = (
        obj: Record<string, unknown>,
        path: string,
        defaultValue: unknown = null
      ): unknown => {
        const keys = path.split('.');
        let current: unknown = obj;

        for (const key of keys) {
          if (current === null || current === undefined) {
            return defaultValue;
          }
          current = (current as Record<string, unknown>)[key];
        }

        return current !== undefined ? current : defaultValue;
      };

      const data = { a: { b: { c: 'value' } } };

      expect(getNestedValue(data, 'a.b.c')).toBe('value');
      expect(getNestedValue(data, 'a.b.d', 'default')).toBe('default');
      expect(getNestedValue(data, 'x.y.z', 'default')).toBe('default');
    });
  });

  describe('Image URL Edge Cases', () => {
    it('treats empty string image_url as falsy', () => {
      const { emptyStrings } = edgeCaseFixtures;

      const hasImage = !!emptyStrings.image_url;
      expect(hasImage).toBe(false);
    });

    it('treats null image_url as falsy', () => {
      const { nullOptionals } = edgeCaseFixtures;

      const hasImage = !!nullOptionals.image_url;
      expect(hasImage).toBe(false);
    });

    it('validates image URL format', () => {
      const isValidImageUrl = (url: string | null | undefined): boolean => {
        if (!url || url.trim() === '') return false;
        // Basic URL validation
        try {
          new URL(url);
          return true;
        } catch {
          return false;
        }
      };

      expect(isValidImageUrl('')).toBe(false);
      expect(isValidImageUrl(null)).toBe(false);
      expect(isValidImageUrl(undefined)).toBe(false);
      expect(isValidImageUrl('  ')).toBe(false);
      expect(isValidImageUrl('https://example.com/image.png')).toBe(true);
      expect(isValidImageUrl('/local/path.png')).toBe(false); // Relative paths fail URL constructor
    });
  });

  describe('Collection Operations', () => {
    it('safely accesses first and last elements', () => {
      const safeFirst = <T>(arr: T[] | undefined | null): T | null => {
        return arr && arr.length > 0 ? arr[0] : null;
      };

      const safeLast = <T>(arr: T[] | undefined | null): T | null => {
        return arr && arr.length > 0 ? arr[arr.length - 1] : null;
      };

      expect(safeFirst([])).toBeNull();
      expect(safeFirst(null)).toBeNull();
      expect(safeFirst(undefined)).toBeNull();
      expect(safeFirst([1, 2, 3])).toBe(1);

      expect(safeLast([])).toBeNull();
      expect(safeLast([1, 2, 3])).toBe(3);
    });

    it('handles pagination boundaries', () => {
      const items = Array(25).fill(null).map((_, i) => ({ id: i + 1 }));
      const pageSize = 10;

      const getPage = <T>(arr: T[], page: number, size: number): T[] => {
        const start = (page - 1) * size;
        if (start >= arr.length) return [];
        return arr.slice(start, start + size);
      };

      // Page 1
      expect(getPage(items, 1, pageSize)).toHaveLength(10);
      // Page 3 (partial)
      expect(getPage(items, 3, pageSize)).toHaveLength(5);
      // Page 4 (empty)
      expect(getPage(items, 4, pageSize)).toHaveLength(0);
    });
  });
});
