export interface SavedVoiceProgress {
  game_id: number;
  day_index: number;
  text_hash: string;
  voice_id: string;
  speed: number;
  paragraph_index: number;
  position_ms: number;
  completed: boolean;
}

/** A saved checkpoint must not become a missing or reset checkpoint. */
export function matchesSavedVoiceProgress(status: number, body: unknown, expected: SavedVoiceProgress): boolean {
  if (status !== 200 || body === null || typeof body !== 'object') return false;
  const actual = body as Record<string, unknown>;
  return Object.entries(expected).every(([key, value]) => actual[key] === value);
}
