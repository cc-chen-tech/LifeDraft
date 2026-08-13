import {
  EVENT_INACTIVITY_TIMEOUT_MS,
  EVENT_POLL_INTERVAL_MS,
  EVENT_POLL_TIMEOUT_MS,
} from '../useEventGenerator';

describe('useEventGenerator recovery timing', () => {
  it('uses the approved continuous inactivity threshold', () => {
    expect(EVENT_INACTIVITY_TIMEOUT_MS).toBe(45_000);
  });

  it('keeps persisted polling within the existing interval and deadline', () => {
    expect(EVENT_POLL_INTERVAL_MS).toBeLessThanOrEqual(5_000);
    expect(EVENT_POLL_TIMEOUT_MS).toBeLessThanOrEqual(180_000);
  });
});
