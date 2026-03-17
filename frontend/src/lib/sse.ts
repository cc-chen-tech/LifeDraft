/**
 * Server-Sent Events (SSE) streaming utilities
 */

export interface StreamCallbacks {
  onChunk?: (chunk: string) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
}

function parseSSEStream(reader: ReadableStreamDefaultReader<Uint8Array>, callbacks: StreamCallbacks): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';

  return new Promise((resolve, reject) => {
    function pump(): Promise<void> {
      return reader.read().then(({ done, value }) => {
        if (done) {
          callbacks.onComplete?.();
          resolve();
          return;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              callbacks.onComplete?.();
              resolve();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.content || parsed.text || parsed.chunk) {
                callbacks.onChunk?.(parsed.content || parsed.text || parsed.chunk);
              }
            } catch {
              // If not JSON, treat as plain text chunk
              if (data) {
                callbacks.onChunk?.(data);
              }
            }
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
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/choices/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ choice_index: choiceIndex }),
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
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/choices/custom/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ custom_choice: customChoice }),
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
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/events/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
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
  options?: { story_context?: string; adjustment?: string }
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/regenerate/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(options || {}),
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
  callbacks: RewriteCallbacks
): Promise<void> {
  const response = await fetch(`/api/games/${gameId}/rewrite/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      story_context: storyContext,
      instruction: instruction,
      segment_to_replace: segmentToReplace,
      language: language,
    }),
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

  return new Promise((resolve, reject) => {
    function pump(): Promise<void> {
      return reader.read().then(({ done, value }) => {
        if (done) {
          callbacks.onComplete?.({});
          resolve();
          return;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              callbacks.onComplete?.({});
              resolve();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'story_chunk' && parsed.content) {
                callbacks.onStory?.(parsed.content);
              } else if (parsed.type === 'status' && parsed.status) {
                callbacks.onStatus?.(parsed.status);
              } else if (parsed.type === 'complete') {
                callbacks.onComplete?.(parsed.data || parsed);
              }
            } catch {
              // If not JSON, ignore
            }
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
