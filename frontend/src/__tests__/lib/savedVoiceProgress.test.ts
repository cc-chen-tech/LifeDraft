import { matchesSavedVoiceProgress } from '../../../e2e/helpers/saved-voice-progress';
const saved = {
  game_id: 42, day_index: 1, text_hash: 'a'.repeat(64), voice_id: 'female-shaonv',
  speed: 1, paragraph_index: 0, position_ms: 1200, completed: false,
};
test('requires the real persisted checkpoint roundtrip', () => {
  expect(matchesSavedVoiceProgress(200, { ...saved, updated_at: 'today' }, saved)).toBe(true);
});
test.each([404, 401, 500])('rejects status %s even with a matching body', status => {
  expect(matchesSavedVoiceProgress(status, saved, saved)).toBe(false);
});
test('rejects lost previously saved progress, not an expected missing-progress case', () => {
  expect(matchesSavedVoiceProgress(404, { detail: 'Progress not found' }, saved)).toBe(false);
});
test.each(Object.keys(saved))('rejects changed or missing checkpoint field %s', key => {
  expect(matchesSavedVoiceProgress(200, { ...saved, [key]: undefined }, saved)).toBe(false);
});
test('rejects reset progress and malformed response', () => {
  expect(matchesSavedVoiceProgress(200, { ...saved, paragraph_index: 0, position_ms: 0 }, saved)).toBe(false);
  expect(matchesSavedVoiceProgress(200, null, saved)).toBe(false);
});
