export interface GameplayRun {
  token: number;
  controller: AbortController;
  isCurrent: () => boolean;
  isLive: () => boolean;
}

export function beginGameplayRun(
  runTokenRef: React.MutableRefObject<number>,
  abortRef: React.MutableRefObject<AbortController | null>,
): GameplayRun {
  const token = runTokenRef.current + 1;
  runTokenRef.current = token;

  const previousController = abortRef.current;
  const controller = new AbortController();
  abortRef.current = controller;
  previousController?.abort();

  const isCurrent = () => runTokenRef.current === token;
  return {
    token,
    controller,
    isCurrent,
    isLive: () => isCurrent() && !controller.signal.aborted,
  };
}

export function invalidateGameplayRun(
  runTokenRef: React.MutableRefObject<number>,
  abortRef: React.MutableRefObject<AbortController | null>,
): void {
  runTokenRef.current += 1;
  const controller = abortRef.current;
  abortRef.current = null;
  controller?.abort();
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof Error && error.name === 'AbortError') ||
    (typeof error === 'object' && error !== null && (error as { name?: unknown }).name === 'AbortError')
  );
}

export function abortableSleep(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return Promise.reject(new DOMException('The operation was aborted.', 'AbortError'));
  }

  return new Promise<void>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      window.clearTimeout(timeoutId);
      reject(new DOMException('The operation was aborted.', 'AbortError'));
    };
    signal.addEventListener('abort', onAbort, { once: true });
  });
}
