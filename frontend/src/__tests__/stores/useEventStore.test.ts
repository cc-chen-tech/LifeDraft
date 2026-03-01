/**
 * useEventStore Tests
 * Tests for the event store state management
 */
import { act } from '@testing-library/react';
import { useEventStore } from '@/stores/useEventStore';

// Mock API
jest.mock('@/lib/api', () => ({
  gameplay: {
    generateSummary: jest.fn().mockResolvedValue({
      summary_text: 'Test summary',
      start_week: 1,
      end_week: 4,
    }),
  },
}));

describe('useEventStore', () => {
  beforeEach(() => {
    act(() => {
      useEventStore.getState().clearCurrentEvent();
    });
  });

  describe('Initial state', () => {
    it('has correct initial values', () => {
      const state = useEventStore.getState();
      expect(state.currentEvent).toBeNull();
      expect(state.storyText).toBe('');
      expect(state.lastSummary).toBeNull();
    });
  });

  describe('Story text management', () => {
    it('sets story text', () => {
      act(() => {
        useEventStore.getState().setStoryText('Test story');
      });
      expect(useEventStore.getState().storyText).toBe('Test story');
    });

    it('appends story text', () => {
      act(() => {
        useEventStore.getState().setStoryText('Hello');
        useEventStore.getState().appendStoryText(' World');
      });
      expect(useEventStore.getState().storyText).toBe('Hello World');
    });

    it('clears story text', () => {
      act(() => {
        useEventStore.getState().setStoryText('Test');
        useEventStore.getState().setStoryText('');
      });
      expect(useEventStore.getState().storyText).toBe('');
    });

    it('does not update if text is same', () => {
      act(() => {
        useEventStore.getState().setStoryText('Test');
      });
      const prevLength = useEventStore.getState().storyText.length;
      act(() => {
        useEventStore.getState().setStoryText('Test');
      });
      expect(useEventStore.getState().storyText.length).toBe(prevLength);
    });
  });

  describe('Current event management', () => {
    it('sets current event', () => {
      const event = {
        story: 'Test story',
        options: [{ text: 'Option 1' }, { text: 'Option 2' }],
      };

      act(() => {
        useEventStore.getState().setCurrentEvent(event);
      });

      const state = useEventStore.getState();
      expect(state.currentEvent).toEqual(event);
    });

    it('clears current event', () => {
      act(() => {
        useEventStore.getState().setCurrentEvent({
          story: 'Test',
          options: [],
        });
        useEventStore.getState().clearCurrentEvent();
      });

      const state = useEventStore.getState();
      expect(state.currentEvent).toBeNull();
      expect(state.storyText).toBe('');
    });

    it('sets null event', () => {
      act(() => {
        useEventStore.getState().setCurrentEvent({
          story: 'Test',
          options: [],
        });
        useEventStore.getState().setCurrentEvent(null);
      });

      expect(useEventStore.getState().currentEvent).toBeNull();
    });

    it('preserves existing story text when setting event', () => {
      act(() => {
        useEventStore.getState().setStoryText('Existing story');
        useEventStore.getState().setCurrentEvent({
          story: 'New event story',
          options: [],
        });
      });

      // Should preserve existing story text
      expect(useEventStore.getState().storyText).toBe('Existing story');
    });
  });

  describe('Summary management', () => {
    it('clears summary', () => {
      act(() => {
        useEventStore.getState().clearSummary();
      });
      expect(useEventStore.getState().lastSummary).toBeNull();
    });
  });
});
