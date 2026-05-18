import { shouldRetryApiResponse } from "@/lib/api";

describe("api retry policy", () => {
  it("does not retry voice reading 401 responses so browser speech fallback starts immediately", () => {
    expect(shouldRetryApiResponse(401, "/voice-reading/read", 0)).toBe(false);
  });

  it("keeps one auth retry for non-voice endpoints that may hit cookie forwarding races", () => {
    expect(shouldRetryApiResponse(401, "/games", 0)).toBe(true);
    expect(shouldRetryApiResponse(401, "/games", 1)).toBe(false);
  });

  it("retries server errors and does not retry normal client errors", () => {
    expect(shouldRetryApiResponse(503, "/voice-reading/read", 0)).toBe(true);
    expect(shouldRetryApiResponse(404, "/voice-reading/read", 0)).toBe(false);
  });
});
