/**
 * GlobalMusicPlayer Component Tests
 * Tests the global music player wrapper with store integration
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock useMusicStore
const mockLoadPlaylist = jest.fn().mockResolvedValue(undefined);
const mockTogglePlay = jest.fn();

jest.mock("@/stores/useMusicStore", () => ({
  useMusicStore: jest.fn(),
}));

// Mock MusicPlayer child component
jest.mock("@/components/game/MusicPlayer", () => ({
  MusicPlayer: ({ storyText, gameId, className }: {
    storyText: string;
    gameId?: number;
    className?: string;
  }) => (
    <div data-testid="music-player" data-story-text={storyText} data-game-id={gameId}>
      MusicPlayer Content
    </div>
  ),
}));

import { useMusicStore } from "@/stores/useMusicStore";
import { GlobalMusicPlayer } from "@/components/game/GlobalMusicPlayer";

const mockUseMusicStore = useMusicStore as jest.MockedFunction<typeof useMusicStore>;

function setStoreState(overrides: Record<string, unknown> = {}) {
  mockUseMusicStore.mockImplementation((selector: (s: Record<string, unknown>) => unknown) => {
    const state = {
      loadPlaylist: mockLoadPlaylist,
      playlistGameId: null,
      currentSong: null,
      queue: [],
      recommendation: null,
      activeStoryText: null,
      activeGameId: null,
      isPlaying: false,
      togglePlay: mockTogglePlay,
      currentTime: 0,
      duration: 0,
      audioElement: null,
      ...overrides,
    };
    return selector(state);
  });
}

describe("GlobalMusicPlayer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
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
      // Recommendation provides song name fallback when no currentSong
      expect(screen.getByText("Test Song")).toBeInTheDocument();
    });

    it("renders when there is a currentSong from persisted state", () => {
      setStoreState({
        activeStoryText: null,
        recommendation: null,
        currentSong: { name: "Persisted Song", artists: [] },
        queue: [],
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getByText("Persisted Song")).toBeInTheDocument();
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
    it("shows song name when currentSong is set", () => {
      setStoreState({
        activeStoryText: "story text",
        currentSong: { name: "My Song", artists: ["Artist A", "Artist B"] },
      });

      render(<GlobalMusicPlayer />);
      expect(screen.getByText("My Song")).toBeInTheDocument();
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
      setStoreState({
        activeStoryText: "story text",
        audioElement: {} as HTMLAudioElement,
        isPlaying: false,
      });

      render(<GlobalMusicPlayer />);

      const playPauseButton = screen.getAllByRole("button")[0];
      await user.click(playPauseButton);

      expect(mockTogglePlay).toHaveBeenCalled();
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

      // Initially hidden via opacity-0/h-0
      expect(screen.getByTestId("music-player")).toBeInTheDocument();

      const playPauseButton = screen.getAllByRole("button")[0];
      await user.click(playPauseButton);

      // Player should still be in the document (always mounted)
      expect(screen.getByTestId("music-player")).toBeInTheDocument();
    });
  });

  describe("Expand/Collapse", () => {
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

      // MusicPlayer should still be present (always mounted)
      expect(screen.getByTestId("music-player")).toBeInTheDocument();
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

      expect(mockLoadPlaylist).toHaveBeenCalledWith(42);
    });

    it("does not load playlist when no gameId in localStorage", () => {
      setStoreState({
        activeStoryText: "story text",
      });

      render(<GlobalMusicPlayer />);

      expect(mockLoadPlaylist).not.toHaveBeenCalled();
    });

    it("does not load playlist on re-render (ref guard)", () => {
      localStorage.setItem("gameId", "42");
      setStoreState({
        activeStoryText: "story text",
      });

      const { rerender } = render(<GlobalMusicPlayer />);
      rerender(<GlobalMusicPlayer />);

      // Should only be called once due to ref guard
      expect(mockLoadPlaylist).toHaveBeenCalledTimes(1);
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
      expect(screen.getByText("Rec Song")).toBeInTheDocument();
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
      expect(screen.getByText("Playing Song")).toBeInTheDocument();
      expect(screen.queryByText("Rec Song")).not.toBeInTheDocument();
    });
  });
});
