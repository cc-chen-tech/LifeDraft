import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockApi = {
  games: {
    load: jest.fn(),
  },
  gameplay: {
    getState: jest.fn(),
    generateSummary: jest.fn(),
  },
  story: {
    chat: jest.fn(),
  },
  collection: {
    get: jest.fn(),
  },
  images: {
    listByGame: jest.fn(),
  },
};

const mockStreamRewrite = jest.fn();

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: mockApi,
}));

jest.mock("@/lib/sse", () => ({
  streamRewrite: (...args: unknown[]) => mockStreamRewrite(...args),
}));

import { ChatBar } from "@/components/game/ChatBar";
import { MusicPlayer } from "@/components/game/MusicPlayer";
import { useCollectionStore } from "@/stores/useCollectionStore";
import { useEventStore } from "@/stores/useEventStore";
import { useGameStore } from "@/stores/useGameStore";
import { useImageStore } from "@/stores/useImageStore";
import { useMusicStore } from "@/stores/useMusicStore";
import { useSceneImageStore } from "@/stores/useSceneImageStore";
import { useSessionStore } from "@/stores/useSessionStore";

const restoredGameState = {
  game_id: 101,
  player_state: {
    player_name: "陆明",
    character_settings: { era: "民国" },
    last_round_full_story: "码头旧账被重新翻开，陆明看见夹层里的暗号。",
    round_history: [],
  },
  progress: { week: 3, current_round: 2, rounds_per_week: 4 },
  round_info: { week: 3, current_round: 2, rounds_per_week: 4 },
  current_event: {
    event_description: "",
    story_text: "",
    options: [{ text: "核对暗号" }, { text: "追去船行" }],
  },
  constraint_level: "expert",
};

function resetStores() {
  useSessionStore.setState({
    gameId: null,
    sessionId: null,
    playerState: null,
    progress: null,
    roundInfo: null,
    isGameOver: false,
    enableSceneImage: true,
    constraintLevel: "expert",
  } as never);
  useEventStore.setState({
    currentEvent: null,
    storyText: "",
    lastSummary: null,
  });
  useSceneImageStore.setState({
    roundSceneImages: [],
    currentRoundSceneImage: null,
    eventSceneImage: null,
    resultSceneImage: null,
    isLoadingRoundSceneImage: false,
    isRegeneratingRoundScene: false,
    roundSceneRegenerateError: null,
    historySceneImage: null,
    isLoadingHistoryImage: false,
    isGeneratingHistoryImage: false,
    isRegeneratingHistoryImage: false,
  });
  useImageStore.setState({
    loadPlayerImages: jest.fn(),
  } as never);
  useCollectionStore.setState({
    characters: [],
    items: [],
    landmarks: [],
    isLoading: false,
    isRefreshing: false,
    selectedCharacter: null,
    selectedItem: null,
    selectedLandmark: null,
    error: null,
  });
  useMusicStore.setState({
    currentSong: null,
    queue: [],
    playedSongs: [],
    recommendation: null,
    recommendationError: null,
    isLoadingRecommendation: false,
    playlistGameId: null,
    audioElement: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    activeStoryText: null,
    activeGameId: null,
  } as never);
  useGameStore.getState()._syncFromSubStores();
}

describe("browser exploration regression preflight", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetStores();
    global.fetch = jest.fn();
  });

  it("restores visible story text from persisted game state when backend current event is empty", async () => {
    mockApi.games.load.mockResolvedValue(restoredGameState);

    await act(async () => {
      await useGameStore.getState().loadGameState(101);
    });

    expect(useGameStore.getState().storyText).toBe("码头旧账被重新翻开，陆明看见夹层里的暗号。");
    expect(useGameStore.getState().currentEvent).toEqual({
      story: "码头旧账被重新翻开，陆明看见夹层里的暗号。",
      options: [{ text: "核对暗号" }, { text: "追去船行" }],
    });
  });

  it("recovers an expired session during sync without leaving the main story blank", async () => {
    mockApi.gameplay.getState.mockRejectedValueOnce(Object.assign(new Error("No active game session"), { status: 404 }));
    mockApi.games.load.mockResolvedValue(restoredGameState);

    useSessionStore.setState({ gameId: 101 } as never);

    await act(async () => {
      await useGameStore.getState().syncState();
    });

    expect(mockApi.games.load).toHaveBeenCalledWith(101);
    expect(useGameStore.getState().storyText).toBe("码头旧账被重新翻开，陆明看见夹层里的暗号。");
    expect(useGameStore.getState().currentEvent?.options).toHaveLength(2);
  });

  it("retries inline rewrite after session restore and applies the rewritten story once", async () => {
    const user = userEvent.setup();
    const originalSyncState = useGameStore.getState().syncState;
    const syncState = jest.fn().mockResolvedValue(undefined);
    const onRewriteComplete = jest.fn();

    useGameStore.setState({ syncState } as never);
    mockStreamRewrite
      .mockRejectedValueOnce(Object.assign(new Error("No active game session"), { status: 404 }))
      .mockImplementationOnce(async (_gameId, _fullStory, _instruction, _segment, _language, callbacks) => {
        callbacks.onComplete({ new_story: "改写后的码头故事只出现一次。" });
        return { completed: true };
      });

    try {
      render(
        <ChatBar
          gameId={101}
          storyText="原始码头故事。"
          onSave={jest.fn()}
          onRegenerate={jest.fn()}
          onRewriteComplete={onRewriteComplete}
        />,
      );

      await user.click(screen.getByLabelText("打开聊天"));
      await user.click(await screen.findByTestId("rewrite-button"));
      await user.type(screen.getByPlaceholderText(/描述你想要的修改/), "压缩重复段落");
      await user.click(screen.getByRole("button", { name: "改写故事" }));

      await waitFor(() => expect(syncState).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(onRewriteComplete).toHaveBeenCalledWith("改写后的码头故事只出现一次。"));
      expect(mockStreamRewrite).toHaveBeenCalledTimes(2);
    } finally {
      useGameStore.setState({ syncState: originalSyncState } as never);
    }
  });

  it("keeps collection data visible when background refresh fails", async () => {
    const existingCharacter = {
      name: "苏小二",
      role: "船行旧相识",
      description: "船行里的旧相识",
      affinity: 15,
      age: null,
      gender: null,
      occupation: null,
      personality_traits: [],
      image_url: "/old-character.png",
      image_generated: true,
      description_generated: true,
    };

    useCollectionStore.setState({
      characters: [existingCharacter],
      selectedCharacter: existingCharacter,
    });
    mockApi.collection.get.mockRejectedValueOnce(new Error("refresh failed"));

    await act(async () => {
      await useCollectionStore.getState().fetchCollection(101, true);
    });

    const state = useCollectionStore.getState();
    expect(state.error).toBe("refresh failed");
    expect(state.isRefreshing).toBe(false);
    expect(state.characters[0]).toMatchObject({
      name: "苏小二",
      image_url: "/old-character.png",
      image_generated: true,
    });
    expect(state.selectedCharacter?.image_url).toBe("/old-character.png");
  });

  it("shows an explicit music degradation state without clearing playlist continuity", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "music provider unavailable" }),
    });
    useMusicStore.setState({
      currentSong: {
        id: 1001,
        name: "雨夜码头",
        artists: ["测试歌手"],
        album: "旧案",
        duration: 180,
        source: "netease",
      },
      queue: [
        {
          id: 1002,
          name: "雾港暗流",
          artists: ["测试歌手"],
          album: "旧案",
          duration: 180,
          source: "netease",
        },
      ],
      playedSongs: [1000],
    } as never);

    render(<MusicPlayer storyText="雨夜码头的旧账册被风吹开。" gameId={101} />);

    await screen.findByText("音乐服务暂不可用");

    const state = useMusicStore.getState();
    expect(state.currentSong?.name).toBe("雨夜码头");
    expect(state.queue.map((song) => song.name)).toEqual(["雾港暗流"]);
    expect(state.playedSongs).toEqual([1000]);
  });
});
