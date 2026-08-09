import { act, renderHook, waitFor } from "@testing-library/react";
import type { StreamCallbacks } from "@/lib/sse";
import { jsonResponse } from "@/__tests__/helpers/fetch";
import { useGameStore } from "@/stores/useGameStore";
import { useSessionStore } from "@/stores/useSessionStore";

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

const mockEventCallbacks: StreamCallbacks[] = [];
const mockChoiceCallbacks: StreamCallbacks[] = [];
const mockStreamGameEvent = jest.fn((_gameId: number, callbacks: StreamCallbacks) => {
  mockEventCallbacks.push(callbacks);
  return new Promise<void>(() => undefined);
});
const mockStreamChoice = jest.fn((_gameId: number, _option: number, callbacks: StreamCallbacks) => {
  mockChoiceCallbacks.push(callbacks);
  return new Promise<void>(() => undefined);
});

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock("@/lib/sse", () => ({
  ...jest.requireActual("@/lib/sse"),
  streamGameEvent: (...args: [number, StreamCallbacks]) => mockStreamGameEvent(...args),
  streamChoice: (...args: [number, number, StreamCallbacks]) => mockStreamChoice(...args),
}));

import { usePlayGame } from "@/hooks/usePlayGame";

const realSyncState = useGameStore.getState().syncState;

describe("usePlayGame shared gameplay run", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEventCallbacks.length = 0;
    mockChoiceCallbacks.length = 0;
    useGameStore.getState().resetGame();
    useSessionStore.setState({ gameId: 9 });
    useGameStore.setState({
      gameId: 9,
      storyText: "event base",
      currentEvent: null,
      roundInfo: { current_round: 1 },
      syncState: jest.fn(() => new Promise<void>(() => undefined)),
      generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
      syncPlayerState: jest.fn().mockResolvedValue(undefined),
      fetchRoundSceneImage: jest.fn().mockResolvedValue(undefined),
      fetchAllRoundSceneImages: jest.fn().mockResolvedValue(undefined),
    } as never);
  });

  it("makes a new choice stale every callback owned by the pending event run", async () => {
    const { result, unmount } = renderHook(() => usePlayGame());
    await waitFor(() => expect(result.current.gameId).toBe(9));

    act(() => {
      void result.current.generateEvent();
    });
    await waitFor(() => expect(mockEventCallbacks).toHaveLength(1));

    act(() => {
      useGameStore.getState().setStoryText("choice base");
      useGameStore.getState().setCurrentEvent({
        story: "choice base",
        options: [{ text: "choose B" }],
      });
      result.current.setPhase("options");
      void result.current.handleChoice(0);
    });
    await waitFor(() => expect(mockChoiceCallbacks).toHaveLength(1));
    const storyBeforeOldCallbacks = useGameStore.getState().storyText;

    await act(async () => {
      mockEventCallbacks[0].onStory?.("OLD event story");
      mockEventCallbacks[0].onStatus?.({ phase: "OLD status" });
      mockEventCallbacks[0].onEventId?.(99);
      mockEventCallbacks[0].onComplete?.({
        event_description: "OLD event complete",
        options: [{ text: "OLD option" }],
      });
      mockEventCallbacks[0].onError?.(new Error("network error"));
      await Promise.resolve();
    });

    expect(useGameStore.getState().storyText).toBe(storyBeforeOldCallbacks);
    expect(result.current.phase).toBe("choosing");
    expect(result.current.transport).toBe("active");

    act(() => {
      mockChoiceCallbacks[0].onStory?.("B continuation");
      mockChoiceCallbacks[0].onComplete?.({
        story_continuation: "B continuation",
        options: [{ text: "next" }],
        need_weekly_summary: false,
        game_over: false,
      });
    });

    expect(useGameStore.getState().storyText).toContain("B continuation");
    expect(result.current.phase).toBe("result");
    expect(result.current.transport).toBe("active");
    unmount();
  });

  it("does not let an initialization response overwrite stores after a gameplay run starts", async () => {
    const initialState = createDeferred<Response>();
    (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/games/9")) return initialState.promise;
      throw new Error(`Unexpected fetch: ${url}`);
    });
    useGameStore.setState({ syncState: realSyncState } as never);

    const { result, unmount } = renderHook(() => usePlayGame());
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/games\/9$/),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));

    act(() => {
      void result.current.generateEvent();
    });
    await waitFor(() => expect(mockStreamGameEvent).toHaveBeenCalledTimes(1));

    act(() => {
      useSessionStore.setState({
        gameId: 9,
        playerState: { player_name: "B player" },
        progress: { week: 8 },
        roundInfo: { week: 8, current_round: 2 },
      } as never);
      useGameStore.setState({
        gameId: 9,
        playerState: { player_name: "B player" },
        progress: { week: 8 },
        roundInfo: { week: 8, current_round: 2 },
        storyText: "B live story",
        currentEvent: null,
      } as never);
    });

    initialState.resolve(jsonResponse({
      player_state: { player_name: "STALE A player" },
      progress: { week: 1 },
      round_info: { week: 1, current_round: 0 },
      current_event: {
        event_description: "STALE A story",
        options: [{ text: "STALE A option" }],
      },
      constraint_level: "expert",
    }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(useSessionStore.getState().playerState).toEqual({ player_name: "B player" });
    expect(useGameStore.getState()).toEqual(expect.objectContaining({
      playerState: { player_name: "B player" },
      progress: { week: 8 },
      roundInfo: { week: 8, current_round: 2 },
      storyText: "B live story",
      currentEvent: null,
    }));
    expect(result.current.phase).toBe("generating");
    unmount();
  });
});
