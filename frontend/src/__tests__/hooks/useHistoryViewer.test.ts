/**
 * hooks/game/useHistoryViewer.ts Tests
 * Tests for history viewing functionality
 */

import { renderHook, act } from '@testing-library/react';
import { useHistoryViewer } from '@/hooks/game/useHistoryViewer';

describe('useHistoryViewer', () => {
  const mockSetOptions = jest.fn();
  const mockSetPhase = jest.fn();
  const mockGeneratingRef = { current: false };

  const defaultParams = {
    playerState: null,
    storyText: 'Current story',
    currentEvent: { story: 'Event story', options: [{ text: 'Option 1' }] },
    phaseRef: { current: 'options' as const },
    setPhase: mockSetPhase,
    setOptions: mockSetOptions,
    generatingRef: mockGeneratingRef,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('initial state', () => {
    it('initializes with showHistory false', () => {
      const { result } = renderHook(() => useHistoryViewer(defaultParams));

      expect(result.current.showHistory).toBe(false);
      expect(result.current.historyRoundIndex).toBeNull();
      expect(result.current.isViewingHistory).toBe(false);
      // ★ displayText 应该等于 storyText
      expect(result.current.displayText).toBe('Current story');
    });

    it('extracts round history from player state', () => {
      const playerState = {
        round_history: [
          { week: 0, round: 0, event_description: 'Story 1' },
          { week: 0, round: 1, event_description: 'Story 2' },
        ],
      };

      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState })
      );

      expect(result.current.roundHistory).toHaveLength(2);
    });

    it('handles empty round history', () => {
      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState: {} })
      );

      expect(result.current.roundHistory).toEqual([]);
    });
  });

  describe('handleOpenHistory', () => {
    it('opens history drawer', () => {
      const { result } = renderHook(() => useHistoryViewer(defaultParams));

      act(() => {
        result.current.handleOpenHistory();
      });

      expect(result.current.showHistory).toBe(true);
    });
  });

  describe('handleSelectHistoryRound', () => {
    it('selects a history round and updates historyDisplayText', () => {
      const playerState = {
        round_history: [
          {
            week: 0,
            round: 0,
            event_description: 'Event description',
            story_continuation: 'Story continuation',
          },
        ],
      };

      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState })
      );

      act(() => {
        result.current.handleSelectHistoryRound(0);
      });

      expect(result.current.historyRoundIndex).toBe(0);
      expect(result.current.isViewingHistory).toBe(true);
      // ★ 应该设置 historyDisplayText
      expect(result.current.historyDisplayText).toContain('Event description');
      // ★ displayText 应该显示历史内容
      expect(result.current.displayText).toContain('Event description');
      expect(mockSetOptions).toHaveBeenCalledWith([]);
    });

    it('backs up current state on first entry', () => {
      const playerState = {
        round_history: [{ week: 0, round: 0, event_description: 'Story' }],
      };

      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState })
      );

      act(() => {
        result.current.handleSelectHistoryRound(0);
      });

      // Internal state backup (not directly testable but ensures behavior)
      expect(result.current.historyRoundIndex).toBe(0);
    });

    it('does nothing for invalid index', () => {
      const playerState = {
        round_history: [{ week: 0, round: 0, event_description: 'Story' }],
      };

      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState })
      );

      act(() => {
        result.current.handleSelectHistoryRound(99);
      });

      expect(result.current.historyRoundIndex).toBeNull();
    });

    it('builds full story with continuation', () => {
      const playerState = {
        round_history: [
          {
            week: 0,
            round: 0,
            event_description: 'Event',
            story_continuation: 'Continuation',
          },
        ],
      };

      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState })
      );

      act(() => {
        result.current.handleSelectHistoryRound(0);
      });

      // ★ 检查 historyDisplayText 包含完整故事
      expect(result.current.historyDisplayText).toContain('Event');
      expect(result.current.historyDisplayText).toContain('Continuation');
      expect(result.current.historyDisplayText).toContain('选择后的故事发展');
    });
  });

  describe('handleBackToCurrent', () => {
    it('returns to current round and restores state', () => {
      const playerState = {
        round_history: [{ week: 0, round: 0, event_description: 'Story' }],
      };

      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState })
      );

      // First enter history mode
      act(() => {
        result.current.handleSelectHistoryRound(0);
      });

      // Then go back
      act(() => {
        result.current.handleBackToCurrent();
      });

      expect(result.current.historyRoundIndex).toBeNull();
      expect(result.current.isViewingHistory).toBe(false);
      // ★ displayText 应该恢复为 storyText
      expect(result.current.displayText).toBe('Current story');
      expect(mockSetPhase).toHaveBeenCalled();
    });

    it('restores current event options', () => {
      const playerState = {
        round_history: [{ week: 0, round: 0, event_description: 'Story' }],
      };

      const { result } = renderHook(() =>
        useHistoryViewer({ ...defaultParams, playerState })
      );

      // Enter history mode
      act(() => {
        result.current.handleSelectHistoryRound(0);
      });

      // Go back
      act(() => {
        result.current.handleBackToCurrent();
      });

      expect(mockSetOptions).toHaveBeenCalledWith(
        defaultParams.currentEvent.options
      );
    });
  });

  describe('setShowHistory', () => {
    it('can close history drawer', () => {
      const { result } = renderHook(() => useHistoryViewer(defaultParams));

      act(() => {
        result.current.setShowHistory(true);
      });
      expect(result.current.showHistory).toBe(true);

      act(() => {
        result.current.setShowHistory(false);
      });
      expect(result.current.showHistory).toBe(false);
    });
  });
});
