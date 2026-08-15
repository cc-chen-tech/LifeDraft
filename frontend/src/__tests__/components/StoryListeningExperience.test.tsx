import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { StoryListeningExperience } from "@/components/game/StoryListeningExperience";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    voice_reading: {
      getSettings: jest.fn(),
      updateSettings: jest.fn(),
      requestReading: jest.fn(),
      getJob: jest.fn(),
      getProgress: jest.fn(),
      updateProgress: jest.fn(),
    },
  },
}));

jest.mock("@/lib/storyVoiceTextHash", () => ({
  storyVoiceTextToHash: jest.fn().mockResolvedValue("chapter-text-hash"),
}));

const voiceApi = api.voice_reading as jest.Mocked<typeof api.voice_reading>;

const context = {
  source_type: "current_story" as const,
  game_id: 42,
  week: 2,
  round_number: 1,
  stage: "event",
  attempt_id: "day-7",
  day_index: 7,
  story_date: "2026-08-15",
  text_hash: "pending-client-hash",
  text: "第一段故事。\n\n第二段故事。",
};

const segments = [
  {
    paragraph_index: 0,
    status: "ready",
    audio_url: "/api/voice-reading/audio/first.mp3",
    asset_id: 1,
    duration_ms: 4_000,
    media_type: "audio/mpeg",
  },
  {
    paragraph_index: 1,
    status: "ready",
    audio_url: "/api/voice-reading/audio/second.mp3",
    asset_id: 2,
    duration_ms: 5_000,
    media_type: "audio/mpeg",
  },
];

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function setupApi() {
  voiceApi.getSettings.mockResolvedValue({
    member_required: false,
    enabled: true,
    available_voice_colors: ["warm_female", "calm_male", "clear_neutral"],
    selected_voice_color: "warm_female",
    selected_speed: 1,
    uploaded_voice_available: false,
    auto_read_enabled: true,
    tts_provider: "minimax",
    tts_model: "speech-02-turbo",
    tts_provider_available: true,
    backend_audio_enabled: true,
    playback_mode: "audio",
  });
  voiceApi.updateSettings.mockResolvedValue({} as never);
  voiceApi.requestReading.mockResolvedValue({
    job_id: 19,
    status: "queued",
    playback_mode: "unavailable",
    provider: "minimax",
    model: "speech-02-turbo",
    message: "",
    segments: segments.map((segment) => ({ ...segment, status: "queued", audio_url: null })),
  });
  voiceApi.getJob.mockResolvedValue({
    job_id: 19,
    status: "ready",
    playback_mode: "audio",
    provider: "minimax",
    model: "speech-02-turbo",
    message: "",
    segments,
  });
  voiceApi.getProgress.mockRejectedValue(Object.assign(new Error("not found"), { status: 404 }));
  voiceApi.updateProgress.mockResolvedValue({} as never);
}

describe("StoryListeningExperience", () => {
  const play = jest.fn().mockResolvedValue(undefined);
  const pause = jest.fn();
  const load = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "info").mockImplementation();
    setupApi();
    Object.defineProperty(HTMLMediaElement.prototype, "play", { configurable: true, value: play });
    Object.defineProperty(HTMLMediaElement.prototype, "pause", { configurable: true, value: pause });
    Object.defineProperty(HTMLMediaElement.prototype, "load", { configurable: true, value: load });
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  function renderExperience(onSelectChoice = jest.fn()) {
    const view = render(
      <StoryListeningExperience
        context={context}
        storyText={context.text}
        dateTitle="公元 2026 年 8 月 15 日"
        dayNumber={8}
        totalDays={365}
        options={[{ text: "推开那扇门" }, { text: "留在原地" }]}
        onSelectChoice={onSelectChoice}
      />,
    );
    return { ...view, onSelectChoice };
  }

  it("queues the completed chapter and automatically starts high-quality audio", async () => {
    renderExperience();

    expect(await screen.findByRole("heading", { name: "听故事" })).toBeInTheDocument();
    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);
    await waitFor(() => expect(play).toHaveBeenCalled());
    expect(screen.queryByText("浏览器语音")).not.toBeInTheDocument();
  });

  it("lets the listener start from a selected paragraph", async () => {
    renderExperience();
    const transcriptLabel = await screen.findByText("查看正文");
    fireEvent.click(transcriptLabel.closest("button") as HTMLButtonElement);
    const secondParagraph = await screen.findByRole("button", {
      name: "从第 2 段开始朗读",
    });

    fireEvent.click(secondParagraph);
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);

    expect(secondParagraph).toHaveAttribute("aria-current", "true");
    await waitFor(() => expect(play).toHaveBeenCalled());
  });

  it("stops narration immediately when a daily choice is selected", async () => {
    const { onSelectChoice } = renderExperience();
    await screen.findByRole("button", { name: /推开那扇门/ });
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);
    await waitFor(() => expect(play).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /推开那扇门/ }));

    expect(pause).toHaveBeenCalled();
    expect(onSelectChoice).toHaveBeenCalledWith(0);
  });

  it("retries a failed high-quality narration job", async () => {
    voiceApi.requestReading
      .mockResolvedValueOnce({
        job_id: 20,
        status: "failed",
        playback_mode: "unavailable",
        provider: "minimax",
        model: "speech-02-turbo",
        error_code: "tts_generation_failed",
        message: "高质量语音生成失败",
        segments: [{ ...segments[0], status: "failed", audio_url: null }],
      })
      .mockResolvedValueOnce({
        job_id: 20,
        status: "ready",
        playback_mode: "audio",
        provider: "minimax",
        model: "speech-02-turbo",
        message: "",
        segments,
      });

    renderExperience();

    fireEvent.click(await screen.findByRole("button", { name: "重试高质量语音" }));

    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(2));
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);
    await waitFor(() => expect(play).toHaveBeenCalled());
  });

  it("restores the saved paragraph and in-paragraph position", async () => {
    voiceApi.getProgress.mockResolvedValue({
      game_id: context.game_id,
      day_index: context.day_index,
      story_date: context.story_date,
      text_hash: "chapter-text-hash",
      voice_id: "warm_female",
      speed: 1,
      paragraph_index: 1,
      position_ms: 2_000,
      completed: false,
      updated_at: "2026-08-15T12:00:00",
    });

    renderExperience();

    const transcriptLabel = await screen.findByText("查看正文");
    fireEvent.click(transcriptLabel.closest("button") as HTMLButtonElement);
    const secondParagraph = await screen.findByRole("button", {
      name: "从第 2 段开始朗读",
    });

    await waitFor(() => expect(secondParagraph).toHaveAttribute("aria-current", "true"));
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);
    await waitFor(() => expect(play).toHaveBeenCalled());
  });

  it("respects a disabled next-chapter auto-read setting", async () => {
    voiceApi.getSettings.mockResolvedValue({
      ...(await voiceApi.getSettings()),
      auto_read_enabled: false,
    });

    renderExperience();

    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    expect(play).not.toHaveBeenCalled();
    expect(screen.getByRole("checkbox", { name: "下一章自动播放" })).not.toBeChecked();
  });

  it("shows a one-tap action when the browser blocks automatic playback", async () => {
    play.mockRejectedValueOnce(new Error("autoplay blocked"));
    renderExperience();

    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);

    expect(await screen.findByText("点击播放，开启自动朗读")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));

    await waitFor(() => expect(play).toHaveBeenCalledTimes(2));
  });

  it("persists voice and speed changes before rebuilding the chapter audio", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("音色"), { target: { value: "calm_male" } });
    fireEvent.change(screen.getByLabelText("语速"), { target: { value: "1.25" } });

    expect(voiceApi.updateSettings).toHaveBeenCalledWith({ selected_voice_color: "calm_male" });
    expect(voiceApi.updateSettings).toHaveBeenCalledWith({ selected_speed: 1.25 });
    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(3));
  });

  it("waits for metadata before applying a cross-paragraph seek and refines chapter duration from the media", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));

    const firstAudio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(firstAudio, "currentTime", { configurable: true, writable: true, value: 0 });

    fireEvent.change(screen.getByLabelText("朗读进度"), { target: { value: "5000" } });

    expect(firstAudio.currentTime).toBe(0);
    await waitFor(() => expect((document.querySelector("audio") as HTMLAudioElement).getAttribute("src")).toBe("/api/voice-reading/audio/second.mp3"));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "duration", { configurable: true, value: 6 });

    fireEvent.loadedMetadata(audio);

    expect(audio.currentTime).toBe(1);
    expect(screen.getByLabelText("朗读进度")).toHaveAttribute("max", "10000");
  });

  it("recovers one stalled paragraph after exactly eight seconds, then offers a manual continuation", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "currentTime", { configurable: true, writable: true, value: 1.75 });

    fireEvent.stalled(audio);
    await act(async () => {
      jest.advanceTimersByTime(7_999);
    });
    expect(load).not.toHaveBeenCalled();

    await act(async () => {
      jest.advanceTimersByTime(1);
    });
    expect(load).toHaveBeenCalledTimes(1);
    expect(play).not.toHaveBeenCalled();
    Object.defineProperty(audio, "duration", { configurable: true, value: 10 });
    fireEvent.loadedMetadata(audio);
    expect(audio.currentTime).toBe(1.75);
    fireEvent.canPlay(audio);
    await waitFor(() => expect(play).toHaveBeenCalledTimes(1));

    fireEvent.stalled(audio);
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(await screen.findByRole("button", { name: "网络不稳定，继续朗读" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "网络不稳定，继续朗读" }));
    expect(load).toHaveBeenCalledTimes(2);
    expect(play).toHaveBeenCalledTimes(2);
    fireEvent.loadedMetadata(audio);
    expect(audio.currentTime).toBe(1.75);
    fireEvent.canPlay(audio);
    expect(play).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });

  it("does not postpone the eight-second watchdog when waiting, error, and stalled repeat", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.waiting(audio);
    await act(async () => {
      jest.advanceTimersByTime(4_000);
    });
    fireEvent.error(audio);
    fireEvent.stalled(audio);
    await act(async () => {
      jest.advanceTimersByTime(3_999);
    });
    expect(load).not.toHaveBeenCalled();

    await act(async () => {
      jest.advanceTimersByTime(1);
    });
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("starts only one play request when canplay fires repeatedly", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.canPlay(audio);
    fireEvent.playing(audio);
    fireEvent.canPlay(audio);

    expect(play).toHaveBeenCalledTimes(1);
  });

  it("pauses delayed playback and ignores old-source canplay after changing paragraphs", async () => {
    const delayedPlay = deferred<void>();
    play.mockImplementationOnce(() => delayedPlay.promise);
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const firstAudio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.canPlay(firstAudio);
    expect(play).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("查看正文").closest("button") as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "从第 2 段开始朗读" }));
    await waitFor(() => expect((document.querySelector("audio") as HTMLAudioElement).getAttribute("src")).toBe("/api/voice-reading/audio/second.mp3"));

    pause.mockClear();
    fireEvent.canPlay(firstAudio);
    await act(async () => {
      delayedPlay.resolve();
    });

    expect(play).toHaveBeenCalledTimes(1);
    expect(pause).toHaveBeenCalledTimes(1);
  });

  it("pauses delayed playback after a daily choice or unmount", async () => {
    const choicePlay = deferred<void>();
    play.mockImplementationOnce(() => choicePlay.promise);
    const { onSelectChoice, unmount } = renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.canPlay(audio);
    expect(play).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /推开那扇门/ }));
    expect(onSelectChoice).toHaveBeenCalledWith(0);
    pause.mockClear();
    fireEvent.canPlay(audio);
    await act(async () => {
      choicePlay.resolve();
    });
    expect(play).toHaveBeenCalledTimes(1);
    expect(pause).toHaveBeenCalledTimes(1);

    const unmountPlay = deferred<void>();
    play.mockImplementationOnce(() => unmountPlay.promise);
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));
    expect(play).toHaveBeenCalledTimes(2);
    unmount();
    pause.mockClear();
    await act(async () => {
      unmountPlay.resolve();
    });
    expect(pause).toHaveBeenCalledTimes(1);
  });

  it("does not reload when a short waiting period returns to playing", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.waiting(audio);
    await act(async () => {
      jest.advanceTimersByTime(2_000);
    });
    fireEvent.playing(audio);
    await act(async () => {
      jest.advanceTimersByTime(6_000);
    });

    expect(load).not.toHaveBeenCalled();
    jest.useRealTimers();
  });

  it("moves to the next paragraph when the current MiniMax audio ends", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.ended(audio);

    expect(await screen.findByText("第 2 段")).toBeInTheDocument();
    expect(document.querySelector("audio")).toHaveAttribute("src", "/api/voice-reading/audio/second.mp3");
  });

  it("cancels a pending recovery when the listener selects a daily choice", async () => {
    jest.useFakeTimers();
    const { onSelectChoice } = renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.waiting(audio);
    fireEvent.click(await screen.findByRole("button", { name: /推开那扇门/ }));
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(onSelectChoice).toHaveBeenCalledWith(0);
    expect(load).not.toHaveBeenCalled();
    jest.useRealTimers();
  });

  it("cancels a pending recovery when the listening experience unmounts", async () => {
    jest.useFakeTimers();
    const { unmount } = renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.waiting(audio);
    unmount();
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).not.toHaveBeenCalled();
    jest.useRealTimers();
  });
});
