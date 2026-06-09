/**
 * remote-log Tests
 * Tests for the remote logging utility
 */

// Mock console.error to avoid noise in tests
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

// Now import
import { reportError, installGlobalErrorReporter } from '@/lib/remote-log';

describe('remote-log', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.sessionStorage.clear();
    // Suppress console.error during tests
    console.error = jest.fn();
    console.warn = jest.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
    console.warn = originalConsoleWarn;
  });

  describe('reportError', () => {
    it('logs error to console', () => {
      const testError = new Error('Test error');
      reportError(testError, { context: 'test' });

      expect(console.error).toHaveBeenCalledWith(
        '[Reported Error]',
        testError,
        { context: 'test' }
      );
    });

    it('works without context', () => {
      const testError = new Error('Test error without context');
      reportError(testError);

      expect(console.error).toHaveBeenCalledWith(
        '[Reported Error]',
        testError,
        undefined
      );
    });

    it('handles non-Error objects', () => {
      const fakeError = { message: 'Not a real error' } as unknown as Error;
      reportError(fakeError);

      expect(console.error).toHaveBeenCalled();
    });
  });

  describe('installGlobalErrorReporter', () => {
    it('installs error event listener', () => {
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener');

      installGlobalErrorReporter();

      expect(addEventListenerSpy).toHaveBeenCalledWith('error', expect.any(Function));
      expect(addEventListenerSpy).toHaveBeenCalledWith('unhandledrejection', expect.any(Function));

      addEventListenerSpy.mockRestore();
    });

    it('handles error events', () => {
      // Capture the handlers when they're registered
      let errorHandler: Function | undefined;
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener').mockImplementation(
        (type: string, listener: EventListenerOrEventListenerObject) => {
          if (type === 'error') {
            errorHandler = listener as Function;
          }
        }
      );

      installGlobalErrorReporter();
      addEventListenerSpy.mockRestore();

      if (errorHandler) {
        const mockEvent = {
          message: 'Test error',
          error: new Error('Test'),
          filename: 'test.js',
          lineno: 10,
          colno: 5,
        };
        errorHandler(mockEvent);

        expect(console.error).toHaveBeenCalledWith('[Global Error]', mockEvent.error);
      }
    });

    it('handles unhandledrejection events', () => {
      // Capture the handlers when they're registered
      let rejectionHandler: Function | undefined;
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener').mockImplementation(
        (type: string, listener: EventListenerOrEventListenerObject) => {
          if (type === 'unhandledrejection') {
            rejectionHandler = listener as Function;
          }
        }
      );

      installGlobalErrorReporter();
      addEventListenerSpy.mockRestore();

      if (rejectionHandler) {
        const mockEvent = {
          reason: new Error('Unhandled rejection'),
        };
        rejectionHandler(mockEvent);

        expect(console.error).toHaveBeenCalledWith('[Unhandled Rejection]', mockEvent.reason);
      }
    });

    it('reloads once when a stale Next script chunk fails to load', () => {
      let errorHandler: Function | undefined;
      const reload = jest.fn();
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener').mockImplementation(
        (type: string, listener: EventListenerOrEventListenerObject) => {
          if (type === 'error') {
            errorHandler = listener as Function;
          }
        }
      );

      installGlobalErrorReporter({ reload, now: () => 1000 });
      addEventListenerSpy.mockRestore();

      const script = document.createElement('script');
      script.src = 'https://story101.live/_next/static/chunks/old-build.js';
      const event = new Event('error');
      Object.defineProperty(event, 'target', { value: script });

      errorHandler?.(event);

      expect(reload).toHaveBeenCalledTimes(1);
      expect(window.sessionStorage.getItem('story101:stale-asset-reload-at')).toBe('1000');
    });

    it('does not reload repeatedly for stale asset errors in the cooldown window', () => {
      let errorHandler: Function | undefined;
      const reload = jest.fn();
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener').mockImplementation(
        (type: string, listener: EventListenerOrEventListenerObject) => {
          if (type === 'error') {
            errorHandler = listener as Function;
          }
        }
      );

      window.sessionStorage.setItem('story101:stale-asset-reload-at', '1000');
      installGlobalErrorReporter({ reload, now: () => 2000 });
      addEventListenerSpy.mockRestore();

      const link = document.createElement('link');
      link.href = 'https://story101.live/_next/static/chunks/old-build.css';
      const event = new Event('error');
      Object.defineProperty(event, 'target', { value: link });

      errorHandler?.(event);

      expect(reload).not.toHaveBeenCalled();
      expect(console.warn).toHaveBeenCalledWith(
        '[Stale Asset Recovery] Suppressed repeated reload for stale build asset',
        expect.any(Object)
      );
    });

    it('reloads once for unhandled ChunkLoadError rejections', () => {
      let rejectionHandler: Function | undefined;
      const reload = jest.fn();
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener').mockImplementation(
        (type: string, listener: EventListenerOrEventListenerObject) => {
          if (type === 'unhandledrejection') {
            rejectionHandler = listener as Function;
          }
        }
      );

      installGlobalErrorReporter({ reload, now: () => 70_000 });
      addEventListenerSpy.mockRestore();

      rejectionHandler?.({
        reason: new Error('ChunkLoadError: Loading chunk app/play failed.'),
      });

      expect(reload).toHaveBeenCalledTimes(1);
      expect(window.sessionStorage.getItem('story101:stale-asset-reload-at')).toBe('70000');
    });

    it('does not throw when window is undefined (SSR)', () => {
      const originalWindow = global.window;
      // @ts-expect-error - simulating SSR
      global.window = undefined;

      expect(() => installGlobalErrorReporter()).not.toThrow();

      global.window = originalWindow;
    });
  });
});
