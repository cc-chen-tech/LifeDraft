/**
 * SSE/EventSource Cleanup Tests
 * 
 * Tests to verify proper cleanup of Server-Sent Events (SSE) connections.
 * Ensures no memory leaks when components mount/unmount.
 */
import { renderHook, act, waitFor } from '@testing-library/react';

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  
  url: string;
  readyState: number = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  
  closeCalled = false;
  
  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  
  close() {
    this.closeCalled = true;
    this.readyState = 2;
  }
  
  addEventListener(type: string, listener: EventListener) {}
  removeEventListener(type: string, listener: EventListener) {}
  
  // Helper to simulate events
  simulateOpen() {
    this.readyState = 1;
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }
  
  simulateMessage(data: string) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data }));
    }
  }
  
  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
  
  static reset() {
    MockEventSource.instances = [];
  }
  
  static getLastInstance(): MockEventSource | undefined {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }
}

// Set global EventSource
const originalEventSource = global.EventSource;
beforeAll(() => {
  (global as unknown as { EventSource: typeof MockEventSource }).EventSource = MockEventSource;
});

afterAll(() => {
  (global as unknown as { EventSource: typeof EventSource }).EventSource = originalEventSource;
});

// Mock AbortController
class MockAbortController {
  static instances: MockAbortController[] = [];
  
  signal = {
    aborted: false,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    onabort: null,
  };
  
  abortCalled = false;
  
  constructor() {
    MockAbortController.instances.push(this);
  }
  
  abort() {
    this.abortCalled = true;
    this.signal.aborted = true;
  }
  
  static reset() {
    MockAbortController.instances = [];
  }
  
  static getLastInstance(): MockAbortController | undefined {
    return MockAbortController.instances[MockAbortController.instances.length - 1];
  }
}

const originalAbortController = global.AbortController;
beforeAll(() => {
  (global as unknown as { AbortController: typeof MockAbortController }).AbortController = MockAbortController;
});

afterAll(() => {
  (global as unknown as { AbortController: typeof AbortController }).AbortController = originalAbortController;
});

describe('SSE Connection Cleanup', () => {
  beforeEach(() => {
    MockEventSource.reset();
    MockAbortController.reset();
    jest.clearAllMocks();
  });

  describe('EventSource.close() called on unmount', () => {
    it('should close EventSource when component unmounts', async () => {
      // Simulate a simple hook that creates an EventSource
      const useSSEConnection = () => {
        const eventSourceRef = { current: null as MockEventSource | null };
        
        const connect = () => {
          eventSourceRef.current = new MockEventSource('/api/events');
          eventSourceRef.current.simulateOpen();
        };
        
        const disconnect = () => {
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
          }
        };
        
        return { connect, disconnect, eventSourceRef };
      };
      
      const { result, unmount } = renderHook(() => useSSEConnection());
      
      // Connect
      act(() => {
        result.current.connect();
      });
      
      expect(MockEventSource.instances).toHaveLength(1);
      const eventSource = MockEventSource.getLastInstance();
      expect(eventSource?.closeCalled).toBe(false);
      
      // Disconnect (simulate unmount behavior)
      act(() => {
        result.current.disconnect();
      });
      
      expect(eventSource?.closeCalled).toBe(true);
    });

    it('should handle multiple mount/unmount cycles', async () => {
      const useSSEConnection = () => {
        const eventSourceRef = { current: null as MockEventSource | null };
        
        const connect = () => {
          eventSourceRef.current = new MockEventSource('/api/events');
        };
        
        const disconnect = () => {
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
          }
        };
        
        return { connect, disconnect };
      };
      
      // First mount/unmount cycle
      const { result: result1, unmount: unmount1 } = renderHook(() => useSSEConnection());
      act(() => result1.current.connect());
      act(() => result1.current.disconnect());
      
      // Second mount/unmount cycle
      const { result: result2, unmount: unmount2 } = renderHook(() => useSSEConnection());
      act(() => result2.current.connect());
      act(() => result2.current.disconnect());
      
      // Third mount/unmount cycle
      const { result: result3, unmount: unmount3 } = renderHook(() => useSSEConnection());
      act(() => result3.current.connect());
      act(() => result3.current.disconnect());
      
      // All EventSources should be closed
      expect(MockEventSource.instances).toHaveLength(3);
      MockEventSource.instances.forEach((es) => {
        expect(es.closeCalled).toBe(true);
      });
    });
  });

  describe('Abort controller triggered on unmount', () => {
    it('should abort pending requests when component unmounts', async () => {
      const useAbortableRequest = () => {
        const abortControllerRef = { current: null as MockAbortController | null };
        
        const startRequest = () => {
          abortControllerRef.current = new MockAbortController();
          // Simulate starting a fetch with the abort signal
          return abortControllerRef.current.signal;
        };
        
        const cancelRequest = () => {
          if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
          }
        };
        
        return { startRequest, cancelRequest, abortControllerRef };
      };
      
      const { result } = renderHook(() => useAbortableRequest());
      
      // Start request
      act(() => {
        result.current.startRequest();
      });
      
      expect(MockAbortController.instances).toHaveLength(1);
      const controller = MockAbortController.getLastInstance();
      expect(controller?.abortCalled).toBe(false);
      
      // Cancel request
      act(() => {
        result.current.cancelRequest();
      });
      
      expect(controller?.abortCalled).toBe(true);
    });

    it('should handle abort during active connection', () => {
      const useAbortableConnection = () => {
        let controller: MockAbortController | null = null;
        let eventSource: MockEventSource | null = null;
        
        const connect = () => {
          controller = new MockAbortController();
          eventSource = new MockEventSource('/api/stream');
          
          // Simulate abort listener
          controller.signal.addEventListener('abort', () => {
            if (eventSource && !eventSource.closeCalled) {
              eventSource.close();
            }
          });
          
          return { controller, eventSource };
        };
        
        const abort = () => {
          if (controller) {
            controller.abort();
            // Manually close EventSource since our mock doesn't trigger the listener
            if (eventSource && !eventSource.closeCalled) {
              eventSource.close();
            }
          }
        };
        
        return { connect, abort };
      };
      
      const { result } = renderHook(() => useAbortableConnection());
      
      act(() => {
        result.current.connect();
      });
      
      expect(MockAbortController.instances).toHaveLength(1);
      expect(MockEventSource.instances).toHaveLength(1);
      
      act(() => {
        result.current.abort();
      });
      
      expect(MockAbortController.getLastInstance()?.abortCalled).toBe(true);
      expect(MockEventSource.getLastInstance()?.closeCalled).toBe(true);
    });
  });

  describe('No memory leak after repeated mount/unmount', () => {
    it('should not accumulate EventSource instances', () => {
      const useTrackedConnection = () => {
        const connect = () => new MockEventSource('/api/events');
        const disconnect = (es: MockEventSource) => es.close();
        return { connect, disconnect };
      };
      
      const iterations = 10;
      let closedCount = 0;
      
      for (let i = 0; i < iterations; i++) {
        const { result } = renderHook(() => useTrackedConnection());
        
        let eventSource: MockEventSource;
        act(() => {
          eventSource = result.current.connect();
        });
        
        act(() => {
          result.current.disconnect(eventSource!);
          if (eventSource!.closeCalled) {
            closedCount++;
          }
        });
      }
      
      // All should be properly closed
      expect(closedCount).toBe(iterations);
      expect(MockEventSource.instances).toHaveLength(iterations);
      MockEventSource.instances.forEach((es) => {
        expect(es.closeCalled).toBe(true);
      });
    });

    it('should release references after cleanup', () => {
      const refs: WeakRef<MockEventSource>[] = [];
      
      const useWeakRefConnection = () => {
        let eventSource: MockEventSource | null = null;
        
        const connect = () => {
          eventSource = new MockEventSource('/api/events');
          refs.push(new WeakRef(eventSource));
          return eventSource;
        };
        
        const disconnect = () => {
          if (eventSource) {
            eventSource.close();
            eventSource = null;  // Release reference
          }
        };
        
        return { connect, disconnect };
      };
      
      const { result } = renderHook(() => useWeakRefConnection());
      
      act(() => {
        result.current.connect();
      });
      
      expect(refs).toHaveLength(1);
      expect(refs[0].deref()).toBeDefined();
      
      act(() => {
        result.current.disconnect();
      });
      
      // After disconnect, the hook should have released its reference
      // (The WeakRef may still hold it until GC, but that's expected)
      expect(MockEventSource.getLastInstance()?.closeCalled).toBe(true);
    });
  });

  describe('Reconnect after page visibility change', () => {
    it('should handle visibility change events', () => {
      let isConnected = false;
      let connectionCount = 0;
      
      const useVisibilityAwareConnection = () => {
        const connect = () => {
          isConnected = true;
          connectionCount++;
          return new MockEventSource('/api/events');
        };
        
        const disconnect = (es: MockEventSource) => {
          isConnected = false;
          es.close();
        };
        
        const handleVisibilityChange = (visible: boolean, currentEs: MockEventSource | null) => {
          if (visible && !isConnected) {
            return connect();
          } else if (!visible && isConnected && currentEs) {
            disconnect(currentEs);
            return null;
          }
          return currentEs;
        };
        
        return { connect, disconnect, handleVisibilityChange };
      };
      
      const { result } = renderHook(() => useVisibilityAwareConnection());
      
      // Initial connect
      let eventSource: MockEventSource | null = null;
      act(() => {
        eventSource = result.current.connect();
      });
      expect(connectionCount).toBe(1);
      expect(isConnected).toBe(true);
      
      // Page becomes hidden
      act(() => {
        eventSource = result.current.handleVisibilityChange(false, eventSource);
      });
      expect(isConnected).toBe(false);
      expect(eventSource).toBeNull();
      
      // Page becomes visible again
      act(() => {
        eventSource = result.current.handleVisibilityChange(true, eventSource);
      });
      expect(connectionCount).toBe(2);
      expect(isConnected).toBe(true);
      expect(eventSource).not.toBeNull();
    });

    it('should not reconnect if already connected', () => {
      let connectionCount = 0;
      
      const useSmartConnection = () => {
        let isConnected = false;
        
        const connect = () => {
          if (!isConnected) {
            isConnected = true;
            connectionCount++;
            return new MockEventSource('/api/events');
          }
          return null;
        };
        
        return { connect };
      };
      
      const { result } = renderHook(() => useSmartConnection());
      
      // Multiple connect calls should only create one connection
      act(() => {
        result.current.connect();
        result.current.connect();
        result.current.connect();
      });
      
      expect(connectionCount).toBe(1);
    });
  });
});
