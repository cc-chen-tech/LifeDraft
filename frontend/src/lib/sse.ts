/**
 * Server-Sent Events (SSE) streaming utilities
 */

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "error" | null;
export type StreamActivityKind = "status" | "story" | "complete" | "error";

export interface GenerationFailurePayload {
  message: string;
  error?: string;
  code?: string;
  summary?: string;
  detail?: string;
  retryable?: boolean;
  attempts_used?: number;
  quality_level?: string;
  operation_id?: string;
}

export interface StreamStatusPayload {
  phase: string;
  heartbeat?: boolean;
  cached_count?: number;
  message?: string;
  attempt?: number;
  max_attempts?: number;
  quality_level?: string;
}

export interface StreamCallbacks {
  onStory?: (text: string) => void;
  onChunk?: (chunk: string) => void;
  onEventId?: (eventId: number) => void;
  onStatus?: (status: StreamStatusPayload) => void;
  onComplete?: (data: Record<string, unknown>) => void;
  onError?: (error: Error | GenerationFailurePayload) => void;
  onConnectionStatus?: (status: ConnectionStatus) => void;
  onReconnecting?: (attempt: number, maxRetries: number) => void;
  onActivity?: (kind: StreamActivityKind) => void;
}

function parseSSEStream(reader: ReadableStreamDefaultReader<Uint8Array>, callbacks: StreamCallbacks): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';
  let currentEventType: string | null = null;
  let completeData: Record<string, unknown> | null = null;
  let isCompleteReceived = false;
  let isErrorReceived = false;
  let isResolved = false;
  let pendingEventId: number | null = null;
  let completeActivityEmitted = false;
  let errorActivityEmitted = false;

  const emitCompleteActivity = () => {
    if (completeActivityEmitted) return;
    completeActivityEmitted = true;
    callbacks.onActivity?.("complete");
  };

  const emitErrorActivity = () => {
    if (errorActivityEmitted) return;
    errorActivityEmitted = true;
    callbacks.onActivity?.("error");
  };

  return new Promise((resolve, reject) => {
    function safeResolve() {
      if (!isResolved) {
        isResolved = true;
        resolve();
      }
    }

    function pump(): Promise<void> {
      return reader!.read().then(({ done, value }) => {
        if (done) {
          // Stream ended - use the last complete event data if received
          console.log('[SSE] Stream ended, isCompleteReceived:', isCompleteReceived, 'completeData keys:', Object.keys(completeData || {}));
          if (isErrorReceived) {
            safeResolve();
          } else if (isCompleteReceived && completeData) {
            callbacks.onComplete?.(completeData);
          } else if (!isCompleteReceived) {
            const error = new Error('Stream ended without complete event');
            callbacks.onError?.(error);
            reject(error);
            return;
          }
          safeResolve();
          return;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('id: ')) {
            const eventId = Number.parseInt(trimmed.slice(4), 10);
            pendingEventId = Number.isFinite(eventId) ? eventId : null;
            continue;
          }
          // Parse event type from event: line
          if (trimmed.startsWith('event: ')) {
            currentEventType = trimmed.slice(7);
            continue;
          }
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              // [DONE] marker - resolve with any stored complete data
              if (!isResolved) {
                if (isErrorReceived) {
                  safeResolve();
                  return;
                }
                emitCompleteActivity();
                if (completeData) {
                  callbacks.onComplete?.(completeData);
                } else {
                  callbacks.onComplete?.({});
                }
                safeResolve();
              }
              return;
            }
            if (isErrorReceived || isCompleteReceived) {
              currentEventType = null;
              pendingEventId = null;
              continue;
            }
            let parsed: unknown;
            try {
              parsed = JSON.parse(data);
            } catch {
              // If not JSON, treat as plain text chunk (for story)
              if (data && currentEventType !== 'complete') {
                callbacks.onActivity?.("story");
                callbacks.onChunk?.(data);
                callbacks.onStory?.(data);
              }
              parsed = undefined;
            }

            if (parsed !== undefined) {
              const parsedRecord = parsed !== null && typeof parsed === 'object'
                ? parsed as Record<string, unknown>
                : null;
              // Handle complete event (either from event: line or type field in data)
              if (
                currentEventType === 'complete' ||
                parsedRecord?.type === 'complete' ||
                parsedRecord?.event === 'complete'
              ) {
                const completePayload = parsedRecord?.data ?? parsed;
                const parsedComplete = completePayload !== null && typeof completePayload === 'object'
                  ? completePayload as Record<string, unknown>
                  : {};
                completeData = parsedComplete;
                isCompleteReceived = true;
                emitCompleteActivity();
                console.log('[SSE] Complete event received, data keys:', Object.keys(completeData || {}));
                currentEventType = null;
                // Callback failures are transport failures, not JSON parse failures.
                callbacks.onComplete?.(parsedComplete);
                safeResolve();
                void reader.cancel().catch(() => undefined);
                return;
              }

              // ★ Handle error events from backend
              if (
                currentEventType === 'error' ||
                parsedRecord?.type === 'error' ||
                parsedRecord?.event === 'error'
              ) {
                const rawError = parsedRecord?.summary ?? parsedRecord?.error ?? parsedRecord?.message;
                const errorMsg = typeof rawError === 'string' ? rawError : 'Unknown server error';
                console.error('[SSE] Error event received:', errorMsg);
                isErrorReceived = true;
                emitErrorActivity();
                callbacks.onError?.(
                  parsedRecord
                    ? { ...parsedRecord, message: errorMsg } as GenerationFailurePayload
                    : { message: errorMsg }
                );
                currentEventType = null;
                pendingEventId = null;
                void reader.cancel().catch(() => undefined);
                safeResolve();
                return;
              }

              // Handle status updates (support both formats: {type: "status", status: {...}} and {phase: "..."})
              if (currentEventType === 'status' || parsedRecord?.type === 'status') {
                const rawStatus = parsedRecord?.status ?? parsedRecord;
                const statusData = rawStatus !== null && typeof rawStatus === 'object'
                  ? rawStatus as StreamStatusPayload
                  : { phase: '' };
                callbacks.onActivity?.("status");
                callbacks.onStatus?.(statusData);
                currentEventType = null;
                // P-修复：status 事件也会消费掉前面 id: 行的 event id，
                // 必须在此重置，否则下一个 data 行会带出陈旧 id 污染重连游标。
                pendingEventId = null;
                continue;
              }

              // Handle story chunks
              // 如果是字符串，直接使用；如果是对象，尝试提取内容字段
              const chunk = typeof parsed === 'string'
                ? parsed
                : [
                    parsedRecord?.content,
                    parsedRecord?.text,
                    parsedRecord?.chunk,
                    parsedRecord?.story,
                  ].find((value): value is string => typeof value === 'string');
              if (chunk) {
                callbacks.onActivity?.("story");
                callbacks.onChunk?.(chunk);
                callbacks.onStory?.(chunk);
              }
            }
            if (pendingEventId !== null) {
              callbacks.onEventId?.(pendingEventId);
              pendingEventId = null;
            }
            // Reset event type after processing data line
            currentEventType = null;
          }
        }

        return pump();
      }).catch((error) => {
        callbacks.onError?.(error);
        reject(error);
      });
    }

    pump();
  });
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    throw new DOMException('The operation was aborted.', 'AbortError');
  }

  await new Promise<void>((resolve, reject) => {
    const timeoutId = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timeoutId);
        reject(new DOMException('The operation was aborted.', 'AbortError'));
      },
      { once: true }
    );
  });
}

function shouldRetrySSEResponse(status: number): boolean {
  return status === 502 || status === 504 || status >= 500;
}

async function fetchSSEWithRetry(
  input: RequestInfo | URL,
  init: RequestInit,
  callbacks: StreamCallbacks,
  maxRetries = 3
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    if (init.signal?.aborted) {
      throw new DOMException('The operation was aborted.', 'AbortError');
    }

    try {
      const response = await fetch(input, init);
      if (response.ok || !shouldRetrySSEResponse(response.status) || attempt === maxRetries - 1) {
        return response;
      }

      lastError = new Error(`HTTP error! status: ${response.status}`);
      callbacks.onConnectionStatus?.('reconnecting');
      callbacks.onReconnecting?.(attempt + 1, maxRetries);
    } catch (error) {
      if (init.signal?.aborted || (error instanceof Error && error.name === 'AbortError')) {
        throw error;
      }

      lastError = error instanceof Error ? error : new Error(String(error));
      if (attempt === maxRetries - 1) {
        throw lastError;
      }

      callbacks.onConnectionStatus?.('reconnecting');
      callbacks.onReconnecting?.(attempt + 1, maxRetries);
    }

    await sleep(Math.pow(2, attempt) * 1000, init.signal || undefined);
  }

  throw lastError || new Error('SSE retry exhausted');
}

export async function streamChoice(
  gameId: number,
  choiceIndex: number,
  callbacks: StreamCallbacks,
  options?: { signal?: AbortSignal; eventId?: string; revision?: number }
): Promise<void> {
  const response = await fetchSSEWithRetry(`/api/games/${gameId}/choice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      option_index: choiceIndex,
      event_id: options?.eventId,
      revision: options?.revision,
    }),
    signal: options?.signal,
  }, callbacks, 1);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  return parseSSEStream(reader, callbacks);
}

export async function streamCustomChoice(
  gameId: number,
  customChoice: string,
  callbacks: StreamCallbacks,
  options?: { signal?: AbortSignal }
): Promise<void> {
  const response = await fetchSSEWithRetry(`/api/games/${gameId}/custom-choice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ custom_text: customChoice }),
    signal: options?.signal,
  }, callbacks, 1);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  return parseSSEStream(reader, callbacks);
}

export async function streamGameEvent(
  gameId: number,
  callbacks: StreamCallbacks,
  options?: { signal?: AbortSignal; lastEventId?: number }
): Promise<void> {
  const headers = options?.lastEventId === undefined
    ? undefined
    : { 'Last-Event-ID': String(options.lastEventId) };
  const response = await fetchSSEWithRetry(`/api/games/${gameId}/event`, {
    method: 'GET',
    credentials: 'include',
    headers,
    signal: options?.signal,
  }, callbacks);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  return parseSSEStream(reader, callbacks);
}

export async function streamRegenerate(
  gameId: number,
  callbacks: StreamCallbacks,
  options?: {
    story_context?: string;
    adjustment?: string;
    signal?: AbortSignal;
    lastEventId?: number;
  }
): Promise<void> {
  const headers = options?.lastEventId === undefined
    ? undefined
    : { 'Last-Event-ID': String(options.lastEventId) };
  const response = await fetchSSEWithRetry(`/api/games/${gameId}/regenerate-stream`, {
    method: 'GET',
    credentials: 'include',
    headers,
    signal: options?.signal,
  }, callbacks);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  return parseSSEStream(reader, callbacks);
}

interface RewriteCallbacks {
  onStory: (text: string) => void;
  onStatus: (status: { phase: string }) => void;
  onComplete: (data: unknown) => void;
  onError?: (error: Error) => void;
  onConnectionStatus?: (status: ConnectionStatus) => void;
  onReconnecting?: (attempt: number, maxRetries: number) => void;
}

export async function streamRewrite(
  gameId: number,
  storyContext: string,
  instruction: string,
  segmentToReplace: string,
  language: string,
  callbacks: RewriteCallbacks,
  options?: { signal?: AbortSignal }
): Promise<{ completed: boolean; error?: Error }> {
  const response = await fetchSSEWithRetry(`/api/games/${gameId}/rewrite-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      full_story: storyContext,
      segment_to_replace: segmentToReplace,
      user_instruction: instruction,
      language: language,
    }),
    signal: options?.signal,
  }, {
    onConnectionStatus: callbacks.onConnectionStatus,
    onReconnecting: callbacks.onReconnecting,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  // Parse SSE stream with rewrite-specific handling
  const decoder = new TextDecoder();
  let buffer = '';
  let currentEventType: string | null = null;

  let completed = false;

  return new Promise((resolve) => {
    function pump(): Promise<void> {
      return reader!.read().then(({ done, value }) => {
        if (done) {
          completed = true;
          callbacks.onComplete?.({});
          resolve({ completed: true, error: undefined });
          return;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          // Parse event type from event: line
          if (trimmed.startsWith('event: ')) {
            currentEventType = trimmed.slice(7);
            continue;
          }
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              completed = true;
              callbacks.onComplete?.({});
              resolve({ completed: true, error: undefined });
              return;
            }
            try {
              const parsed = JSON.parse(data);
              // Handle complete event
              if (currentEventType === 'complete' || parsed.type === 'complete') {
                completed = true;
                callbacks.onComplete?.(parsed.data || parsed);
                continue;
              }
              // Handle status updates
              if (currentEventType === 'status' || parsed.type === 'status') {
                const statusData = parsed.status || parsed;
                if (statusData) {
                  callbacks.onStatus?.(statusData);
                }
                continue;
              }
              // Handle story chunks - check both event type and parsed content
              if (currentEventType === 'story') {
                // If it's a string, use it directly; if object, extract content
                const chunk = typeof parsed === 'string'
                  ? parsed
                  : (parsed.content || parsed.text || parsed.chunk || parsed.story);
                if (chunk) {
                  callbacks.onStory?.(chunk);
                }
                continue;
              }
              // Fallback: check for story_chunk type for backwards compatibility
              if (parsed.type === 'story_chunk' && parsed.content) {
                callbacks.onStory?.(parsed.content);
              }
            } catch {
              // If not JSON, treat as plain text chunk (for story)
              if (data && currentEventType === 'story') {
                callbacks.onStory?.(data);
              }
            }
            // Reset event type after processing data line
            currentEventType = null;
          }
        }

        return pump();
      }).catch((error) => {
        callbacks.onError?.(error);
        resolve({ completed, error });
      });
    }

    pump();
  });
}

/**
 * Stream opening story generation
 */
export async function streamOpeningStory(
  characterSettings: Record<string, unknown>,
  playerName: string,
  lifeVision: string,
  language: string,
  callbacks: {
    onStory?: (text: string) => void;
    onComplete?: (data: unknown) => void;
    onError?: (error: { message: string }) => void;
  },
  options?: { signal?: AbortSignal; enableReconnect?: boolean }
): Promise<void> {
  const response = await fetchSSEWithRetry('/api/character/opening-story', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      character_settings: characterSettings,
      player_name: playerName,
      life_vision: lifeVision,
      language: language,
    }),
    signal: options?.signal,
  }, {});

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  let streamedText = '';
  return parseSSEStream(reader, {
    onStory: (text) => {
      streamedText += text;
      callbacks.onStory?.(text);
    },
    onComplete: (data) => {
      const fullStory = typeof data.full_story === 'string' ? data.full_story : '';
      if (!streamedText.trim() && !fullStory.trim()) {
        throw new Error('Opening story stream completed without story text');
      }
      callbacks.onComplete?.(data);
    },
    onError: (error) => callbacks.onError?.({ message: error.message || 'Stream error' }),
  });
}
