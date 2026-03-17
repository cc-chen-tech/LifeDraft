/**
 * lib/sse.ts Tests
 * Tests for SSE streaming functions
 */

// Polyfill for Jest environment
import { ReadableStream } from 'stream/web';
import { TextEncoder, TextDecoder } from 'util';
global.ReadableStream = ReadableStream as unknown as typeof globalThis.ReadableStream;
global.TextEncoder = TextEncoder as unknown as typeof globalThis.TextEncoder;
global.TextDecoder = TextDecoder as unknown as typeof globalThis.TextDecoder;

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock navigator
Object.defineProperty(window, 'navigator', {
  value: {
    onLine: true,
  },
  writable: true,
});

// Mock remote-log
jest.mock('@/lib/remote-log', () => ({
  reportError: jest.fn(),
}));

import {
  streamGameEvent,
  streamChoice,
  streamCustomChoice,
  streamOpeningStory,
  streamRegenerate,
  streamRewrite,
  StreamCallbacks,
} from '@/lib/sse';

// Helper to create a mock ReadableStream
function createMockStream(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(new TextEncoder().encode(chunk));
      }
      controller.close();
    },
  });
}

describe('SSE Streaming', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    (window.navigator as { onLine: boolean }).onLine = true;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('streamGameEvent', () => {
    it('calls fetch with correct URL and credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      const callbacks: StreamCallbacks = {};
      await streamGameEvent(123, callbacks);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/games/123/event'),
        expect.objectContaining({
          credentials: 'include',
        })
      );
    });

    it('handles chunk events', async () => {
      const onChunk = jest.fn();
      const callbacks: StreamCallbacks = { onChunk };

      const sseData = 'data: {"content":"Hello World"}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamGameEvent(123, callbacks);

      expect(onChunk).toHaveBeenCalledWith('Hello World');
    });

    it('handles text field in data', async () => {
      const onChunk = jest.fn();
      const callbacks: StreamCallbacks = { onChunk };

      const sseData = 'data: {"text":"Story text"}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamGameEvent(123, callbacks);

      expect(onChunk).toHaveBeenCalledWith('Story text');
    });

    it('handles complete events', async () => {
      const onComplete = jest.fn();
      const callbacks: StreamCallbacks = { onComplete };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      await streamGameEvent(123, callbacks);

      expect(onComplete).toHaveBeenCalledWith({});
    });

    it('throws on HTTP errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Server Error'),
      });

      const callbacks: StreamCallbacks = {};

      await expect(streamGameEvent(123, callbacks)).rejects.toThrow('HTTP error! status: 500');
    });

    it('throws on network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network failed'));

      const callbacks: StreamCallbacks = {};

      await expect(streamGameEvent(123, callbacks)).rejects.toThrow('Network failed');
    });
  });

  describe('streamChoice', () => {
    it('calls fetch with POST method and correct body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      const callbacks: StreamCallbacks = {};
      await streamChoice(123, 0, callbacks);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/games/123/choice'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('option_index'),
          credentials: 'include',
        })
      );
    });

    it('includes choice index in request body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      const callbacks: StreamCallbacks = {};
      await streamChoice(123, 2, callbacks);

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.option_index).toBe(2);
    });
  });

  describe('streamCustomChoice', () => {
    it('calls fetch with POST method and custom text', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      const callbacks: StreamCallbacks = {};
      await streamCustomChoice(123, 'My custom action', callbacks);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/games/123/custom-choice'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        })
      );

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.custom_text).toBe('My custom action');
    });
  });

  describe('streamOpeningStory', () => {
    it('calls fetch with POST and character settings', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      const callbacks: StreamCallbacks = {};
      await streamOpeningStory(
        { era: 'modern', age: 25 },
        'TestPlayer',
        'My vision',
        'zh',
        callbacks
      );

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/character/opening-story'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        })
      );

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.player_name).toBe('TestPlayer');
      expect(body.life_vision).toBe('My vision');
      expect(body.character_settings).toEqual({ era: 'modern', age: 25 });
    });
  });

  describe('streamRegenerate', () => {
    it('calls fetch with correct URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      const callbacks: StreamCallbacks = {};
      await streamRegenerate(123, callbacks);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/games/123/regenerate-stream'),
        expect.objectContaining({
          credentials: 'include',
        })
      );
    });

    it('handles chunk events', async () => {
      const onChunk = jest.fn();
      const callbacks: StreamCallbacks = { onChunk };

      const sseData = 'data: {"content":"Regenerated story"}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamRegenerate(123, callbacks);

      expect(onChunk).toHaveBeenCalledWith('Regenerated story');
    });
  });

  describe('streamRewrite', () => {
    it('calls fetch with POST and parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream(['data: [DONE]\n\n']),
      });

      const callbacks = {
        onStory: jest.fn(),
        onStatus: jest.fn(),
        onComplete: jest.fn(),
      };
      await streamRewrite(123, 'story context', 'instruction', 'segment', 'zh', callbacks);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/games/123/rewrite-stream'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        })
      );

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.full_story).toBe('story context');
      expect(body.user_instruction).toBe('instruction');
      expect(body.segment_to_replace).toBe('segment');
      expect(body.language).toBe('zh');
    });

    it('handles rewrite events with story chunks', async () => {
      const onStory = jest.fn();
      const callbacks = { onStory, onStatus: jest.fn(), onComplete: jest.fn() };

      const sseData = 'data: {"type":"story_chunk","content":"Rewritten story"}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamRewrite(123, 'context', 'instruction', 'segment', 'zh', callbacks);

      expect(onStory).toHaveBeenCalledWith('Rewritten story');
    });

    it('handles rewrite status events', async () => {
      const onStatus = jest.fn();
      const callbacks = { onStory: jest.fn(), onStatus, onComplete: jest.fn() };

      const sseData = 'data: {"type":"status","status":{"phase":"rewriting"}}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamRewrite(123, 'context', 'instruction', 'segment', 'zh', callbacks);

      expect(onStatus).toHaveBeenCalledWith({ phase: 'rewriting' });
    });

    it('handles HTTP errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Server Error'),
      });

      const callbacks = {
        onStory: jest.fn(),
        onStatus: jest.fn(),
        onComplete: jest.fn(),
      };

      await expect(streamRewrite(123, 'context', 'instruction', 'segment', 'zh', callbacks)).rejects.toThrow('HTTP error');
    });
  });

  describe('Stream parsing edge cases', () => {
    it('handles multiple events in single chunk', async () => {
      const onChunk = jest.fn();
      const callbacks: StreamCallbacks = { onChunk };

      const sseData = 'data: {"content":"First"}\n\ndata: {"content":"Second"}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamGameEvent(123, callbacks);

      expect(onChunk).toHaveBeenCalledTimes(2);
      expect(onChunk).toHaveBeenNthCalledWith(1, 'First');
      expect(onChunk).toHaveBeenNthCalledWith(2, 'Second');
    });

    it('handles events split across chunks', async () => {
      const onChunk = jest.fn();
      const callbacks: StreamCallbacks = { onChunk };

      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('data: {"con'));
          controller.enqueue(new TextEncoder().encode('tent":"Test"}\n\n'));
          controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'));
          controller.close();
        },
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: stream,
      });

      await streamGameEvent(123, callbacks);

      expect(onChunk).toHaveBeenCalledWith('Test');
    });

    it('handles malformed JSON as plain text', async () => {
      const onChunk = jest.fn();
      const callbacks: StreamCallbacks = { onChunk };

      // When JSON parsing fails, the code treats the data as plain text
      const sseData = 'data: {invalid json}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamGameEvent(123, callbacks);

      // Should treat invalid JSON as plain text
      expect(onChunk).toHaveBeenCalledWith('{invalid json}');
    });

    it('throws when no response body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      });

      await expect(streamGameEvent(123, {})).rejects.toThrow('No response body');
    });

    it('handles chunk field in data', async () => {
      const onChunk = jest.fn();
      const callbacks: StreamCallbacks = { onChunk };

      const sseData = 'data: {"chunk":"Chunk data"}\n\n';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([sseData, 'data: [DONE]\n\n']),
      });

      await streamGameEvent(123, callbacks);

      expect(onChunk).toHaveBeenCalledWith('Chunk data');
    });
  });

  describe('Error handling', () => {
    it('throws on 401 unauthorized', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: () => Promise.resolve('Unauthorized'),
      });

      await expect(streamGameEvent(123, {})).rejects.toThrow('HTTP error! status: 401');
    });

    it('throws on 404 not found', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        text: () => Promise.resolve('Not Found'),
      });

      await expect(streamGameEvent(123, {})).rejects.toThrow('HTTP error! status: 404');
    });

    it('throws on abort signal', async () => {
      const controller = new AbortController();
      controller.abort();

      // The fetch will throw AbortError when aborted
      const abortError = new Error('The operation was aborted');
      abortError.name = 'AbortError';
      mockFetch.mockRejectedValueOnce(abortError);

      await expect(streamGameEvent(123, {}, controller.signal)).rejects.toThrow('The operation was aborted');
    });
  });
});
