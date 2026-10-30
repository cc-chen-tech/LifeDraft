import { isExpectedMissingVoiceProgress } from '../../../e2e/helpers/expected-voice-progress';
import type { NetworkError } from '../../../e2e/helpers/network-monitor';

const scope = { origin: 'http://localhost:3000', gameId: 42, dayIndex: 1, textHash: 'a'.repeat(64) };
const error: NetworkError = {
  url: `${scope.origin}/api/voice-reading/progress?game_id=42&day_index=1&text_hash=${scope.textHash}&voice_id=narrator&speed=1`,
  method: 'GET', status: 404, statusText: 'Not Found', timestamp: '',
  body: JSON.stringify({ detail: 'Progress not found' }),
};

test('accepts only the current chapter missing progress contract', () => {
  expect(isExpectedMissingVoiceProgress(error, scope)).toBe(true);
});

test.each([
  { method: 'PATCH' }, { status: 500 }, { status: 401 },
  { body: '{"detail":"Not Found"}' }, { body: '{"detail":"Game not found"}' },
  { body: '{"detail":"Progress not found","error":"unexpected"}' },
  { body: '' }, { body: 'invalid json' },
  { url: error.url.replace('/progress?', '/progress/other?') },
  { url: error.url.replace('/voice-reading/progress', '/games/42/history') },
  { url: error.url.replace('localhost:3000', 'other.example') },
  { url: error.url.replace('game_id=42', 'game_id=43') },
  { url: error.url.replace('day_index=1', 'day_index=2') },
  { url: error.url.replace(scope.textHash, 'b'.repeat(64)) },
  { url: error.url.replace('voice_id=narrator', 'voice_id=') },
  { url: error.url.replace('speed=1', 'speed=NaN') },
  { url: error.url.replace('speed=1', 'speed=0') },
  { url: error.url + '&game_id=42' }, { url: error.url + '&unknown=value' },
  { url: 'not a URL' },
])('preserves unexpected errors: %j', (change) => {
  expect(isExpectedMissingVoiceProgress({ ...error, ...change }, scope)).toBe(false);
});
