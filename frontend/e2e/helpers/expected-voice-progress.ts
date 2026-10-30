import type { NetworkError } from './network-monitor';

export interface VoiceProgressScope {
  origin: string;
  gameId: number;
  dayIndex: number;
  textHash: string;
}

/** Only the documented no-saved-progress response for this exact chapter. */
export function isExpectedMissingVoiceProgress(error: NetworkError, scope: VoiceProgressScope): boolean {
  if (error.method !== 'GET' || error.status !== 404) return false;
  try {
    const url = new URL(error.url);
    if (url.origin !== scope.origin || url.pathname !== '/api/voice-reading/progress') return false;
    const params = url.searchParams;
    const keys = ['game_id', 'day_index', 'text_hash', 'voice_id', 'speed'];
    if ([...params.keys()].length !== keys.length || keys.some(key => params.getAll(key).length !== 1)) return false;
    if (!Number.isInteger(scope.gameId) || scope.gameId <= 0
      || !Number.isInteger(scope.dayIndex) || scope.dayIndex < 0
      || !/^[a-f0-9]{64}$/.test(scope.textHash)) return false;
    if (params.get('game_id') !== String(scope.gameId)
      || params.get('day_index') !== String(scope.dayIndex)
      || params.get('text_hash') !== scope.textHash) return false;
    const speed = Number(params.get('speed'));
    if (!params.get('voice_id')?.trim() || !Number.isFinite(speed) || speed <= 0) return false;
    const body = JSON.parse(error.body ?? '');
    return body !== null && typeof body === 'object'
      && Object.keys(body).length === 1 && body.detail === 'Progress not found';
  } catch {
    return false;
  }
}
