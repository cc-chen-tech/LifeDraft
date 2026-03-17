/**
 * remote-log Tests
 * Tests for the remote logging utility
 */

// Mock console.error to avoid noise in tests
const originalConsoleError = console.error;

// Now import
import { reportError, installGlobalErrorReporter } from '@/lib/remote-log';

describe('remote-log', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Suppress console.error during tests
    console.error = jest.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
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

    it('does not throw when window is undefined (SSR)', () => {
      const originalWindow = global.window;
      // @ts-expect-error - simulating SSR
      global.window = undefined;

      expect(() => installGlobalErrorReporter()).not.toThrow();

      global.window = originalWindow;
    });
  });
});
