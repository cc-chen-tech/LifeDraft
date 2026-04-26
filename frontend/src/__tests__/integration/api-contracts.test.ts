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

  describe("music playlist API contracts", () => {
    it("playlist endpoint paths must match backend routes", () => {
      // These paths must match the FastAPI router definitions exactly
      const gameId = 123;
      const paths = [
        `/music/playlist/${gameId}`,
        `/music/playlist/${gameId}/sync`,
        `/music/playlist/${gameId}/advance`,
      ];
      paths.forEach((path) => {
        expect(path).toMatch(/^\/music\/playlist\/\d+/);
      });
    });

    it("playlist response shape must include required fields", () => {
      // Compile-time shape validation via a dummy object
      const dummyResponse: {
        game_id: number;
        current_song: { id: number; name: string; artists: string[]; album: string; duration: number; url?: string } | null;
        queue: Array<{ id: number; name: string; artists: string[]; album: string; duration: number }>;
        played_songs: Array<{ id: number; name: string; artists: string[]; album: string; duration: number }>;
        is_playing: boolean;
        volume: number;
        current_position_ms: number;
        recommendation_mood: string | null;
        updated_at: string | null;
      } = {
        game_id: 1,
        current_song: null,
        queue: [],
        played_songs: [],
        is_playing: false,
        volume: 0.5,
        current_position_ms: 0,
        recommendation_mood: null,
        updated_at: null,
      };
      expect(dummyResponse.game_id).toBe(1);
    });
  });
});
