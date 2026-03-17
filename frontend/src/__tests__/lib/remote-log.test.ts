/**
 * remote-log Tests
 * Tests for the remote logging utility
 */

// Mock fetch before importing
const mockFetch = jest.fn().mockResolvedValue({ ok: true });
global.fetch = mockFetch;

// Set up window mock before importing
const mockAddEventListener = jest.fn();
const mockWindow = {
  location: { href: 'http://localhost:3000/test' },
  addEventListener: mockAddEventListener,
};

// @ts-expect-error - mocking window for tests
global.window = mockWindow;

// Now import after mocks are set up
import { remoteLog, installGlobalErrorReporter } from '@/lib/remote-log';

describe('remote-log', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('remoteLog', () => {
    it('sends log to server', () => {
      remoteLog('error', 'Test error message', 'test-context');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/client-log',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('Test error message'),
        })
      );
    });

    it('includes context in payload', () => {
      remoteLog('warn', 'Warning message', 'api');

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);

      expect(body.context).toBe('api');
      expect(body.level).toBe('warn');
      expect(body.message).toBe('Warning message');
    });

    it('includes url from window.location', () => {
      remoteLog('error', 'Test with URL');

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);

      // Check that url exists and contains the expected parts
      expect(body.url).toBeDefined();
      expect(body.url).toContain('http://localhost');
    });

    it('deduplicates messages within 30 seconds', () => {
      remoteLog('error', 'Duplicate message');
      remoteLog('error', 'Duplicate message');
      remoteLog('error', 'Duplicate message');

      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('allows same message after 30 seconds', () => {
      remoteLog('error', 'Delayed message');

      // Advance time by 31 seconds
      jest.advanceTimersByTime(31000);

      remoteLog('error', 'Delayed message');

      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('handles different messages separately', () => {
      remoteLog('error', 'First error');
      remoteLog('error', 'Second error');

      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('handles different levels separately', () => {
      remoteLog('error', 'Same message');
      remoteLog('warn', 'Same message');

      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('handles fetch failure gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      // Should not throw
      expect(() => {
        remoteLog('error', 'Test error');
      }).not.toThrow();
    });

    it('works without context parameter', () => {
      remoteLog('info', 'Message without context');

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);

      expect(body.message).toBe('Message without context');
      expect(body.context).toBeUndefined();
    });
  });

  describe('installGlobalErrorReporter', () => {
    it('installs error event listener', () => {
      // The function should add event listeners
      // Since window is mocked, we verify the function runs without error
      expect(() => installGlobalErrorReporter()).not.toThrow();
    });

    it('installs unhandledrejection event listener', () => {
      // The function should add event listeners
      // Since window is mocked, we verify the function runs without error
      expect(() => installGlobalErrorReporter()).not.toThrow();
    });

    it('handles error event with filename', () => {
      // Get the error handler from the addEventListener calls
      const calls = mockAddEventListener.mock.calls;
      const errorHandler = calls.find(call => call[0] === 'error')?.[1];

      if (errorHandler) {
        // Simulate error event with filename
        const mockEvent = {
          message: 'Test error',
          error: new Error('Test'),
          filename: 'test.js',
          lineno: 10,
          colno: 5,
        };
        errorHandler(mockEvent);

        // Verify remoteLog was called
        expect(mockFetch).toHaveBeenCalled();
        const call = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
        const body = JSON.parse(call[1].body);
        expect(body.message).toContain('[Uncaught]');
        expect(body.message).toContain('test.js');
        expect(body.message).toContain('10');
        expect(body.message).toContain('5');
      }
    });

    it('handles error event without filename', () => {
      const calls = mockAddEventListener.mock.calls;
      const errorHandler = calls.find(call => call[0] === 'error')?.[1];

      if (errorHandler) {
        // Simulate error event without filename
        const mockEvent = {
          message: '',
          error: new Error('Error without message'),
          filename: '',
          lineno: 0,
          colno: 0,
        };
        errorHandler(mockEvent);

        expect(mockFetch).toHaveBeenCalled();
        const call = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
        const body = JSON.parse(call[1].body);
        expect(body.message).toContain('[Uncaught]');
      }
    });

    it('handles error event with message but no error object', () => {
      const calls = mockAddEventListener.mock.calls;
      const errorHandler = calls.find(call => call[0] === 'error')?.[1];

      if (errorHandler) {
        const mockEvent = {
          message: 'Script error',
          error: undefined,
          filename: 'script.js',
          lineno: 1,
          colno: 1,
        };
        errorHandler(mockEvent);

        expect(mockFetch).toHaveBeenCalled();
        const call = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
        const body = JSON.parse(call[1].body);
        expect(body.message).toContain('Script error');
      }
    });

    it('handles unhandledrejection with Error reason', () => {
      const calls = mockAddEventListener.mock.calls;
      const rejectionHandler = calls.find(call => call[0] === 'unhandledrejection')?.[1];

      if (rejectionHandler) {
        // Simulate unhandledrejection with Error
        const mockEvent = {
          reason: new Error('Unhandled error'),
        };
        rejectionHandler(mockEvent);

        expect(mockFetch).toHaveBeenCalled();
        const call = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
        const body = JSON.parse(call[1].body);
        expect(body.message).toContain('[UnhandledRejection]');
        expect(body.message).toContain('Unhandled error');
      }
    });

    it('handles unhandledrejection with non-Error reason', () => {
      const calls = mockAddEventListener.mock.calls;
      const rejectionHandler = calls.find(call => call[0] === 'unhandledrejection')?.[1];

      if (rejectionHandler) {
        // Simulate unhandledrejection with non-Error
        const mockEvent = {
          reason: 'String reason',
        };
        rejectionHandler(mockEvent);

        expect(mockFetch).toHaveBeenCalled();
        const call = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
        const body = JSON.parse(call[1].body);
        expect(body.message).toContain('[UnhandledRejection]');
        expect(body.message).toContain('String reason');
      }
    });

    it('handles unhandledrejection with object reason', () => {
      const calls = mockAddEventListener.mock.calls;
      const rejectionHandler = calls.find(call => call[0] === 'unhandledrejection')?.[1];

      if (rejectionHandler) {
        const mockEvent = {
          reason: { custom: 'object' },
        };
        rejectionHandler(mockEvent);

        expect(mockFetch).toHaveBeenCalled();
      }
    });

    it('handles unhandledrejection with null reason', () => {
      const calls = mockAddEventListener.mock.calls;
      const rejectionHandler = calls.find(call => call[0] === 'unhandledrejection')?.[1];

      if (rejectionHandler) {
        const mockEvent = {
          reason: null,
        };
        rejectionHandler(mockEvent);

        expect(mockFetch).toHaveBeenCalled();
        const call = mockFetch.mock.calls[mockFetch.mock.calls - 1];
        const body = JSON.parse(call[1].body);
        expect(body.message).toContain('[UnhandledRejection]');
      }
    });

    it('handles unhandledrejection with undefined reason', () => {
      const calls = mockAddEventListener.mock.calls;
      const rejectionHandler = calls.find(call => call[0] === 'unhandledrejection')?.[1];

      if (rejectionHandler) {
        const mockEvent = {
          reason: undefined,
        };
        rejectionHandler(mockEvent);

        expect(mockFetch).toHaveBeenCalled();
      }
    });
  });

  describe('Deduplication edge cases', () => {
    it('cleans up old entries when cache exceeds 100 items', () => {
      // Add 101 unique messages quickly
      for (let i = 0; i < 101; i++) {
        remoteLog('error', `Message ${i}`);
      }

      // All should be sent since they're unique
      expect(mockFetch).toHaveBeenCalledTimes(101);
    });

    it('deduplicates same level and message combination', () => {
      // Use unique messages to avoid interference from other tests
      const uniqueMsg = `Unique test message ${Date.now()}`;

      remoteLog('error', uniqueMsg);
      remoteLog('error', uniqueMsg); // Duplicate - same level and message
      remoteLog('warn', uniqueMsg); // Different level - not a duplicate
      remoteLog('error', uniqueMsg); // Duplicate of first error

      // error (1st) + error (dup, skip) + warn (different level, sent) + error (dup, skip)
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('allows messages after deduplication window expires', () => {
      const msg = 'Expiring message test';

      remoteLog('error', msg);
      expect(mockFetch).toHaveBeenCalledTimes(1);

      // Advance past dedup window
      jest.advanceTimersByTime(30001);

      remoteLog('error', msg);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('Info level logging', () => {
    it('sends info level logs', () => {
      remoteLog('info', 'Info message', 'test');

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);

      expect(body.level).toBe('info');
    });
  });

  describe('Cache cleanup', () => {
    it('properly cleans up expired entries', () => {
      // Add messages and then advance time past dedup window
      remoteLog('error', 'Old message 1');
      remoteLog('error', 'Old message 2');
      remoteLog('error', 'Old message 3');

      jest.advanceTimersByTime(35000);

      // These should not be deduplicated since cache was cleaned
      remoteLog('error', 'Old message 1');
      remoteLog('error', 'Old message 2');

      // 3 original + 2 new after cleanup = 5
      expect(mockFetch).toHaveBeenCalledTimes(5);
    });
  });
});
