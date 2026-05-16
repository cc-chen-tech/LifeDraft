/**
 * SSE mock helper — creates a fake Response with a fake ReadableStream
 * so the real parseSSEStream code in @/lib/sse can run in tests.
 *
 * Usage:
 *   (global.fetch as jest.Mock).mockResolvedValue(
 *     createSSEMockResponse([
 *       'event: story\ndata: {"content":"hello"}\n\n',
 *       'event: complete\ndata: {"result":"ok"}\n\n',
 *     ])
 *   );
 *
 * Each chunk string is a complete SSE message. The TextDecoder API
 * (available in jsdom) will decode the Uint8Array into the string form
 * that parseSSEStream expects.
 */

export function createSSEMockResponse(chunks: string[]): Response {
  let index = 0;

  const reader: ReadableStreamDefaultReader<Uint8Array> = {
    read(): Promise<ReadableStreamReadResult<Uint8Array>> {
      if (index >= chunks.length) {
        return Promise.resolve({ done: true, value: undefined });
      }
      const value = new TextEncoder().encode(chunks[index]);
      index++;
      return Promise.resolve({ done: false, value });
    },
    cancel(): Promise<void> {
      return Promise.resolve();
    },
    releaseLock(): void {
      // no-op
    },
    get closed(): Promise<undefined> {
      return Promise.resolve(undefined);
    },
  };

  const body = {
    locked: false,
    cancel(): Promise<void> {
      return Promise.resolve();
    },
    getReader(): ReadableStreamDefaultReader<Uint8Array> {
      return reader;
    },
    pipeThrough: () => {
      return {} as ReadableStream<Uint8Array>;
    },
    pipeTo: () => Promise.resolve(),
    tee: () => [] as unknown as [ReadableStream<Uint8Array>, ReadableStream<Uint8Array>],
  } as unknown as ReadableStream<Uint8Array>;

  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'text/event-stream' }),
    body,
  } as Response;
}

/**
 * Create an error response (non-200) that causes SSE fetch functions
 * to throw. Useful for testing error handling paths.
 */
export function createSSEErrorResponse(status: number, detail?: string): Response {
  return {
    ok: false,
    status,
    statusText: detail || `HTTP error ${status}`,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: () => Promise.resolve({ detail: detail || 'error' }),
    text: () => Promise.resolve(JSON.stringify({ detail: detail || 'error' })),
    body: null,
  } as Response;
}
