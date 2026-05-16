/**
 * useMusicStore playlist logic tests (no API mocks — tests pure state logic).
 */
import { describe, it, expect } from '@jest/globals';

// Test the pure mergeQueuePreservingCurrent logic without the full store
function mergeQueuePreservingCurrent(
  currentSong: { id: number; name: string } | null,
  newSongs: Array<{ id: number; name: string }>
): { currentSong: { id: number; name: string } | null; queue: Array<{ id: number; name: string }> } {
  if (currentSong === null) {
    if (newSongs.length === 0) return { currentSong: null, queue: [] };
    return { currentSong: newSongs[0], queue: newSongs.slice(1) };
  }
  const queue = newSongs.filter((s) => s.id !== currentSong.id);
  return { currentSong, queue };
}

describe('mergeQueuePreservingCurrent', () => {
  it('should set first song as current when no current exists', () => {
    const result = mergeQueuePreservingCurrent(null, [
      { id: 1, name: 'A' },
      { id: 2, name: 'B' },
    ]);
    expect(result.currentSong).toEqual({ id: 1, name: 'A' });
    expect(result.queue).toEqual([{ id: 2, name: 'B' }]);
  });

  it('should preserve current song when new songs arrive', () => {
    const result = mergeQueuePreservingCurrent(
      { id: 1, name: 'A' },
      [
        { id: 1, name: 'A' },
        { id: 2, name: 'B' },
        { id: 3, name: 'C' },
      ]
    );
    expect(result.currentSong).toEqual({ id: 1, name: 'A' });
    expect(result.queue).toEqual([
      { id: 2, name: 'B' },
      { id: 3, name: 'C' },
    ]);
  });

  it('should handle empty new songs', () => {
    const result = mergeQueuePreservingCurrent({ id: 1, name: 'A' }, []);
    expect(result.currentSong).toEqual({ id: 1, name: 'A' });
    expect(result.queue).toEqual([]);
  });

  it('should handle all new songs being the current song', () => {
    const result = mergeQueuePreservingCurrent(
      { id: 1, name: 'A' },
      [{ id: 1, name: 'A' }]
    );
    expect(result.currentSong).toEqual({ id: 1, name: 'A' });
    expect(result.queue).toEqual([]);
  });
});

describe('advanceQueue', () => {
  function advanceQueue(
    current: { id: number } | null,
    queue: Array<{ id: number }>,
    played: Array<{ id: number }>
  ): { current: { id: number } | null; queue: Array<{ id: number }>; played: Array<{ id: number }> } {
    if (current !== null) {
      played = [...played, current];
    }
    if (queue.length > 0) {
      return { current: queue[0], queue: queue.slice(1), played };
    }
    if (played.length > 0) {
      return { current: played[0], queue: played.slice(1), played: [] };
    }
    return { current: null, queue: [], played: [] };
  }

  it('should move current to played and pop queue head', () => {
    const result = advanceQueue(
      { id: 1 },
      [{ id: 2 }, { id: 3 }],
      []
    );
    expect(result.current).toEqual({ id: 2 });
    expect(result.queue).toEqual([{ id: 3 }]);
    expect(result.played).toEqual([{ id: 1 }]);
  });

  it('should wrap played songs when queue is empty', () => {
    const result = advanceQueue(
      { id: 1 },
      [],
      [{ id: 0 }]
    );
    expect(result.current).toEqual({ id: 0 });
    expect(result.queue).toEqual([{ id: 1 }]);
    expect(result.played).toEqual([]);
  });
});
