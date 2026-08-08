/**
 * hooks/game/usePhaseManager.ts Tests
 * Tests for game phase management
 */
import { renderHook, act } from '@testing-library/react';
import { useUIStore } from '@/stores/useUIStore';
import { usePhaseManager, Phase } from '@/hooks/game/usePhaseManager';

function setupDefaultState() {
  useUIStore.setState({
    processingMessage: '',
  });
}

describe('usePhaseManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    setupDefaultState();
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

    it('starts with active narrative transport', () => {
      const { result } = renderHook(() => usePhaseManager());
      expect(result.current.transport).toBe('active');
    });
  });

  describe('setPhase', () => {
    it('updates phase state', () => {
      const { result } = renderHook(() => usePhaseManager());
      act(() => { result.current.setPhase('generating'); });
      expect(result.current.phase).toBe('generating');
      expect(result.current.phaseRef.current).toBe('generating');
    });

    it('supports functional updates', () => {
      const { result } = renderHook(() => usePhaseManager());
      act(() => { result.current.setPhase('generating'); });
      act(() => { result.current.setPhase((prev) => prev === 'generating' ? 'options' : prev); });
      expect(result.current.phase).toBe('options');
    });

    it('handles all phase types', () => {
      const { result } = renderHook(() => usePhaseManager());
      const phases: Phase[] = ['loading', 'generating', 'options', 'choosing', 'result', 'summary', 'ending', 'error'];
      for (const phase of phases) {
        act(() => { result.current.setPhase(phase); });
        expect(result.current.phase).toBe(phase);
      }
    });
  });

  describe('Connection status', () => {
    it('updates connection status', () => {
      const { result } = renderHook(() => usePhaseManager());
      act(() => { result.current.setConnectionStatus('connecting'); });
      expect(result.current.connectionStatus).toBe('connecting');
    });

    it('handles all connection status types', () => {
      const { result } = renderHook(() => usePhaseManager());
      const statuses = ['connecting', 'connected', 'reconnecting', 'error', null] as const;
      for (const status of statuses) {
        act(() => { result.current.setConnectionStatus(status); });
        expect(result.current.connectionStatus).toBe(status);
      }
    });
  });

  describe('Reconnect attempt tracking', () => {
    it('sets reconnect attempt info', () => {
      const { result } = renderHook(() => usePhaseManager());
      act(() => { result.current.setReconnectAttempt({ current: 2, max: 5 }); });
      expect(result.current.reconnectAttempt).toEqual({ current: 2, max: 5 });
    });

    it('clears reconnect attempt', () => {
      const { result } = renderHook(() => usePhaseManager());
      act(() => { result.current.setReconnectAttempt({ current: 1, max: 3 }); });
      act(() => { result.current.setReconnectAttempt(null); });
      expect(result.current.reconnectAttempt).toBeNull();
    });
  });

  describe('Narrative transport', () => {
    it('does not schedule a phase stopwatch or expose elapsed/copy APIs', () => {
      const intervalSpy = jest.spyOn(global, 'setInterval');
      const { result } = renderHook(() => usePhaseManager());

      act(() => { result.current.setPhase('generating'); });
      act(() => { result.current.setPhase('choosing'); });

      expect(intervalSpy).not.toHaveBeenCalled();
      expect(result.current).not.toHaveProperty('elapsedSeconds');
      expect(result.current).not.toHaveProperty('getLoadingMessage');
    });

    it.each(['active', 'reconnecting', 'polling', 'failed'] as const)(
      'reports %s transport directly',
      (transport) => {
        const { result } = renderHook(() => usePhaseManager());
        act(() => { result.current.setTransport(transport); });
        expect(result.current.transport).toBe(transport);
      },
    );
  });
});
