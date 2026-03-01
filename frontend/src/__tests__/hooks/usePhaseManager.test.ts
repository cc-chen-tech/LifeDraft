/**
 * hooks/game/usePhaseManager.ts Tests
 * Tests for game phase management
 */
import { renderHook, act } from '@testing-library/react';

// Mock useUIStore
jest.mock('@/stores/useUIStore', () => ({
  useUIStore: jest.fn(() => ({
    setProcessing: jest.fn(),
    processingMessage: '',
  })),
}));

import { useUIStore } from '@/stores/useUIStore';
import { usePhaseManager, STATUS_MESSAGES, Phase } from '@/hooks/game/usePhaseManager';

describe('usePhaseManager', () => {
  const mockSetProcessing = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    (useUIStore as unknown as jest.Mock).mockReturnValue({
      setProcessing: mockSetProcessing,
      processingMessage: '',
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Initial state', () => {
    it('starts with loading phase', () => {
      const { result } = renderHook(() => usePhaseManager());

      expect(result.current.phase).toBe('loading');
      expect(result.current.phaseRef.current).toBe('loading');
    });

    it('starts with null connection status', () => {
      const { result } = renderHook(() => usePhaseManager());

      expect(result.current.connectionStatus).toBeNull();
    });

    it('starts with no reconnect attempt', () => {
      const { result } = renderHook(() => usePhaseManager());

      expect(result.current.reconnectAttempt).toBeNull();
    });

    it('starts with zero elapsed seconds', () => {
      const { result } = renderHook(() => usePhaseManager());

      expect(result.current.elapsedSeconds).toBe(0);
    });
  });

  describe('setPhase', () => {
    it('updates phase state', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      expect(result.current.phase).toBe('generating');
      expect(result.current.phaseRef.current).toBe('generating');
    });

    it('supports functional updates', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      act(() => {
        result.current.setPhase((prev) => prev === 'generating' ? 'options' : prev);
      });

      expect(result.current.phase).toBe('options');
    });

    it('handles all phase types', () => {
      const { result } = renderHook(() => usePhaseManager());
      const phases: Phase[] = ['loading', 'generating', 'options', 'choosing', 'result', 'summary', 'ending', 'error'];

      for (const phase of phases) {
        act(() => {
          result.current.setPhase(phase);
        });
        expect(result.current.phase).toBe(phase);
      }
    });
  });

  describe('Connection status', () => {
    it('updates connection status', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setConnectionStatus('connecting');
      });

      expect(result.current.connectionStatus).toBe('connecting');
    });

    it('handles all connection status types', () => {
      const { result } = renderHook(() => usePhaseManager());
      const statuses = ['connecting', 'connected', 'reconnecting', 'error', null] as const;

      for (const status of statuses) {
        act(() => {
          result.current.setConnectionStatus(status);
        });
        expect(result.current.connectionStatus).toBe(status);
      }
    });
  });

  describe('Reconnect attempt tracking', () => {
    it('sets reconnect attempt info', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setReconnectAttempt({ current: 2, max: 5 });
      });

      expect(result.current.reconnectAttempt).toEqual({ current: 2, max: 5 });
    });

    it('clears reconnect attempt', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setReconnectAttempt({ current: 1, max: 3 });
      });

      act(() => {
        result.current.setReconnectAttempt(null);
      });

      expect(result.current.reconnectAttempt).toBeNull();
    });
  });

  describe('Elapsed time timer', () => {
    it('starts timer in generating phase', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      act(() => {
        jest.advanceTimersByTime(3000);
      });

      expect(result.current.elapsedSeconds).toBe(3);
    });

    it('starts timer in choosing phase', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('choosing');
      });

      act(() => {
        jest.advanceTimersByTime(5000);
      });

      expect(result.current.elapsedSeconds).toBe(5);
    });

    it('stops timer in other phases', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      act(() => {
        result.current.setPhase('options');
      });

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      // Timer should have stopped
      expect(result.current.elapsedSeconds).toBe(0);
    });

    it('resets elapsed time on phase change', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      act(() => {
        jest.advanceTimersByTime(3000);
      });

      act(() => {
        result.current.setPhase('options');
      });

      expect(result.current.elapsedSeconds).toBe(0);
    });

    it('cleans up timer on unmount', () => {
      const { result, unmount } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      act(() => {
        jest.advanceTimersByTime(1000);
      });

      unmount();

      // Timer should be cleared without error
      act(() => {
        jest.advanceTimersByTime(1000);
      });
    });
  });

  describe('getLoadingMessage', () => {
    it('returns reconnecting message for generating phase', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
        result.current.setConnectionStatus('reconnecting');
      });

      expect(result.current.getLoadingMessage()).toBe('故事正在生成，请稍候...');
    });

    it('returns reconnecting message for choosing phase', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('choosing');
        result.current.setConnectionStatus('reconnecting');
      });

      expect(result.current.getLoadingMessage()).toBe('结果正在生成，请稍候...');
    });

    it('returns default reconnecting message for other phases', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('loading');
        result.current.setConnectionStatus('reconnecting');
      });

      expect(result.current.getLoadingMessage()).toBe('正在连接服务器...');
    });

    it('returns connecting message', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setConnectionStatus('connecting');
      });

      expect(result.current.getLoadingMessage()).toBe(STATUS_MESSAGES.connecting);
    });

    it('returns generating message', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      expect(result.current.getLoadingMessage()).toBe('正在构思剧情...');
    });

    it('returns choosing message', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('choosing');
      });

      expect(result.current.getLoadingMessage()).toBe('正在推演结果...');
    });

    it('uses processingMessage when available', () => {
      (useUIStore as unknown as jest.Mock).mockReturnValue({
        setProcessing: mockSetProcessing,
        processingMessage: 'generating_story',
      });

      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('generating');
      });

      expect(result.current.getLoadingMessage()).toBe(STATUS_MESSAGES.generating_story);
    });

    it('returns default message for other phases', () => {
      const { result } = renderHook(() => usePhaseManager());

      act(() => {
        result.current.setPhase('options');
      });

      expect(result.current.getLoadingMessage()).toBe('正在加载...');
    });
  });

  describe('STATUS_MESSAGES', () => {
    it('contains all expected status messages', () => {
      expect(STATUS_MESSAGES.preparing).toBe('正在准备...');
      expect(STATUS_MESSAGES.initializing).toBe('正在初始化...');
      expect(STATUS_MESSAGES.loading_context).toBe('正在加载上下文...');
      expect(STATUS_MESSAGES.building_world).toBe('正在构建世界...');
      expect(STATUS_MESSAGES.generating_story).toBe('正在生成故事...');
      expect(STATUS_MESSAGES.generating_options).toBe('正在生成选项...');
      expect(STATUS_MESSAGES.compressing).toBe('正在整理剧情...');
      expect(STATUS_MESSAGES.weekly_summary).toBe('正在生成周总结...');
      expect(STATUS_MESSAGES.processing).toBe('正在处理中...');
      expect(STATUS_MESSAGES.connecting).toBe('正在连接服务器...');
      expect(STATUS_MESSAGES.fallback).toBe('正在使用备用模式...');
      expect(STATUS_MESSAGES.replaying).toBe('正在恢复进度...');
      expect(STATUS_MESSAGES.waiting).toBe('等待服务器响应...');
      expect(STATUS_MESSAGES.retrying).toBe('故事逻辑校验中，正在优化...');
    });
  });
});
