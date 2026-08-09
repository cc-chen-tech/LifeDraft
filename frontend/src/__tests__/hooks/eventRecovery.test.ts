import { fetchPersistedEventSnapshot } from "@/hooks/game/eventRecovery";

describe("eventRecovery read-only snapshots", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("uses the first nonblank persisted story candidate", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: {
          event_description: "   ",
          story_text: "persisted story text",
          story: "older story field",
          options: [{ text: "continue" }],
        },
        round_info: { game_over: false },
      }),
    });

    const snapshot = await fetchPersistedEventSnapshot(4, new AbortController().signal);

    expect(snapshot?.story).toBe("persisted story text");
  });

  it("carries a durable game-over result even when current_event is empty", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: null,
        player_state: { resume_view: { phase: "ending" } },
        progress: { week: 52, total_weeks: 52 },
      }),
    });

    const snapshot = await fetchPersistedEventSnapshot(4, new AbortController().signal);

    expect(snapshot).toEqual(expect.objectContaining({
      story: "",
      options: [],
      gameOver: true,
    }));
  });

  it("aborts a hanging snapshot request at its per-request deadline", async () => {
    jest.useFakeTimers();
    const parent = new AbortController();
    let requestSignal: AbortSignal | undefined;
    (global.fetch as jest.Mock).mockImplementation((_url: string, init: RequestInit) => {
      requestSignal = init.signal as AbortSignal;
      return new Promise((_resolve, reject) => {
        requestSignal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        }, { once: true });
      });
    });
    const fetchWithDeadline = fetchPersistedEventSnapshot as unknown as (
      gameId: number,
      signal: AbortSignal,
      timeoutMs: number,
    ) => Promise<unknown>;
    const observed = fetchWithDeadline(4, parent.signal, 100).catch((error) => error);

    await jest.advanceTimersByTimeAsync(100);

    expect(requestSignal).not.toBe(parent.signal);
    expect(requestSignal?.aborted).toBe(true);
    parent.abort();
    await observed;
    jest.clearAllTimers();
    jest.useRealTimers();
  });
});
