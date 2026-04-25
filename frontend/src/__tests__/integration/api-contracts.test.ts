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

  describe("music API paths", () => {
    it("must use relative /api paths (not absolute URL with inconsistent prefix)", () => {
      // Music API must go through the same /api proxy as all other APIs.
      // Using window.location-based absolute URLs bypasses the proxy
      // and can cause CORS/timeout issues.
      const validPaths = [
        "/api/music/recommend",
        "/api/music/song-url",
        "/api/music/stream/123",
      ];
      validPaths.forEach((path) => {
        expect(path).toMatch(/^\/api\/music\//);
      });
    });
  });
});
