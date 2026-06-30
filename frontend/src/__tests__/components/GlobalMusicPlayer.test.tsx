/**
 * GlobalMusicPlayer Component Tests
 * Tests the global music player wrapper with store integration
 */
import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock API-calling functions from music store to avoid real HTTP calls
jest.mock("@/stores/useMusicStore", () => {
  const actual = jest.requireActual("@/stores/useMusicStore");
  return {
    ...actual,
    fetchMusicRecommendation: jest.fn().mockResolvedValue(undefined),
    fetchSongUrl: jest.fn().mockResolvedValue(""),
  };
});

import {
  fetchMusicRecommendation,
  useMusicStore,
} from "@/stores/useMusicStore";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";
import { GlobalMusicPlayer } from "@/components/game/GlobalMusicPlayer";
import type { ReadingContext } from "@/lib/types";
import { jsonResponse } from "@/__tests__/helpers/fetch";

const activeReadingContext: ReadingContext = {
  source_type: "current_story",
  game_id: 1,
  week: 1,
  round_number: 1,
  stage: "event",
  attempt_id: "1-1",
  text_hash: "hash",
  text: "一段需要朗读的故事。",
};

function setStoreState(overrides: Record<string, unknown> = {}) {
  useMusicStore.setState({
    playlistGameId: null,
    currentSong: null,
    queue: [],
    recommendation: null,
    activeStoryText: null,
    activeGameId: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    audioElement: null,
    ...overrides,
  } as never);
}

describe("GlobalMusicPlayer", () => {
  let loadPlaylistSpy: jest.SpyInstance;
  let togglePlaySpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes("/voice-reading/settings")) {
        return Promise.resolve(
          jsonResponse({
            auto_read_enabled: false,
            selected_voice_color: "warm_female",
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    useMusicStore.setState({
      playlistGameId: null,
      currentSong: null as never,
      queue: [],
      recommendation: null,
      activeStoryText: null as never,
      activeGameId: null as never,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      audioElement: null as never,
    });
    useStoryVoiceStore.setState({
      readingState: "idle",
      currentSource: "",
      currentContextLabel: "",
      currentAudioUrl: "",
      currentJobId: null,
      currentProvider: "",
      playbackMode: "none",
      spokenTextLength: 0,
      currentSpeechText: "",
      errorMessage: "",
      queueText: "",
      autoReadEnabled: false,
      selectedVoiceId: "warm_female",
      musicDuckState: "idle",
      musicWasPlaying: false,
      userChangedMusic: false,
      activeReadingContext: null,
      activeAutoReadText: "",
      activeAutoReadReady: false,
    } as never);
    loadPlaylistSpy = jest
      .spyOn(useMusicStore.getState(), "loadPlaylist")
      .mockResolvedValue(undefined);
    togglePlaySpy = jest.spyOn(useMusicStore.getState(), "togglePlay");
  });

  afterEach(() => {
    loadPlaylistSpy.mockRestore();
    togglePlaySpy.mockRestore();
  });

  describe("Conditional rendering", () => {
    it("returns null when there is no storyText and no persisted music data", () => {
      setStoreState({
        activeStoryText: null,
        recommendation: null,
        currentSong: null,
        queue: [],
      });

      const { container } = render(<GlobalMusicPlayer />);
      expect(container.firstChild).toBeNull();
    });

    it("renders when activeStoryText is set", () => {
      setStoreState({
        activeStoryText: "Some story text",
        recommendation: null,
        currentSong: null,
        queue: [],
      });

      render(<GlobalMusicPlayer />);
      expect(
        within(screen.getByTestId("global-music-mini-bar")).getByText("声音"),
      ).toBeInTheDocument();
    });

    it("renders when there is a persisted recommendation", () => {
      setStoreState({
        activeStoryText: null,
        recommendation: { songs: [{ name: "Test Song", artists: [] }] },
        currentSong: null,
        queue: [],
      });

      render(<GlobalMusicPlayer />);
      // Song name appears in both mini bar and MusicPlayer (always mounted)
      expect(screen.getAllByText("Test Song")[0]).toBeInTheDocument();
    });

    it("renders when there is a currentSong from persisted state", () => {
      setStoreState({
        activeStoryText: null,
        recommendation: null,
        currentSong: { name: "Persisted Song", artists: [] },
        queue: [],
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getAllByText("Persisted Song")[0]).toBeInTheDocument();
    });

    it("renders when queue has songs but no recommendation", () => {
      setStoreState({
        activeStoryText: null,
        recommendation: null,
        currentSong: null,
        queue: [{ name: "Queued Song", artists: [] }],
      });

      render(<GlobalMusicPlayer />);
      expect(
        within(screen.getByTestId("global-music-mini-bar")).getByText("声音"),
      ).toBeInTheDocument();
    });
  });

  describe("Mini player bar", () => {
    it("uses one compact sound console action bar instead of separate music and reading modules", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const console = within(panel).getByRole("group", { name: "声音控制台" });
      const controls = within(console).getByTestId("sound-console-unified-controls");

      expect(within(controls).getByTestId("sound-music-console")).toBeInTheDocument();
      expect(within(controls).getByTestId("story-voice-console")).toBeInTheDocument();
      expect(within(controls).getByRole("button", { name: "播放" })).toBeInTheDocument();
      expect(
        within(controls).getByRole("button", { name: "朗读故事" }),
      ).toBeInTheDocument();
      expect(
        within(controls).getByRole("combobox", { name: "选择朗读声音" }),
      ).toBeInTheDocument();
      expect(
        within(controls).getByRole("checkbox", { name: "自动朗读" }),
      ).toBeInTheDocument();
      expect(within(console).queryByTestId("sound-console-music-slot")).not.toBeInTheDocument();
      expect(within(console).queryByTestId("sound-console-reading-slot")).not.toBeInTheDocument();
      expect(within(console).queryByTestId("sound-music-row")).not.toBeInTheDocument();
      expect(within(console).queryByTestId("sound-reading-row")).not.toBeInTheDocument();
      expect(within(console).queryByText("背景音乐")).not.toBeInTheDocument();
      expect(within(console).queryByText("故事朗读")).not.toBeInTheDocument();
    });

    it("combines music and story reading into one expandable sound panel", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      expect(screen.getByRole("region", { name: "声音" })).toBeInTheDocument();
      expect(
        screen.queryByRole("region", { name: "声音控制" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "展开声音" }),
      ).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      expect(
        screen.getByRole("group", { name: "音乐和朗读" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("region", { name: "声音面板" }),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("sound-control-console")).toBeInTheDocument();
      expect(screen.getByTestId("sound-console-unified-controls")).toBeInTheDocument();
      expect(screen.getByTestId("sound-music-console")).toBeInTheDocument();
      expect(screen.getByTestId("story-voice-console")).toBeInTheDocument();
      expect(
        screen.queryByRole("region", { name: "故事朗读" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("checkbox", { name: "自动朗读" }),
      ).toBeInTheDocument();
    });

    it("presents music and narration as one unified sound panel with embedded channels", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      expect(within(panel).queryByText("声音控制")).not.toBeInTheDocument();
      const console = within(panel).getByTestId("sound-control-console");
      const controls = within(console).getByTestId("sound-console-unified-controls");
      const musicConsole = within(controls).getByTestId("sound-music-console");
      const readingConsole = within(controls).getByTestId("story-voice-console");

      expect(console).toHaveAccessibleName("声音控制台");
      expect(within(musicConsole).getByText("Playing Song")).toBeInTheDocument();
      expect(
        within(readingConsole).getByRole("button", { name: "朗读故事" }),
      ).toBeInTheDocument();
      expect(
        within(readingConsole).getByRole("combobox", { name: "选择朗读声音" }),
      ).toBeInTheDocument();
      expect(
        within(readingConsole).getByRole("checkbox", { name: "自动朗读" }),
      ).toBeInTheDocument();
      expect(
        within(panel).queryByRole("region", { name: "故事朗读" }),
      ).not.toBeInTheDocument();
      expect(musicConsole).not.toHaveClass(
        "bg-card",
      );
      expect(musicConsole).not.toHaveClass(
        "border",
      );
      expect(readingConsole).not.toHaveClass("bg-card");
      expect(readingConsole).not.toHaveClass("border");
    });

    it("keeps the collapsed sound bar to one entry and one combined status", () => {
      setStoreState({
        activeStoryText: "story text",
        isPlaying: true,
        audioElement: {
          pause: jest.fn(),
          play: jest.fn().mockResolvedValue(undefined),
          ended: false,
          currentTime: 0,
        } as unknown as HTMLAudioElement,
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
        readingState: "playing",
      } as never);

      render(<GlobalMusicPlayer />);

      const miniBar = within(screen.getByTestId("global-music-mini-bar"));
      expect(miniBar.getByText("声音")).toBeInTheDocument();
      expect(miniBar.getByTestId("collapsed-sound-status")).toHaveTextContent(
        "音乐播放中 · 朗读中",
      );
      expect(miniBar.queryByTestId("collapsed-sound-summary")).not.toBeInTheDocument();
      expect(miniBar.queryByText("背景音乐")).not.toBeInTheDocument();
      expect(miniBar.queryByText("故事朗读")).not.toBeInTheDocument();
      expect(miniBar.getByRole("button", { name: "暂停音乐" })).toBeInTheDocument();
      expect(miniBar.getByRole("button", { name: "展开声音" })).toBeInTheDocument();
      expect(miniBar.queryByRole("button", { name: "朗读故事" })).not.toBeInTheDocument();
    });

    it("uses one sound mixer with compact vertical channel rows instead of nested cards", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const console = within(panel).getByTestId("sound-control-console");
      const controls = within(console).getByTestId("sound-console-unified-controls");
      const musicConsole = within(controls).getByTestId("sound-music-console");
      const readingConsole = within(controls).getByTestId("story-voice-console");

      expect(controls).toHaveClass("min-w-0");
      expect(musicConsole).not.toHaveClass("rounded-lg");
      expect(readingConsole).not.toHaveClass("rounded-lg");
      expect(musicConsole).not.toHaveClass("rounded-md");
      expect(readingConsole).not.toHaveClass("rounded-md");
    });

    it("combines music and narration into one sound console instead of two section groups", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const console = within(panel).getByTestId("sound-control-console");

      expect(console).toHaveAccessibleName("声音控制台");
      expect(within(console).getByTestId("sound-console-unified-controls")).toBeInTheDocument();
      expect(within(console).getByTestId("sound-music-console")).toBeInTheDocument();
      expect(within(console).getByTestId("story-voice-console")).toBeInTheDocument();
      expect(within(console).queryByText("背景音乐")).not.toBeInTheDocument();
      expect(within(console).queryByText("故事朗读")).not.toBeInTheDocument();
      expect(
        within(console).getByRole("button", { name: "朗读故事" }),
      ).toBeInTheDocument();
      expect(
        within(console).getByRole("combobox", { name: "选择朗读声音" }),
      ).toBeInTheDocument();
      expect(
        within(console).getByRole("checkbox", { name: "自动朗读" }),
      ).toBeInTheDocument();
      expect(
        within(panel).queryByRole("group", { name: "背景音乐" }),
      ).not.toBeInTheDocument();
      expect(
        within(panel).queryByRole("group", { name: "故事朗读" }),
      ).not.toBeInTheDocument();
      expect(within(panel).queryByTestId("sound-channel-list")).not.toBeInTheDocument();
    });

    it("replaces the collapsed mini bar with a panel header while expanded", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      expect(
        screen.queryByTestId("global-music-mini-bar"),
      ).not.toBeInTheDocument();
      expect(
        within(panel).getByRole("button", { name: "收起声音" }),
      ).toBeInTheDocument();
    });

    it("stays below the app header on desktop so it cannot cover header controls or the chat launcher", () => {
      setStoreState({ activeStoryText: "story text" });

      render(<GlobalMusicPlayer />);

      const wrapper = screen.getByTestId("global-music-player");
      expect(wrapper).toHaveClass("top-16");
      expect(wrapper).not.toHaveClass("md:top-auto");
      expect(wrapper).not.toHaveClass("md:bottom-4");
    });

    it("shows song name when currentSong is set", () => {
      setStoreState({
        activeStoryText: "story text",
        currentSong: { name: "My Song", artists: ["Artist A", "Artist B"] },
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getAllByText("My Song")[0]).toBeInTheDocument();
      expect(
        within(screen.getByTestId("global-music-mini-bar")).getByText(
          "My Song · Artist A, Artist B",
        ),
      ).toBeInTheDocument();
    });

    it("labels the collapsed control as sound instead of music-only waiting text", () => {
      setStoreState({
        activeStoryText: "story text",
        recommendation: {
          songs: [],
        },
        currentSong: null,
      });

      render(<GlobalMusicPlayer />);
      const miniBar = within(screen.getByTestId("global-music-mini-bar"));
      expect(miniBar.getByText("声音")).toBeInTheDocument();
      expect(miniBar.getByText("音乐和朗读")).toBeInTheDocument();
      expect(screen.queryByText("等待音乐...")).not.toBeInTheDocument();
    });

    it("shows play button when not playing", () => {
      setStoreState({
        activeStoryText: "story text",
        isPlaying: false,
      });

      render(<GlobalMusicPlayer />);
      const playButton = screen.getAllByRole("button")[0];
      expect(playButton).toBeInTheDocument();
    });

    it("labels the collapsed sound-panel entry for reliable browser automation", () => {
      setStoreState({
        activeStoryText: "story text",
        isPlaying: false,
        audioElement: null,
      });

      render(<GlobalMusicPlayer />);

      expect(
        screen.getByRole("button", { name: "展开声音" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "打开声音" }),
      ).not.toBeInTheDocument();
    });

    it("keeps collapsed narration hidden while exposing a single music playback button", () => {
      setStoreState({
        activeStoryText: "story text",
        isPlaying: true,
        audioElement: {
          pause: jest.fn(),
          play: jest.fn().mockResolvedValue(undefined),
          ended: false,
          currentTime: 0,
        } as unknown as HTMLAudioElement,
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      const miniBar = within(screen.getByTestId("global-music-mini-bar"));
      expect(
        miniBar.getByRole("button", { name: "展开声音" }),
      ).toBeInTheDocument();
      expect(
        miniBar.getByRole("button", { name: "暂停音乐" }),
      ).toBeInTheDocument();
      expect(
        miniBar.queryByRole("button", { name: "朗读故事" }),
      ).not.toBeInTheDocument();
    });

    it("keeps collapsed narration controls inside the expanded sound panel", async () => {
      const user = userEvent.setup();
      const fakeAudio = {
        pause: jest.fn(),
        play: jest.fn().mockResolvedValue(undefined),
        ended: false,
        src: "",
        currentTime: 0,
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
      } as unknown as HTMLAudioElement;
      setStoreState({
        activeStoryText: "story text",
        audioElement: fakeAudio,
        isPlaying: false,
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      const miniBar = within(screen.getByTestId("global-music-mini-bar"));
      expect(
        miniBar.getByRole("button", { name: "展开声音" }),
      ).toBeInTheDocument();
      expect(
        miniBar.getByRole("button", { name: "播放音乐" }),
      ).toBeInTheDocument();
      expect(
        miniBar.queryByRole("button", { name: "朗读故事" }),
      ).not.toBeInTheDocument();

      await user.click(miniBar.getByRole("button", { name: "展开声音" }));

      const readingSection = screen.getByTestId("story-voice-console");
      expect(
        within(readingSection).getByRole("button", { name: "朗读故事" }),
      ).toBeInTheDocument();
    });

    it("offers to open music when a persisted song has not initialized audio yet", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: null,
        audioElement: null,
        currentSong: {
          id: 9101,
          name: "全局音乐夹具",
          artists: ["测试"],
          album: "回归夹具",
          duration: 120,
        },
      });

      render(<GlobalMusicPlayer />);

      const miniBar = within(screen.getByTestId("global-music-mini-bar"));
      expect(
        miniBar.getByRole("button", { name: "打开音乐" }),
      ).toBeInTheDocument();
      expect(
        miniBar.queryByRole("button", { name: "朗读故事" }),
      ).not.toBeInTheDocument();

      await user.click(miniBar.getByRole("button", { name: "打开音乐" }));

      expect(
        screen.getByRole("group", { name: "音乐和朗读" }),
      ).toBeInTheDocument();
      expect(togglePlaySpy).not.toHaveBeenCalled();
    });

    it("does not use explanatory copy inside the sound panel", async () => {
      const user = userEvent.setup();
      setStoreState({ activeStoryText: "story text" });

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      expect(
        screen.getByRole("group", { name: "音乐和朗读" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByText("场景音乐和故事朗读统一在这里控制"),
      ).not.toBeInTheDocument();
    });

    it("uses concise sound channel labels without a redundant expanded header", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      expect(within(panel).queryByText("声音控制")).not.toBeInTheDocument();
      expect(within(panel).queryByText("场景音乐")).not.toBeInTheDocument();
      expect(
        within(panel).queryByRole("heading", { name: "音乐", level: 3 }),
      ).not.toBeInTheDocument();
      expect(
        within(panel).queryByRole("heading", { name: "朗读", level: 3 }),
      ).not.toBeInTheDocument();
      expect(within(panel).getByTestId("sound-control-console")).toBeInTheDocument();
      expect(within(panel).getByTestId("sound-console-unified-controls")).toBeInTheDocument();
      expect(within(panel).getByTestId("sound-music-console")).toBeInTheDocument();
      expect(within(panel).getByTestId("story-voice-console")).toBeInTheDocument();
    });

    it("presents the expanded controls as one sound mixer with semantic channel headings and combined status", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
        isPlaying: true,
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: false,
        readingState: "playing",
        autoReadEnabled: true,
      } as never);
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url.includes("/voice-reading/settings")) {
          return Promise.resolve(
            jsonResponse({
              auto_read_enabled: true,
              selected_voice_color: "warm_female",
            }),
          );
        }
        return Promise.resolve(jsonResponse({}));
      });

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const overview = within(panel).getByTestId("sound-mixer-overview");
      expect(overview).toHaveTextContent("声音");
      expect(overview).toHaveTextContent("音乐播放中");
      expect(overview).toHaveTextContent("朗读中");
      expect(overview).not.toHaveTextContent("自动朗读");
      expect(overview).not.toHaveTextContent("手动朗读");

      expect(within(panel).getByTestId("sound-control-console")).toBeInTheDocument();
      expect(within(panel).getByTestId("sound-console-unified-controls")).toBeInTheDocument();
      expect(within(panel).getByTestId("sound-music-console")).toBeInTheDocument();
      expect(within(panel).getByTestId("story-voice-console")).toBeInTheDocument();
    });

    it("uses a single combined status line in the sound header instead of separate status pills", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
        isPlaying: true,
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
        readingState: "playing",
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const status = within(panel).getByTestId("sound-mixer-status");
      expect(status).toHaveTextContent("音乐播放中");
      expect(status).toHaveTextContent("朗读中");
      expect(status).toHaveTextContent("·");
      expect(within(panel).queryAllByTestId("sound-status-pill")).toHaveLength(0);
    });

    it("does not duplicate music and narration status badges inside each channel", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
        isPlaying: true,
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: false,
        readingState: "playing",
        autoReadEnabled: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const status = within(panel).getByTestId("sound-mixer-status");
      expect(status).toHaveTextContent("音乐播放中");
      expect(status).toHaveTextContent("朗读中");
      expect(within(panel).queryAllByTestId("sound-status-pill")).toHaveLength(0);
      expect(within(panel).getAllByText("自动朗读")).toHaveLength(1);
      expect(within(panel).queryByText("手动朗读")).not.toBeInTheDocument();
      expect(within(panel).getByTestId("sound-control-console")).toBeInTheDocument();
      expect(within(panel).getByTestId("sound-music-console")).toBeInTheDocument();
      expect(within(panel).getByTestId("story-voice-console")).toBeInTheDocument();
    });

    it("merges music and read-aloud into one compact sound console without duplicate module headings", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
        isPlaying: true,
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
        readingState: "playing",
        autoReadEnabled: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const console = within(panel).getByTestId("sound-control-console");
      const controls = within(console).getByTestId("sound-console-unified-controls");
      expect(controls).toHaveClass("min-w-0");

      const musicChannel = within(console).getByTestId("sound-music-console");
      const readingChannel = within(console).getByTestId("story-voice-console");

      expect(within(musicChannel).getByText("Playing Song")).toBeInTheDocument();
      expect(within(readingChannel).getByRole("button", { name: /朗读/ })).toBeInTheDocument();
      expect(
        within(panel).queryByRole("heading", { name: "音乐", level: 3 }),
      ).not.toBeInTheDocument();
      expect(
        within(panel).queryByRole("heading", { name: "朗读", level: 3 }),
      ).not.toBeInTheDocument();
      expect(
        within(panel).queryByRole("region", { name: "故事朗读" }),
      ).not.toBeInTheDocument();
    });

    it("uses one compact vertical sound panel instead of two nested audio cards", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
        recommendation: {
          mood: "平静",
          environment: "城市",
          story_style: "现代",
          songs: [
            {
              id: 2,
              name: "Playing Song",
              artists: ["Artist"],
              album: "",
              duration: 200,
            },
            {
              id: 3,
              name: "Queued Song",
              artists: ["Artist"],
              album: "",
              duration: 200,
            },
          ],
        },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const console = within(panel).getByTestId("sound-control-console");
      expect(console).toBeInTheDocument();
      expect(within(panel).queryByTestId("sound-mixer-grid")).not.toBeInTheDocument();

      const musicSection = within(console).getByTestId("sound-music-console");
      const readingSection = within(console).getByTestId("story-voice-console");
      expect(musicSection).not.toHaveClass("rounded-md");
      expect(readingSection).not.toHaveClass("rounded-md");
      expect(within(console).queryByTestId("sound-inline-reading-controls")).not.toBeInTheDocument();
      expect(within(musicSection).queryByText(/推荐歌曲/)).not.toBeInTheDocument();
      expect(within(musicSection).queryByText("平静")).not.toBeInTheDocument();
      expect(within(musicSection).queryByText("城市")).not.toBeInTheDocument();
      expect(within(readingSection).getByRole("button", { name: "朗读故事" })).toBeInTheDocument();
      expect(within(readingSection).getByRole("combobox", { name: "选择朗读声音" })).toBeInTheDocument();
      expect(within(readingSection).getByRole("checkbox", { name: "自动朗读" })).toBeInTheDocument();
    });

    it("shows persisted current music inside the expanded music section", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: null,
        recommendation: null,
        currentSong: {
          id: 9101,
          name: "全局音乐夹具",
          artists: ["测试"],
          album: "回归夹具",
          duration: 120,
          source: "netease",
        },
      });

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      const musicSection = screen.getByTestId("sound-music-console");
      expect(
        within(musicSection).getByText("全局音乐夹具"),
      ).toBeInTheDocument();
      expect(
        within(musicSection).getByText("测试 · 回归夹具"),
      ).toBeInTheDocument();
    });

    it("shows pause button when playing", () => {
      setStoreState({
        activeStoryText: "story text",
        isPlaying: true,
      });

      render(<GlobalMusicPlayer />);
      const playPauseButton = screen.getAllByRole("button")[0];
      expect(playPauseButton).toBeInTheDocument();
    });
  });

  describe("Collapsed sound panel interaction", () => {
    it("uses the collapsed playback button for music without opening the panel", async () => {
      const user = userEvent.setup();
      const fakeAudio = {
        pause: jest.fn(),
        play: jest.fn().mockResolvedValue(undefined),
        ended: false,
        src: "",
        currentTime: 0,
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
      } as unknown as HTMLAudioElement;
      setStoreState({
        activeStoryText: "story text",
        audioElement: fakeAudio,
        isPlaying: false,
      });

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "播放音乐" }));

      expect(togglePlaySpy).toHaveBeenCalledTimes(1);
      expect(
        screen.queryByRole("group", { name: "音乐和朗读" }),
      ).not.toBeInTheDocument();
    });

    it("does not treat collapsed song text as an implicit expand target", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        audioElement: null,
        isPlaying: false,
        recommendation: { songs: [{ name: "Song", artists: [] }] },
      });

      render(<GlobalMusicPlayer />);

      await user.click(
        within(screen.getByTestId("global-music-mini-bar")).getByText("Song"),
      );

      expect(
        screen.queryByRole("group", { name: "音乐和朗读" }),
      ).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      expect(
        screen.getByRole("group", { name: "音乐和朗读" }),
      ).toBeInTheDocument();
    });
  });

  describe("Expand/Collapse", () => {
    it("does not fetch a new recommendation while collapsed", () => {
      setStoreState({ activeStoryText: "story text", recommendation: null });

      render(<GlobalMusicPlayer />);

      expect(fetchMusicRecommendation).not.toHaveBeenCalled();
    });

    it("shows chevron up icon in collapsed state", () => {
      setStoreState({ activeStoryText: "story text" });

      render(<GlobalMusicPlayer />);
      expect(
        screen.getByRole("button", { name: "展开声音" }),
      ).toBeInTheDocument();
    });

    it("toggles expanded state from the explicit sound expand button", async () => {
      const user = userEvent.setup();
      setStoreState({ activeStoryText: "story text" });

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音" }));

      expect(
        screen.getByRole("group", { name: "音乐和朗读" }),
      ).toBeInTheDocument();
    });
  });

  describe("Progress bar", () => {
    it("shows 0% progress when duration is 0", () => {
      setStoreState({
        activeStoryText: "story text",
        currentTime: 30,
        duration: 0,
      });

      render(<GlobalMusicPlayer />);
      // Component should render without errors
      expect(
        within(screen.getByTestId("global-music-mini-bar")).getByText("声音"),
      ).toBeInTheDocument();
    });

    it("calculates progress percentage correctly", () => {
      setStoreState({
        activeStoryText: "story text",
        currentTime: 30,
        duration: 120,
      });

      render(<GlobalMusicPlayer />);
      const progressBar = screen.getByTestId("global-sound-progress");
      expect(progressBar).toHaveStyle({ width: "25%" });
    });
  });

  describe("LocalStorage initialization", () => {
    it("attempts to load playlist on mount when gameId is in localStorage", () => {
      localStorage.setItem("gameId", "42");
      setStoreState({
        activeStoryText: "story text",
      });

      render(<GlobalMusicPlayer />);

      expect(loadPlaylistSpy).toHaveBeenCalledWith(42);
    });

    it("does not load playlist when no gameId in localStorage", () => {
      setStoreState({
        activeStoryText: "story text",
      });

      render(<GlobalMusicPlayer />);

      expect(loadPlaylistSpy).not.toHaveBeenCalled();
    });

    it("does not load playlist on re-render (ref guard)", () => {
      localStorage.setItem("gameId", "42");
      setStoreState({
        activeStoryText: "story text",
      });

      const { rerender } = render(<GlobalMusicPlayer />);
      rerender(<GlobalMusicPlayer />);

      // Should only be called once due to ref guard
      expect(loadPlaylistSpy).toHaveBeenCalledTimes(1);
    });
  });

  describe("Song display with recommendation fallback", () => {
    it("shows recommendation song name when no currentSong is set", () => {
      setStoreState({
        activeStoryText: "story text",
        recommendation: {
          songs: [
            { id: 1, name: "Rec Song", artists: [], album: "", duration: 180 },
          ],
        },
        currentSong: null,
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getAllByText("Rec Song")[0]).toBeInTheDocument();
    });

    it("prioritizes currentSong over recommendation", () => {
      setStoreState({
        activeStoryText: "story text",
        recommendation: {
          songs: [
            { id: 1, name: "Rec Song", artists: [], album: "", duration: 180 },
          ],
        },
        currentSong: {
          id: 2,
          name: "Playing Song",
          artists: ["Artist"],
          album: "",
          duration: 200,
        },
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getAllByText("Playing Song")[0]).toBeInTheDocument();
      expect(screen.queryByText("Rec Song")).not.toBeInTheDocument();
    });
  });
});
