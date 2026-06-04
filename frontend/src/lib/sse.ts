/**
 * Server-Sent Events (SSE) streaming utilities
 */

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "error" | null;

export interface StreamCallbacks {
  onStory?: (text: string) => void;
  onChunk?: (chunk: string) => void;
  onStatus?: (status: { phase: string; heartbeat?: boolean; cached_count?: number; message?: string }) => void;
  onComplete?: (data: Record<string, unknown>) => void;
  onError?: (error: Error | { message: string }) => void;
  onConnectionStatus?: (status: ConnectionStatus) => void;
  onReconnecting?: (attempt: number, maxRetries: number) => void;
}

function parseSSEStream(reader: ReadableStreamDefaultReader<Uint8Array>, callbacks: StreamCallbacks): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';
  let currentEventType: string | null = null;
  let completeData: Record<string, unknown> | null = null;
  let isCompleteReceived = false;
  let isErrorReceived = false;
  let isResolved = false;

  return new Promise((resolve, reject) => {
    function safeResolve() {
      if (!isResolved) {
        isResolved = true;
        resolve();
      }
    }

    function pump(): Promise<void> {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      return reader!.read().then(({ done, value }) => {
        if (done) {
          // Stream ended - use the last complete event data if received
          console.log('[SSE] Stream ended, isCompleteReceived:', isCompleteReceived, 'completeData keys:', Object.keys(completeData || {}));
          if (isCompleteReceived && completeData) {
            callbacks.onComplete?.(completeData);
          } else if (!isCompleteReceived && !isErrorReceived) {
            callbacks.onComplete?.({});
          }
          safeResolve();
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
              // [DONE] marker - resolve with any stored complete data
              if (!isResolved) {
                if (isErrorReceived) {
                  safeResolve();
                  return;
                }
                if (completeData) {
                  callbacks.onComplete?.(completeData);
                } else {
                  callbacks.onComplete?.({});
                }
                safeResolve();
              }
              return;
            }
            try {
              const parsed = JSON.parse(data);

              // Handle complete event (either from event: line or type field in data)
              if (currentEventType === 'complete' || parsed.type === 'complete' || parsed.event === 'complete') {
                // Store the complete data but don't call callback yet
                // Wait for stream to end or [DONE] marker to ensure all data is received
                completeData = parsed.data || parsed;
                isCompleteReceived = true;
                console.log('[SSE] Complete event received, data keys:', Object.keys(completeData || {}));
                currentEventType = null;
                continue;
              }

              // ★ Handle error events from backend
              if (currentEventType === 'error' || parsed.type === 'error' || parsed.event === 'error') {
                const errorMsg = parsed.error || parsed.message || 'Unknown server error';
                console.error('[SSE] Error event received:', errorMsg);
                isErrorReceived = true;
                callbacks.onError?.({ message: errorMsg });
                currentEventType = null;
                continue;
              }

              // Handle status updates (support both formats: {type: "status", status: {...}} and {phase: "..."})
              if (currentEventType === 'status' || parsed.type === 'status') {
                const statusData = parsed.status || parsed;
                callbacks.onStatus?.(statusData);
                currentEventType = null;
                continue;
              }

              // Handle story chunks
              // 如果是字符串，直接使用；如果是对象，尝试提取内容字段
              const chunk = typeof parsed === 'string' 
                ? parsed 
                : (parsed.content || parsed.text || parsed.chunk || parsed.story);
              if (chunk) {
                callbacks.onChunk?.(chunk);
                callbacks.onStory?.(chunk);
              }
            } catch {
              // If not JSON, treat as plain text chunk (for story)
              if (data && currentEventType !== 'complete') {
                callbacks.onChunk?.(data);
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
        reject(error);
      });
    }

    pump();
  });
}

export async function streamChoice(
  gameId: number,
  choiceIndex: number,
  callbacks: StreamCallbacks,
  options?: { signal?: AbortSignal }
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/choice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ option_index: choiceIndex }),
    signal: options?.signal,
  });

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
  const response = await fetch(`/api/games/${gameId}/custom-choice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ custom_text: customChoice }),
    signal: options?.signal,
  });

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
  options?: { signal?: AbortSignal }
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/event`, {
    method: 'GET',
    credentials: 'include',
    signal: options?.signal,
  });

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
  options?: { story_context?: string; adjustment?: string; signal?: AbortSignal }
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/regenerate-stream`, {
    method: 'GET',
    credentials: 'include',
    signal: options?.signal,
  });

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
  const response = await fetch(`/api/games/${gameId}/rewrite-stream`, {
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

  return new Promise((resolve, reject) => {
    function pump(): Promise<void> {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
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
  const response = await fetch('/api/character/opening-story', {
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
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  return parseSSEStream(reader, {
    onStory: callbacks.onStory,
    onComplete: callbacks.onComplete as ((data: Record<string, unknown>) => void) | undefined,
    onError: (error) => callbacks.onError?.({ message: error.message || 'Stream error' }),
  });
}
