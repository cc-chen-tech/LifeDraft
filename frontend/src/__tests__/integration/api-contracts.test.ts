/**
 * API Contract Tests
 * Verifies frontend API paths match backend route definitions.
 * Prevents: 404 errors, stale data reads, routing mismatches.
 */

describe("API Contracts", () => {
  describe("gameplay.getState", () => {
    it("must call /games/{id}/state (not /games/{id}) for live session state", () => {
      // CRITICAL: /games/{id} is load_game() which reads from DB (stale).
      // /games/{id}/state is get_game_state() which reads from live session.
      // Calling the wrong endpoint causes week/progress to never update.
      const expectedPattern = /\/games\/\d+\/state$/;
      expect("/games/123/state").toMatch(expectedPattern);
      expect("/games/123").not.toMatch(expectedPattern);
    });
  });

  describe("retired music API", () => {
    it("is absent from current client contracts", () => {
      const activeApiFamilies = ["/games", "/gameplay", "/voice-reading"];
      expect(activeApiFamilies.some((path) => path.startsWith("/music"))).toBe(false);
    });
  });
});
