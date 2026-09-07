import { api } from "./api";
import type { VoiceReadingJobResponse } from "./types";

// Waiting owns its listeners and timer, so changing a story also cancels backoff.
function waitForRefresh(milliseconds: number, signal: AbortSignal, wakeOnVisibility = true) {
  return new Promise<void>((resolve) => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const finish = () => {
      if (timer !== undefined) clearTimeout(timer);
      signal.removeEventListener("abort", finish);
      window.removeEventListener("online", finish);
      document.removeEventListener("visibilitychange", visible);
      resolve();
    };
    const visible = () => { if (!document.hidden) finish(); };
    if (signal.aborted) { resolve(); return; }
    signal.addEventListener("abort", finish, { once: true });
    window.addEventListener("online", finish, { once: true });
    if (wakeOnVisibility) document.addEventListener("visibilitychange", visible);
    if (navigator.onLine) timer = setTimeout(finish, milliseconds);
  });
}

export async function pollStoryVoiceJob(
  initial: VoiceReadingJobResponse,
  signal: AbortSignal,
  onJob: (job: VoiceReadingJobResponse) => void,
  onConnectionRetry: (retrying: boolean) => void,
  usingBrowserSpeech: () => boolean,
) {
  let job = initial;
  let failures = 0;
  while (!signal.aborted && !["ready", "failed"].includes(job.status)) {
    if (!navigator.onLine) {
      onConnectionRetry(true);
      await waitForRefresh(0, signal);
      if (signal.aborted) return;
    }
    let retryAfter = 0;
    try {
      job = await api.voice_reading.getJob(initial.job_id, signal);
      if (signal.aborted) return;
      failures = 0;
      onConnectionRetry(false);
      onJob(job);
    } catch (error) {
      if (signal.aborted) return;
      const failure = error as { status?: number; retryAfterMs?: number };
      if (failure.status && failure.status >= 400 && failure.status < 500 && failure.status !== 429) throw error;
      failures += 1;
      retryAfter = failure.retryAfterMs ?? 0;
      onConnectionRetry(true);
    }
    if (!["ready", "failed"].includes(job.status)) {
      const interval = failures ? Math.min(10_000, 1_000 * 2 ** Math.min(failures - 1, 4))
        : usingBrowserSpeech() ? 10_000 : 1_000;
      await waitForRefresh(Math.max(retryAfter, document.hidden ? 15_000 : interval), signal, retryAfter === 0);
    }
  }
}
