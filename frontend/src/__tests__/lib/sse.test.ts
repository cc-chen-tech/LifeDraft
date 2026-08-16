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

    it('commits numeric SSE ids after delivering their story chunks', async () => {
      const onEventId = jest.fn();
      const onStory = jest.fn();
      const callbacks: StreamCallbacks = { onEventId, onStory };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'id: 4\nevent: story\ndata: "后续片段"\n\n',
          'event: complete\ndata: {"event_description":"完成","options":[{"text":"继续"}]}\n\n',
        ]),
      });

      await streamGameEvent(3, callbacks);

      expect(onEventId).toHaveBeenCalledWith(4);
      expect(onStory.mock.invocationCallOrder[0]).toBeLessThan(
        onEventId.mock.invocationCallOrder[0]
      );
      expect(onStory).toHaveBeenCalledWith('后续片段');
    });

    it('does not leak a status frame id into the next event', async () => {
      const onEventId = jest.fn();
      const callbacks: StreamCallbacks = { onEventId };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'id: 7\nevent: status\ndata: {"phase":"validating"}\n\n',
          'event: story\ndata: "正文"\n\n',
          'data: [DONE]\n\n',
        ]),
      });

      await streamGameEvent(3, callbacks);

      expect(onEventId).not.toHaveBeenCalled();
    });

    it.each([
      ['heartbeat status', 'event: status\ndata: {"phase":"generating_story","heartbeat":true}\n\n', 'status'],
      ['ordinary status', 'event: status\ndata: {"phase":"validating"}\n\n', 'status'],
      ['story chunk', 'event: story\ndata: "新正文"\n\n', 'story'],
      ['complete frame', 'event: complete\ndata: {"event_description":"完成","options":[{"text":"继续"}]}\n\n', 'complete'],
      ['error frame', 'event: error\ndata: {"message":"generation failed"}\n\n', 'error'],
    ] as const)('reports one real SSE activity for %s', async (_name, frame, expectedKind) => {
      const onActivity = jest.fn();
      const callbacks = { onActivity } as StreamCallbacks & {
        onActivity: (kind: 'status' | 'story' | 'complete' | 'error') => void;
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([frame]),
      });

      const stream = streamGameEvent(123, callbacks);
      if (expectedKind === 'status' || expectedKind === 'story') {
        await expect(stream).rejects.toThrow('Stream ended without complete event');
      } else {
        await stream;
      }

      expect(onActivity).toHaveBeenCalledTimes(1);
      expect(onActivity).toHaveBeenCalledWith(expectedKind);
    });

    it('sends Last-Event-ID only for a resume request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: complete\ndata: {"event_description":"完成","options":[{"text":"继续"}]}\n\n',
        ]),
      });

      await streamGameEvent(3, {}, { lastEventId: 7 });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/games/3/event',
        expect.objectContaining({ headers: { 'Last-Event-ID': '7' } })
      );
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

    it('does not emit empty complete after an error event', async () => {
      const onComplete = jest.fn();
      const onError = jest.fn();
      const callbacks: StreamCallbacks = { onComplete, onError };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: error\ndata: {"message":"Timeout waiting for event generation"}\n\n',
        ]),
      });

      await streamGameEvent(123, callbacks);

      expect(onError).toHaveBeenCalledWith({ message: 'Timeout waiting for event generation' });
      expect(onComplete).not.toHaveBeenCalled();
    });

    it('preserves structured generation failure fields', async () => {
      const onError = jest.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: error\ndata: {"error":"故事角色一致性检查连续未通过","code":"REQUIRED_CAST_MISSING","summary":"故事角色一致性检查连续未通过","detail":"当天需要登场的人物没有出现。","retryable":true,"attempts_used":3,"quality_level":"expert","operation_id":"op-123"}\n\n',
        ]),
      });

      await streamGameEvent(123, { onError });

      expect(onError).toHaveBeenCalledWith({
        message: '故事角色一致性检查连续未通过',
        error: '故事角色一致性检查连续未通过',
        code: 'REQUIRED_CAST_MISSING',
        summary: '故事角色一致性检查连续未通过',
        detail: '当天需要登场的人物没有出现。',
        retryable: true,
        attempts_used: 3,
        quality_level: 'expert',
        operation_id: 'op-123',
      });
    });

    it('does not emit empty complete when an error event is followed by DONE', async () => {
      const onComplete = jest.fn();
      const onError = jest.fn();
      const callbacks: StreamCallbacks = { onComplete, onError };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: error\ndata: {"message":"Timeout waiting for event generation"}\n\n',
          'data: [DONE]\n\n',
        ]),
      });

      await streamGameEvent(123, callbacks);

      expect(onError).toHaveBeenCalledWith({ message: 'Timeout waiting for event generation' });
      expect(onComplete).not.toHaveBeenCalled();
    });

    it('treats an error frame as terminal when buffered complete and story frames follow it', async () => {
      const onStory = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: error\ndata: {"message":"generation failed"}\n\n',
          'event: story\ndata: "buffered stale story"\n\n',
          'event: complete\ndata: {"event_description":"buffered stale complete","options":[{"text":"stale"}]}\n\n',
        ]),
      });

      await streamGameEvent(123, { onStory, onComplete, onError });

      expect(onError).toHaveBeenCalledTimes(1);
      expect(onStory).not.toHaveBeenCalled();
      expect(onComplete).not.toHaveBeenCalled();
    });

    it('settles and cancels an open body immediately after one error frame', async () => {
      jest.useRealTimers();
      const onStory = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();
      const cancelBody = jest.fn();
      let closeProducer!: () => void;
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          closeProducer = () => controller.close();
          controller.enqueue(new TextEncoder().encode(
            'event: error\ndata: {"message":"generation failed"}\n\n',
          ));
        },
        cancel() {
          cancelBody();
        },
      });
      mockFetch.mockResolvedValueOnce({ ok: true, body });

      const stream = streamGameEvent(123, { onStory, onComplete, onError });
      const settledBeforeProducerClose = await Promise.race([
        stream.then(() => true),
        new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 100)),
      ]);
      if (!settledBeforeProducerClose) closeProducer();
      await stream;

      expect(settledBeforeProducerClose).toBe(true);
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onError).toHaveBeenCalledWith({ message: 'generation failed' });
      expect(cancelBody).toHaveBeenCalledTimes(1);
      expect(onStory).not.toHaveBeenCalled();
      expect(onComplete).not.toHaveBeenCalled();
    });

    it('ignores buffered story frames after a complete frame', async () => {
      const onStory = jest.fn();
      const onComplete = jest.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: complete\ndata: {"event_description":"complete story","options":[{"text":"next"}]}\n\n',
          'event: story\ndata: "buffered stale story"\n\n',
          'data: [DONE]\n\n',
        ]),
      });

      await streamGameEvent(123, { onStory, onComplete });

      expect(onStory).not.toHaveBeenCalled();
      expect(onComplete).toHaveBeenCalledTimes(1);
      expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({
        event_description: 'complete story',
      }));
    });

    it('commits and resolves as soon as a complete frame arrives even if the body stays open', async () => {
      const onComplete = jest.fn();
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(
            'event: complete\ndata: {"event_description":"complete now","options":[{"text":"next"}]}\n\n',
          ));
        },
      });
      mockFetch.mockResolvedValueOnce({ ok: true, body });

      const stream = streamGameEvent(123, { onComplete });
      const completedBeforeClose = await Promise.race([
        stream.then(() => true),
        new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 100)),
      ]);
      await stream;

      expect(completedBeforeClose).toBe(true);
      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it('keeps collected stream chunks and fails with missing complete event', async () => {
      const onChunk = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();
      const callbacks: StreamCallbacks = { onChunk, onComplete, onError };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'data: {"content":"这是部分故事"}\n\n',
        ]),
      });

      await expect(streamGameEvent(123, callbacks)).rejects.toThrow('Stream ended without complete event');

      expect(onChunk).toHaveBeenCalledWith('这是部分故事');
      expect(onError).toHaveBeenCalledWith(expect.objectContaining({
        message: 'Stream ended without complete event',
      }));
      expect(onComplete).not.toHaveBeenCalled();
    });

    it('throws on client HTTP errors without retrying', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        text: () => Promise.resolve('Bad Request'),
      });

      const callbacks: StreamCallbacks = {};

      await expect(streamGameEvent(123, callbacks)).rejects.toThrow('HTTP error! status: 400');
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('throws on network errors after retrying transient failures', async () => {
      mockFetch
        .mockRejectedValueOnce(new Error('Network failed'))
        .mockRejectedValueOnce(new Error('Network failed'))
        .mockRejectedValueOnce(new Error('Network failed'));

      const callbacks: StreamCallbacks = {};

      const promise = streamGameEvent(123, callbacks);
      const rejection = expect(promise).rejects.toThrow('Network failed');
      await Promise.resolve();
      await jest.advanceTimersByTimeAsync(1000);
      await Promise.resolve();
      await jest.advanceTimersByTimeAsync(2000);

      await rejection;
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });

    it('retries transient 5xx responses before parsing event stream', async () => {
      const onChunk = jest.fn();
      const onReconnecting = jest.fn();
      const callbacks: StreamCallbacks = { onChunk, onReconnecting };

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 502,
          text: () => Promise.resolve('Bad Gateway'),
        })
        .mockResolvedValueOnce({
          ok: true,
          body: createMockStream([
            'data: {"content":"Recovered event"}\n\n',
            'data: [DONE]\n\n',
          ]),
        });

      const promise = streamGameEvent(123, callbacks);
      await Promise.resolve();
      await jest.advanceTimersByTimeAsync(1000);
      await promise;

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onReconnecting).toHaveBeenCalledWith(1, 3);
      expect(onChunk).toHaveBeenCalledWith('Recovered event');
    });
  });

  describe('streamChoice', () => {
    it.each([
      ['normal choice', () => streamChoice(123, 0, {})],
      ['custom choice', () => streamCustomChoice(123, 'wait', {})],
    ])('never retries the mutating POST transport for %s', async (_name, start) => {
      mockFetch.mockRejectedValue(new Error('network failed after request dispatch'));

      const rejection = expect(start()).rejects.toThrow('network failed after request dispatch');
      await Promise.resolve();
      await jest.advanceTimersByTimeAsync(3_000);
      await rejection;

      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

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
        body: createMockStream([
          'event: story\n',
          'data: "开场故事。"\n\n',
          'event: complete\n',
          'data: {}\n\n',
        ]),
      });

      const callbacks = {
        onStory: jest.fn(),
        onComplete: jest.fn(),
        onError: jest.fn(),
      };
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

    it('rejects when opening story completes without any story text', async () => {
      const onStory = jest.fn();
      const onComplete = jest.fn();
      const onError = jest.fn();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: complete\n',
          'data: {}\n\n',
        ]),
      });

      await expect(
        streamOpeningStory(
          { era: 'modern' },
          '林舟',
          '找到自己的路',
          'zh',
          { onStory, onComplete, onError }
        )
      ).rejects.toThrow('Opening story stream completed without story text');

      expect(onStory).not.toHaveBeenCalled();
      expect(onComplete).not.toHaveBeenCalled();
      expect(onError).toHaveBeenCalledWith({
        message: 'Opening story stream completed without story text',
      });
    });

    it('streams backend event: story chunks and preserves text when complete payload is empty', async () => {
      const onStory = jest.fn();
      const onComplete = jest.fn();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: story\n',
          'data: "雨停以后，林舟推开窗。"\n\n',
          'event: story\n',
          'data: {"content":"街口的灯还亮着。"}\n\n',
          'event: complete\n',
          'data: {}\n\n',
        ]),
      });

      await streamOpeningStory(
        { era: 'modern' },
        '林舟',
        '找到自己的路',
        'zh',
        { onStory, onComplete }
      );

      expect(onStory).toHaveBeenNthCalledWith(1, '雨停以后，林舟推开窗。');
      expect(onStory).toHaveBeenNthCalledWith(2, '街口的灯还亮着。');
      expect(onComplete).toHaveBeenCalledWith({});
    });
  });

  describe('streamRegenerate', () => {
    it('sends Last-Event-ID when resuming the same regeneration transaction', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockStream([
          'event: complete\ndata: {"event_description":"完成","options":[{"text":"继续"}]}\n\n',
        ]),
      });

      await streamRegenerate(9, {}, { lastEventId: 12 });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/games/9/regenerate-stream',
        expect.objectContaining({ headers: { 'Last-Event-ID': '12' } })
      );
    });

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

    it('retries transient 5xx responses before parsing regenerated stream', async () => {
      const onChunk = jest.fn();
      const onReconnecting = jest.fn();
      const callbacks: StreamCallbacks = { onChunk, onReconnecting };

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 504,
          text: () => Promise.resolve('Gateway Timeout'),
        })
        .mockResolvedValueOnce({
          ok: true,
          body: createMockStream([
            'data: {"content":"Recovered regeneration"}\n\n',
            'data: [DONE]\n\n',
          ]),
        });

      const promise = streamRegenerate(123, callbacks);
      await Promise.resolve();
      await jest.advanceTimersByTimeAsync(1000);
      await promise;

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onReconnecting).toHaveBeenCalledWith(1, 3);
      expect(onChunk).toHaveBeenCalledWith('Recovered regeneration');
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
        status: 400,
        text: () => Promise.resolve('Bad Request'),
      });

      const callbacks = {
        onStory: jest.fn(),
        onStatus: jest.fn(),
        onComplete: jest.fn(),
      };

      await expect(streamRewrite(123, 'context', 'instruction', 'segment', 'zh', callbacks)).rejects.toThrow('HTTP error');
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('retries transient 5xx responses before parsing rewrite stream', async () => {
      const onStory = jest.fn();
      const callbacks = { onStory, onStatus: jest.fn(), onComplete: jest.fn() };

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 502,
          text: () => Promise.resolve('Bad Gateway'),
        })
        .mockResolvedValueOnce({
          ok: true,
          body: createMockStream([
            'data: {"type":"story_chunk","content":"Recovered rewrite"}\n\n',
            'data: [DONE]\n\n',
          ]),
        });

      const promise = streamRewrite(123, 'context', 'instruction', 'segment', 'zh', callbacks);
      await Promise.resolve();
      await jest.advanceTimersByTimeAsync(1000);
      await promise;

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onStory).toHaveBeenCalledWith('Recovered rewrite');
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

      await expect(streamGameEvent(123, {}, { signal: controller.signal })).rejects.toThrow('The operation was aborted');
    });
  });
});
