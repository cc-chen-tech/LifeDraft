import { api } from "@/lib/api";
import type { VoiceReadingProgress } from "@/lib/types";

type Session = { active: boolean };
type PendingWrite = {
  key: string;
  progress: VoiceReadingProgress;
  session: Session;
  retain: boolean;
  retries: number;
  readyAt: number;
};

// Shared across remounts so a final choice write cannot retry over a newer
// snapshot of the same story. Entries disappear on success, exhaustion or release.
const pending = new Map<string, PendingWrite>();
let inFlight: PendingWrite | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
const MAX_RETRIES = 3;

function flush() {
  if (inFlight) return;
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
  const next = [...pending.values()].sort((left, right) => left.readyAt - right.readyAt)[0];
  if (!next) return;
  const delay = next.readyAt - Date.now();
  if (delay > 0) {
    timer = setTimeout(flush, Math.min(delay, 2_147_483_647));
    return;
  }
  pending.delete(next.key);
  inFlight = next;
  void api.voice_reading.updateProgress(next.progress).catch((error: unknown) => {
    console.warn("[StoryListeningExperience] Progress persistence unavailable", error);
    const failure = error as { status?: number; retryAfterMs?: number } | null;
    const newer = pending.get(next.key);
    if (failure?.status !== 503 || next.retries >= MAX_RETRIES || (!newer && !next.session.active && !next.retain)) return;
    const retryAfter = Number.isFinite(failure.retryAfterMs) ? Math.max(0, failure.retryAfterMs!) : 0;
    pending.set(next.key, {
      ...(newer ?? next),
      retries: next.retries + 1,
      readyAt: Date.now() + Math.max(1000 * 2 ** next.retries, retryAfter),
    });
  }).finally(() => {
    inFlight = null;
    flush();
  });
}

export function createStoryVoiceProgressSession() {
  const session: Session = { active: true };
  return {
    write(progress: VoiceReadingProgress, retainAfterRelease = false) {
      if (!session.active) return;
      const key = JSON.stringify([progress.game_id, progress.day_index, progress.text_hash, progress.voice_id, progress.speed]);
      const previous = pending.get(key) ?? (inFlight?.key === key ? inFlight : null);
      pending.set(key, {
        key,
        progress: { ...progress },
        session,
        retain: retainAfterRelease,
        retries: previous?.retries ?? 0,
        readyAt: previous?.readyAt ?? 0,
      });
      flush();
    },
    release() {
      session.active = false;
      for (const [key, entry] of pending) {
        if (entry.session === session && !entry.retain) pending.delete(key);
      }
      flush();
    },
  };
}
