import { act, renderHook, waitFor } from "@testing-library/react";
import { useChoiceHandler } from "@/hooks/game/useChoiceHandler";
import { useGameStore } from "@/stores/useGameStore";
import type { StreamCallbacks } from "@/lib/sse";

const mockStreamChoice = jest.fn();
const mockStreamCustomChoice = jest.fn();
const mockMakeChoiceSync = jest.fn();
const mockMakeCustomChoiceSync = jest.fn();

jest.mock("@/lib/sse", () => ({
  streamChoice: (...args: unknown[]) => mockStreamChoice(...args),
  streamCustomChoice: (...args: unknown[]) => mockStreamCustomChoice(...args),
}));

jest.mock("@/lib/api", () => ({
  gameplay: {
    makeChoiceSync: (...args: unknown[]) => mockMakeChoiceSync(...args),
    makeCustomChoiceSync: (...args: unknown[]) => mockMakeCustomChoiceSync(...args),
  },
}));

function pendingStream(callbacks: StreamCallbacks[]): (gameId: number, value: unknown, next: StreamCallbacks) => Promise<void> {
  return (_gameId, _value, next) => {
    callbacks.push(next);
    return new Promise<void>(() => undefined);
  };
}

describe("useChoiceHandler run isolation", () => {
  const abortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const generatingRef: React.MutableRefObject<boolean> = { current: false };
  const runTokenRef: React.MutableRefObject<number> = { current: 0 };
  const setters = {
    setPhase: jest.fn(),
    setConnectionStatus: jest.fn(),
    setReconnectAttempt: jest.fn(),
    setTransport: jest.fn(),
    setLoadingIdentity: jest.fn(),
    setProcessing: jest.fn(),
    appendStoryText: jest.fn(),
    setCurrentEvent: jest.fn(),
    setGameOver: jest.fn(),
    setSummaryText: jest.fn(),
    setRoundSummary: jest.fn(),
    setOptions: jest.fn(),
    setStoryText: jest.fn(),
  };

  const params = {
    gameId: 7,
    abortRef,
    generatingRef,
    runTokenRef,
    ...setters,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockReset().mockResolvedValue({
      ok: true,
      json: async () => ({ current_event: null, round_info: { game_over: false } }),
    });
    abortRef.current = null;
    generatingRef.current = false;
    runTokenRef.current = 0;
    useGameStore.setState({
      storyText: "A base",
      currentEvent: { story: "A", options: [{ text: "A choice" }] },
      roundInfo: { current_round: 1 },
      generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
      syncPlayerState: jest.fn().mockResolvedValue(undefined),
    } as never);
  });

  it("silences every callback from choice A after custom choice B replaces it while B remains live", async () => {
    const aCallbacks: StreamCallbacks[] = [];
    const bCallbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(aCallbacks));
    mockStreamCustomChoice.mockImplementation(pendingStream(bCallbacks));
    mockMakeChoiceSync.mockResolvedValue({
      story_continuation: "old fallback",
      options: [{ text: "old option" }],
    });

    const { result } = renderHook(() => useChoiceHandler(params));

    act(() => {
      void result.current.handleChoice(0);
    });
    useGameStore.setState({
      storyText: "B base",
      currentEvent: { story: "B", options: [{ text: "B choice" }] },
    } as never);
    act(() => {
      void result.current.handleCustomChoice("B custom");
    });

    expect(aCallbacks).toHaveLength(1);
    expect(bCallbacks).toHaveLength(1);
    Object.values(setters).forEach((setter) => setter.mockClear());

    await act(async () => {
      aCallbacks[0].onStory?.("OLD story");
      aCallbacks[0].onStatus?.({ phase: "OLD status" });
      aCallbacks[0].onConnectionStatus?.("error");
      aCallbacks[0].onReconnecting?.(3, 3);
      await aCallbacks[0].onError?.(new Error("network error"));
      aCallbacks[0].onComplete?.({
        event_description: "OLD complete",
        options: [{ text: "OLD option" }],
      });
    });

    expect(mockMakeChoiceSync).not.toHaveBeenCalled();
    expect(setters.appendStoryText).not.toHaveBeenCalled();
    expect(setters.setProcessing).not.toHaveBeenCalled();
    expect(setters.setConnectionStatus).not.toHaveBeenCalled();
    expect(setters.setReconnectAttempt).not.toHaveBeenCalled();
    expect(setters.setStoryText).not.toHaveBeenCalled();
    expect(setters.setOptions).not.toHaveBeenCalled();
    expect(setters.setPhase).not.toHaveBeenCalled();
    expect(setters.setTransport).not.toHaveBeenCalled();

    act(() => {
      bCallbacks[0].onStory?.("B story");
      bCallbacks[0].onStatus?.({ phase: "B status" });
      bCallbacks[0].onComplete?.({
        event_description: "B complete",
        options: [{ text: "B option" }],
      });
    });

    expect(setters.appendStoryText).toHaveBeenCalledWith("B story");
    expect(setters.setProcessing).toHaveBeenCalledWith(true, "B status");
    expect(setters.setPhase).toHaveBeenCalledWith("result");
  });

  it("treats AbortError as silent cancellation without sync fallback or failed UI", async () => {
    const callbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(callbacks));
    const { result } = renderHook(() => useChoiceHandler(params));

    act(() => {
      void result.current.handleChoice(0);
    });
    Object.values(setters).forEach((setter) => setter.mockClear());

    await act(async () => {
      await callbacks[0].onError?.(new DOMException("cancelled", "AbortError"));
    });

    expect(mockMakeChoiceSync).not.toHaveBeenCalled();
    expect(setters.setPhase).not.toHaveBeenCalledWith("error");
    expect(setters.setConnectionStatus).not.toHaveBeenCalledWith("error");
    expect(setters.setTransport).not.toHaveBeenCalledWith("failed");
  });

  it("does not commit choice A when its in-flight read-only reconciliation resolves after B starts", async () => {
    const aCallbacks: StreamCallbacks[] = [];
    const bCallbacks: StreamCallbacks[] = [];
    let resolveSnapshot!: (value: Response) => void;
    const pendingSnapshot = new Promise<Response>((resolve) => {
      resolveSnapshot = resolve;
    });
    mockStreamChoice.mockImplementation(pendingStream(aCallbacks));
    mockStreamCustomChoice.mockImplementation(pendingStream(bCallbacks));
    (global.fetch as jest.Mock).mockReturnValue(pendingSnapshot);

    const { result } = renderHook(() => useChoiceHandler(params));
    act(() => {
      void result.current.handleChoice(0);
    });
    act(() => {
      aCallbacks[0].onError?.(new Error("network error"));
    });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    useGameStore.setState({ storyText: "B base" } as never);
    act(() => {
      void result.current.handleCustomChoice("B custom");
    });
    Object.values(setters).forEach((setter) => setter.mockClear());

    await act(async () => {
      resolveSnapshot({
        ok: true,
        json: async () => ({
          current_event: null,
          player_state: {
            round_history: [{ choice: "A choice", story_continuation: "OLD continuation" }],
            resume_view: { phase: "result", story_text: "OLD recovered story" },
          },
          progress: { week: 1, total_weeks: 52 },
        }),
      } as Response);
      await pendingSnapshot;
      await Promise.resolve();
    });

    expect(mockMakeChoiceSync).not.toHaveBeenCalled();
    expect(setters.setStoryText).not.toHaveBeenCalled();
    expect(setters.setOptions).not.toHaveBeenCalled();
    expect(setters.setPhase).not.toHaveBeenCalled();
    expect(setters.setTransport).not.toHaveBeenCalled();
  });

  it("reports real reconnect and read-only reconciliation before returning active/result", async () => {
    const callbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(callbacks));
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: null,
        player_state: {
          round_history: [{ choice: "A choice", story_continuation: "fallback continuation" }],
          resume_view: { phase: "result", story_text: "A base\n\nfallback continuation" },
        },
        progress: { week: 1, total_weeks: 52 },
      }),
    });

    const { result } = renderHook(() => useChoiceHandler(params));
    act(() => {
      void result.current.handleChoice(0);
    });
    act(() => {
      callbacks[0].onConnectionStatus?.("reconnecting");
      callbacks[0].onReconnecting?.(1, 3);
      callbacks[0].onError?.(new Error("network error"));
    });
    await waitFor(() => expect(setters.setPhase).toHaveBeenCalledWith("result"));

    const transports = setters.setTransport.mock.calls.map(([transport]) => transport);
    const activeStart = transports.indexOf("active");
    const reconnecting = transports.indexOf("reconnecting", activeStart + 1);
    const polling = transports.indexOf("polling", reconnecting + 1);
    const activeEnd = transports.indexOf("active", polling + 1);
    expect([activeStart, reconnecting, polling, activeEnd].every((index) => index >= 0)).toBe(true);
    expect(activeStart).toBeLessThan(reconnecting);
    expect(reconnecting).toBeLessThan(polling);
    expect(polling).toBeLessThan(activeEnd);
  });

  it("reports failed when read-only choice reconciliation finds a persisted failure", async () => {
    const callbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(callbacks));
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: null,
        player_state: { resume_view: { phase: "failed" } },
        progress: { week: 1, total_weeks: 52 },
      }),
    });
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);

    const { result } = renderHook(() => useChoiceHandler(params));
    act(() => {
      void result.current.handleChoice(0);
    });
    act(() => {
      callbacks[0].onError?.(new Error("network error"));
    });

    await waitFor(() => expect(setters.setTransport).toHaveBeenCalledWith("failed"));
    expect(setters.setPhase).toHaveBeenCalledWith("error");
    errorSpy.mockRestore();
  });

  it.each([
    ["normal", (result: ReturnType<typeof useChoiceHandler>) => result.handleChoice(0)],
    ["custom", (result: ReturnType<typeof useChoiceHandler>) => result.handleCustomChoice("B custom")],
  ] as const)("retries a restored %s choice at most once after repeated 404 responses", async (_kind, start) => {
    const callbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(callbacks));
    mockStreamCustomChoice.mockImplementation(pendingStream(callbacks));
    mockMakeChoiceSync.mockRejectedValue(new Error("fallback failed"));
    mockMakeCustomChoiceSync.mockRejectedValue(new Error("fallback failed"));
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: {
          event_description: "restored story",
          options: [{ text: "restored option" }],
        },
      }),
    });
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);
    const { result } = renderHook(() => useChoiceHandler(params));

    act(() => {
      void start(result.current);
    });
    act(() => {
      callbacks[0].onError?.(new Error("404 Not Found"));
    });
    await waitFor(() => expect(callbacks).toHaveLength(2));
    act(() => {
      callbacks[1].onError?.(new Error("404 Not Found"));
    });
    await waitFor(() => expect(setters.setTransport).toHaveBeenCalledWith("failed"));

    expect(callbacks).toHaveLength(2);
    expect(mockStreamChoice.mock.calls.length + mockStreamCustomChoice.mock.calls.length).toBe(2);
    errorSpy.mockRestore();
  });

  it("ignores buffered choice frames after an error starts fallback", async () => {
    const callbacks: StreamCallbacks[] = [];
    let resolveSnapshot!: (value: Response) => void;
    mockStreamChoice.mockImplementation(pendingStream(callbacks));
    (global.fetch as jest.Mock).mockReturnValue(new Promise<Response>((resolve) => {
      resolveSnapshot = resolve;
    }));
    const { result } = renderHook(() => useChoiceHandler(params));

    act(() => {
      void result.current.handleChoice(0);
    });
    act(() => {
      callbacks[0].onError?.(new Error("network error"));
    });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    Object.values(setters).forEach((setter) => setter.mockClear());

    act(() => {
      callbacks[0].onStory?.("buffered stale story");
      callbacks[0].onStatus?.({ phase: "buffered stale status" });
      callbacks[0].onComplete?.({
        event_description: "buffered stale complete",
        options: [{ text: "stale" }],
      });
    });

    expect(setters.appendStoryText).not.toHaveBeenCalled();
    expect(setters.setProcessing).not.toHaveBeenCalled();
    expect(setters.setPhase).not.toHaveBeenCalled();
    resolveSnapshot({
      ok: true,
      json: async () => ({
        current_event: null,
        player_state: {
          round_history: [{ choice: "A choice", story_continuation: "current fallback" }],
          resume_view: { phase: "result", story_text: "current fallback" },
        },
      }),
    } as Response);
  });

  it("manually reconciles the current choice from read-only history without another submit", async () => {
    const callbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(callbacks));
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: null,
        player_state: {
          round_history: [{
            choice: "A choice",
            story_continuation: "server-side completed continuation",
          }],
          resume_view: {
            phase: "result",
            story_text: "A base plus server-side completed continuation",
            round_summary: "server summary",
          },
        },
        progress: { week: 1, total_weeks: 52 },
      }),
    });
    const syncPlayerState = jest.fn().mockResolvedValue(undefined);
    useGameStore.setState({ syncPlayerState } as never);
    const { result } = renderHook(() => useChoiceHandler(params));

    act(() => {
      void result.current.handleChoice(0);
    });
    const withManualRecovery = result.current as typeof result.current & {
      recoverChoiceGeneration: () => Promise<void>;
    };
    await act(async () => {
      await withManualRecovery.recoverChoiceGeneration();
    });

    expect(mockStreamChoice).toHaveBeenCalledTimes(1);
    expect(mockStreamCustomChoice).not.toHaveBeenCalled();
    expect(mockMakeChoiceSync).not.toHaveBeenCalled();
    expect(syncPlayerState).not.toHaveBeenCalled();
    expect(setters.setStoryText).toHaveBeenCalledWith(
      "A base plus server-side completed continuation",
    );
    expect(setters.setRoundSummary).toHaveBeenCalledWith("server summary");
    expect(setters.setPhase).toHaveBeenCalledWith("result");
    expect(setters.setTransport.mock.calls.map(([transport]) => transport)).toEqual(
      expect.arrayContaining(["polling", "active"]),
    );
  });

  it("drops A's manual recovery target when the same page switches to game B", async () => {
    const callbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(callbacks));
    const { result, rerender } = renderHook(
      ({ gameId }) => useChoiceHandler({ ...params, gameId }),
      { initialProps: { gameId: 7 } },
    );

    act(() => {
      void result.current.handleChoice(0);
    });
    expect(callbacks).toHaveLength(1);

    rerender({ gameId: 8 });
    (global.fetch as jest.Mock).mockClear();
    Object.values(setters).forEach((setter) => setter.mockClear());

    await act(async () => {
      void result.current.recoverChoiceGeneration();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(global.fetch).not.toHaveBeenCalled();
    Object.values(setters).forEach((setter) => expect(setter).not.toHaveBeenCalled());

    useGameStore.setState({
      storyText: "B base",
      currentEvent: { story: "B", options: [{ text: "B choice" }] },
    } as never);
    act(() => {
      void result.current.handleChoice(0);
    });
    expect(callbacks).toHaveLength(2);
    (global.fetch as jest.Mock).mockReset().mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: null,
        player_state: {
          round_history: [{
            choice: "B choice",
            story_continuation: "B completed continuation",
          }],
          resume_view: {
            phase: "result",
            story_text: "B base plus completed continuation",
          },
        },
        progress: { week: 2, total_weeks: 52 },
      }),
    });
    Object.values(setters).forEach((setter) => setter.mockClear());

    await act(async () => {
      await result.current.recoverChoiceGeneration();
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(setters.setStoryText).toHaveBeenCalledWith("B base plus completed continuation");
    expect(setters.setPhase).toHaveBeenCalledWith("result");
  });

  it("uses B's captured base story for B complete-only fallback", () => {
    const aCallbacks: StreamCallbacks[] = [];
    const bCallbacks: StreamCallbacks[] = [];
    mockStreamChoice.mockImplementation(pendingStream(aCallbacks));
    mockStreamCustomChoice.mockImplementation(pendingStream(bCallbacks));

    const { result } = renderHook(() => useChoiceHandler(params));
    act(() => {
      void result.current.handleChoice(0);
    });
    useGameStore.setState({ storyText: "B base" } as never);
    act(() => {
      void result.current.handleCustomChoice("B custom");
    });
    setters.setStoryText.mockClear();

    act(() => {
      bCallbacks[0].onComplete?.({
        event_description: "B complete",
        options: [{ text: "B option" }],
      });
    });

    expect(setters.setStoryText).toHaveBeenCalledWith("B base\n\nB complete");
  });
});
