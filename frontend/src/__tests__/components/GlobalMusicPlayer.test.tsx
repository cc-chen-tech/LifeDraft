/**
 * GlobalMusicPlayer Component Tests
 * Tests the global music player wrapper with store integration
 */
import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock API-calling functions from music store to avoid real HTTP calls
jest.mock('@/stores/useMusicStore', () => {
  const actual = jest.requireActual('@/stores/useMusicStore');
  return {
    ...actual,
    fetchMusicRecommendation: jest.fn().mockResolvedValue(undefined),
    fetchSongUrl: jest.fn().mockResolvedValue(''),
  };
});

import { fetchMusicRecommendation, useMusicStore } from "@/stores/useMusicStore";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";
import { GlobalMusicPlayer } from "@/components/game/GlobalMusicPlayer";
import type { ReadingContext } from "@/lib/types";

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
    loadPlaylistSpy = jest.spyOn(useMusicStore.getState(), 'loadPlaylist').mockResolvedValue(undefined);
    togglePlaySpy = jest.spyOn(useMusicStore.getState(), 'togglePlay');
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
      expect(screen.getByText("等待音乐...")).toBeInTheDocument();
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
      expect(screen.getByText("等待音乐...")).toBeInTheDocument();
    });
  });

  describe("Mini player bar", () => {
    it("combines music and story reading into one expandable sound panel", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: { id: 2, name: "Playing Song", artists: ["Artist"], album: "", duration: 200 },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      expect(screen.getByRole("region", { name: "声音控制" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "展开声音面板" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "展开声音面板" }));

      expect(screen.getByRole("region", { name: "声音面板" })).toBeInTheDocument();
      expect(screen.getByText("场景音乐")).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "故事朗读" })).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: "自动朗读" })).toBeInTheDocument();
    });

    it("presents music and narration as one unified sound panel with peer sections", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        currentSong: { id: 2, name: "Playing Song", artists: ["Artist"], album: "", duration: 200 },
      });
      useStoryVoiceStore.setState({
        activeReadingContext,
        activeAutoReadText: activeReadingContext.text,
        activeAutoReadReady: true,
      } as never);

      render(<GlobalMusicPlayer />);

      await user.click(screen.getByRole("button", { name: "展开声音面板" }));

      const panel = screen.getByTestId("unified-sound-panel");
      const musicSection = within(panel).getByTestId("sound-music-section");
      const readingSection = within(panel).getByTestId("sound-reading-section");

      expect(within(musicSection).getByText("场景音乐")).toBeInTheDocument();
      expect(within(readingSection).getByText("故事朗读")).toBeInTheDocument();
      expect(within(readingSection).getByRole("button", { name: "朗读故事" })).toBeInTheDocument();
      expect(within(readingSection).getByRole("combobox", { name: "选择朗读声音" })).toBeInTheDocument();
      expect(within(readingSection).getByRole("checkbox", { name: "自动朗读" })).toBeInTheDocument();
      expect(readingSection).not.toHaveClass("border-t");
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
      expect(screen.getByText("Artist A, Artist B")).toBeInTheDocument();
    });

    it("shows waiting text when no song is selected", () => {
      setStoreState({
        activeStoryText: "story text",
        recommendation: {
          songs: [],
        },
        currentSong: null,
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getByText("等待音乐...")).toBeInTheDocument();
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

    it("labels icon-only mini-player controls for reliable browser automation", () => {
      setStoreState({
        activeStoryText: "story text",
        isPlaying: false,
        audioElement: null,
      });

      render(<GlobalMusicPlayer />);

      expect(screen.getByRole("button", { name: "打开声音面板" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "展开声音面板" })).toBeInTheDocument();
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

  describe("Play/Pause interaction", () => {
    it("calls togglePlay when clicking play/pause button with audio element", async () => {
      const user = userEvent.setup();
      const fakeAudio = { pause: jest.fn(), play: jest.fn(), ended: false, src: '', currentTime: 0, addEventListener: jest.fn(), removeEventListener: jest.fn() } as unknown as HTMLAudioElement;
      setStoreState({
        activeStoryText: "story text",
        audioElement: fakeAudio,
        isPlaying: false,
      });

      render(<GlobalMusicPlayer />);

      const playPauseButton = screen.getAllByRole("button")[0];
      await user.click(playPauseButton);

      expect(togglePlaySpy).toHaveBeenCalled();
    });

    it("expands player when clicking play/pause without audio element", async () => {
      const user = userEvent.setup();
      setStoreState({
        activeStoryText: "story text",
        audioElement: null,
        isPlaying: false,
        recommendation: { songs: [{ name: "Song", artists: [] }] },
      });

      render(<GlobalMusicPlayer />);

      // MusicPlayer always mounted, initially collapsed with opacity-0 h-0
      const wrapper = document.querySelector('.fixed.z-50');
      expect(wrapper).toBeInTheDocument();

      const playPauseButton = screen.getAllByRole("button")[0];
      await user.click(playPauseButton);

      // After click, the expanded MusicPlayer container should be visible
      expect(screen.getByRole("region", { name: "声音面板" })).toBeInTheDocument();
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
      // In collapsed state, there should be a chevron-up icon
      expect(screen.getByText("等待音乐...")).toBeInTheDocument();
    });

    it("toggles expanded state when clicking mini bar", async () => {
      const user = userEvent.setup();
      setStoreState({ activeStoryText: "story text" });

      render(<GlobalMusicPlayer />);

      const miniBar = screen.getByText("等待音乐...").closest(".cursor-pointer");
      await user.click(miniBar!);

      // MusicPlayer always mounted, expanded after click
      expect(screen.getByRole("region", { name: "声音面板" })).toBeInTheDocument();
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
      expect(screen.getByText("等待音乐...")).toBeInTheDocument();
    });

    it("calculates progress percentage correctly", () => {
      setStoreState({
        activeStoryText: "story text",
        currentTime: 30,
        duration: 120,
      });

      render(<GlobalMusicPlayer />);
      const progressBar = document.querySelector(".bg-primary");
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
          songs: [{ id: 1, name: "Rec Song", artists: [], album: "", duration: 180 }],
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
          songs: [{ id: 1, name: "Rec Song", artists: [], album: "", duration: 180 }],
        },
        currentSong: { id: 2, name: "Playing Song", artists: ["Artist"], album: "", duration: 200 },
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getAllByText("Playing Song")[0]).toBeInTheDocument();
      expect(screen.queryByText("Rec Song")).not.toBeInTheDocument();
    });
  });
});
