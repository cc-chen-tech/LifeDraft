import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import {
  StoryListeningExperience,
} from "@/components/game/StoryListeningExperience";
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
    audio_url: "/api/voice-reading/audio/chapter.mp3",
    asset_id: 1,
    duration_ms: 4_000,
    start_ms: 0,
    end_ms: 4_000,
    media_type: "audio/mpeg",
  },
  {
    paragraph_index: 1,
    status: "ready",
    audio_url: "/api/voice-reading/audio/chapter.mp3",
    asset_id: 1,
    duration_ms: 5_000,
    start_ms: 4_000,
    end_ms: 9_000,
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
    tts_model: "speech-2.8-turbo",
    tts_provider_available: true,
    backend_audio_enabled: true,
    playback_mode: "audio",
    voice_catalog: [
      {
        voice_id: "female-shaonv",
        label: "少女音色",
        language: "普通话",
        group: "标准音色",
        recommended: true,
      },
      {
        voice_id: "male-qn-qingse",
        label: "青涩青年音色",
        language: "普通话",
        group: "标准音色",
        recommended: true,
      },
      {
        voice_id: "female-yujie",
        label: "御姐音色",
        language: "普通话",
        group: "标准音色",
        recommended: true,
      },
      {
        voice_id: "female-chengshu",
        label: "成熟女性音色",
        language: "普通话",
        group: "标准音色",
        recommended: true,
      },
      {
        voice_id: "Chinese (Mandarin)_Gentleman",
        label: "温润男声",
        language: "普通话",
        group: "主播与叙事",
        recommended: false,
      },
      {
        voice_id: "Cantonese_GentleLady",
        label: "温柔女声",
        language: "粤语",
        group: "粤语音色",
        recommended: false,
      },
    ],
  });
  voiceApi.updateSettings.mockResolvedValue({} as never);
  voiceApi.requestReading.mockResolvedValue({
    job_id: 19,
    status: "queued",
    playback_mode: "unavailable",
    provider: "minimax",
    model: "speech-2.8-turbo",
    message: "",
    segments: segments.map((segment) => ({ ...segment, status: "queued", audio_url: null })),
  });
  voiceApi.getJob.mockResolvedValue({
    job_id: 19,
    status: "ready",
    playback_mode: "audio",
    provider: "minimax",
    model: "speech-2.8-turbo",
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
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);
    await waitFor(() => expect(play).toHaveBeenCalled());
    expect(screen.queryByText("浏览器语音")).not.toBeInTheDocument();
  });

  it("plays a ready chapter when only the job-level audio URL is present", async () => {
    voiceApi.getJob.mockResolvedValueOnce({
      job_id: 19,
      status: "ready",
      audio_url: "/api/voice-reading/audio/chapter.mp3",
      playback_mode: "audio",
      provider: "minimax",
      model: "speech-2.8-turbo",
      message: "",
      segments: segments.map((segment) => ({
        ...segment,
        status: "ready",
        audio_url: null,
      })),
    });

    renderExperience();

    const audio = await waitFor(() => {
      const element = document.querySelector("audio");
      expect(element).not.toBeNull();
      return element as HTMLAudioElement;
    });

    expect(audio).toHaveAttribute("src", "/api/voice-reading/audio/chapter.mp3");
    expect(screen.getByRole("button", { name: "播放朗读" })).toBeEnabled();
  });

  it("keeps polling a long generation without switching voices", async () => {
    jest.useFakeTimers();
    voiceApi.getJob.mockResolvedValue({ job_id: 19, status: "processing", segments: [] } as never);
    renderExperience();
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await jest.advanceTimersByTimeAsync(211_000); });
    expect(screen.queryByText("这一章暂时无法朗读")).not.toBeInTheDocument();
    voiceApi.getJob.mockResolvedValue({ job_id: 19, status: "ready", segments } as never);
    await act(async () => { await jest.advanceTimersByTimeAsync(15_000); });
    expect(document.querySelector("audio")).toHaveAttribute("src", "/api/voice-reading/audio/chapter.mp3");
  });

  it("preserves buffered audio through a polling timeout and resumes the original job", async () => {
    jest.useFakeTimers();
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "processing", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], audio_url: null, status: "queued" }] } as never);
    voiceApi.getJob.mockRejectedValueOnce(new Error("request timed out"));
    renderExperience();
    await act(async () => { await Promise.resolve(); });
    expect(document.querySelector("audio")).toHaveAttribute("src", "/first.mp3");
    expect(screen.queryByText("这一章暂时无法朗读")).not.toBeInTheDocument();
    await act(async () => { await jest.advanceTimersByTimeAsync(2_000); });
    expect(voiceApi.getJob).toHaveBeenCalledTimes(2);
    expect(document.querySelector("audio")).toHaveAttribute("src", "/first.mp3");
  });

  it("keeps ready segments playable when generation fails", async () => {
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "failed", message: "后续段落失败", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], status: "failed", audio_url: null }] } as never);
    renderExperience();
    await waitFor(() => expect(document.querySelector("audio")).toHaveAttribute("src", "/first.mp3"));
    expect(screen.getByRole("button", { name: "播放朗读" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "重试高质量语音" })).toBeInTheDocument();
  });

  it("keeps the current segment source when the assembled chapter becomes ready", async () => {
    const completion = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "processing", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], audio_url: null, status: "queued" }] } as never);
    voiceApi.getJob.mockReturnValue(completion.promise);
    renderExperience();
    const audio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    fireEvent.playing(audio);
    audio.currentTime = 2;
    await act(async () => { completion.resolve({ job_id: 19, status: "ready", audio_url: "/chapter.mp3", segments: segments.map(s => ({ ...s, audio_url: "/chapter.mp3" })) } as never); });
    expect(document.querySelector("audio")).toBe(audio);
    expect(audio.currentTime).toBe(2);
  });

  it.each([
    { cachedStatus: "ready", assembled: false, missingUrl: true },
    { cachedStatus: "failed", assembled: false, missingUrl: true },
    { cachedStatus: "ready", assembled: true, missingUrl: true },
    { cachedStatus: "failed", assembled: true, missingUrl: true },
    { cachedStatus: "ready", assembled: true, missingUrl: false },
    { cachedStatus: "failed", assembled: true, missingUrl: false },
  ])("replaces a cached $cachedStatus scene after same-job regeneration (assembled=$assembled, missingUrl=$missingUrl) and resumes its local position", async ({ cachedStatus, assembled, missingUrl }) => {
    const completion = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    const sceneSegments = [
      { ...segments[0], audio_url: "/first.mp3" },
      { ...segments[1], status: cachedStatus, start_ms: 0, end_ms: 5000, audio_url: "/old-second.mp3" },
    ];
    voiceApi.getProgress.mockResolvedValueOnce({ paragraph_index: 1, position_ms: 1500 } as never);
    voiceApi.requestReading.mockResolvedValueOnce({ job_id: 19, status: "failed", segments: sceneSegments } as never);
    voiceApi.requestReading.mockResolvedValueOnce({ job_id: 19, status: "processing", segments: missingUrl ? [sceneSegments[0], { ...sceneSegments[1], status: "processing", audio_url: null }] : sceneSegments } as never);
    voiceApi.getJob.mockReturnValueOnce(completion.promise);
    renderExperience();
    const oldAudio = await waitFor(() => {
      expect(document.querySelector("audio")).toHaveAttribute("src", "/old-second.mp3");
      return document.querySelector("audio")!;
    });
    Object.defineProperty(oldAudio, "duration", { configurable: true, value: 5 });
    fireEvent.loadedMetadata(oldAudio);
    expect(oldAudio.currentTime).toBe(1.5);
    fireEvent.playing(oldAudio);
    oldAudio.currentTime = 2;
    fireEvent.click(screen.getByRole("button", { name: "重试高质量语音" }));
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalled());
    expect(voiceApi.requestReading).toHaveBeenLastCalledWith(expect.objectContaining({ force_retry: true }), expect.any(AbortSignal));
    expect(document.querySelector("audio")).toBe(oldAudio);
    expect(oldAudio.currentTime).toBe(2);

    await act(async () => completion.resolve(assembled
      ? { job_id: 19, status: "ready", audio_url: "/regenerated-chapter.mp3", segments: segments.map(segment => ({ ...segment, asset_id: 3, audio_url: "/regenerated-chapter.mp3" })) } as never
      : { job_id: 19, status: "ready", segments: [sceneSegments[0], { ...sceneSegments[1], status: "ready", asset_id: 3, audio_url: "/regenerated-second.mp3" }] } as never));

    const replacement = document.querySelector("audio")!;
    expect(replacement).toHaveAttribute("src", assembled ? "/regenerated-chapter.mp3" : "/regenerated-second.mp3");
    Object.defineProperty(replacement, "duration", { configurable: true, value: assembled ? 9 : 5 });
    fireEvent.loadedMetadata(replacement);
    expect(replacement.currentTime).toBe(assembled ? 6 : 2);
    expect(screen.getByText("第 2 段")).toBeInTheDocument();
    fireEvent.playing(replacement);
    fireEvent.click(screen.getByRole("button", { name: "暂停朗读" }));
    expect(voiceApi.updateProgress).toHaveBeenLastCalledWith(expect.objectContaining({ game_id: 42, day_index: 7, text_hash: "chapter-text-hash", paragraph_index: 1, position_ms: 2000 }));
  });

  it("aborts polling on voice change and ignores the old response", async () => {
    const old = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    voiceApi.getJob.mockReturnValueOnce(old.promise);
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalled());
    const signal = (voiceApi.getJob.mock.calls[0] as unknown as [number, AbortSignal])[1];
    fireEvent.click(screen.getByRole("button", { name: "选择青涩青年音色" }));
    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(2));
    expect(signal?.aborted).toBe(true);
    await act(async () => { old.resolve({ job_id: 19, status: "ready", segments: [{ ...segments[0], audio_url: "/obsolete.mp3" }] } as never); });
    expect(document.querySelector("audio")).not.toHaveAttribute("src", "/obsolete.mp3");
  });

  it.each([0, 1])("keeps coherent chapter cues when a mixed retry completes with paragraph %s active", async (paragraphIndex) => {
    const completion = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    const oldScenes = [
      { ...segments[0], audio_url: "/old-first.mp3" },
      { ...segments[1], start_ms: 0, end_ms: 5000, audio_url: "/old-second.mp3" },
    ];
    voiceApi.getProgress.mockResolvedValueOnce({ paragraph_index: paragraphIndex, position_ms: 0 } as never);
    voiceApi.requestReading.mockResolvedValueOnce({ job_id: 19, status: "failed", segments: oldScenes } as never);
    voiceApi.requestReading.mockResolvedValueOnce({ job_id: 19, status: "processing", segments: [oldScenes[0], { ...oldScenes[1], audio_url: "/new-second.mp3", asset_id: 3 }] } as never);
    voiceApi.getJob.mockReturnValueOnce(completion.promise);
    renderExperience();
    const original = await waitFor(() => {
      expect(document.querySelector("audio")).toHaveAttribute("src", paragraphIndex === 0 ? "/old-first.mp3" : "/old-second.mp3");
      return document.querySelector("audio")!;
    });
    Object.defineProperty(original, "duration", { configurable: true, value: paragraphIndex === 0 ? 4 : 5 });
    fireEvent.loadedMetadata(original);
    fireEvent.playing(original);
    original.currentTime = 2;
    fireEvent.click(screen.getByRole("button", { name: "重试高质量语音" }));
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalled());
    const partial = document.querySelector("audio")!;
    expect(partial).toHaveAttribute("src", paragraphIndex === 0 ? "/old-first.mp3" : "/new-second.mp3");
    if (paragraphIndex === 1) {
      Object.defineProperty(partial, "duration", { configurable: true, value: 5 });
      fireEvent.loadedMetadata(partial);
      fireEvent.playing(partial);
    }
    expect(partial.currentTime).toBe(2);

    await act(async () => completion.resolve({ job_id: 19, status: "ready", audio_url: "/chapter.mp3", segments: segments.map(segment => ({ ...segment, audio_url: "/chapter.mp3", asset_id: 4 })) } as never));
    const chapter = document.querySelector("audio")!;
    expect(chapter).toHaveAttribute("src", "/chapter.mp3");
    Object.defineProperty(chapter, "duration", { configurable: true, value: 9 });
    fireEvent.loadedMetadata(chapter);
    expect(document.querySelector("audio")).toBe(chapter);
    expect(chapter.currentTime).toBe(paragraphIndex === 0 ? 2 : 6);
    expect(screen.getByText(`第 ${paragraphIndex + 1} 段`)).toBeInTheDocument();
    fireEvent.playing(chapter);
    chapter.currentTime = paragraphIndex === 0 ? 4.5 : 6.5;
    fireEvent.timeUpdate(chapter);
    expect(document.querySelector("audio")).toBe(chapter);
    expect(screen.getByText("第 2 段")).toBeInTheDocument();
    expect(screen.getByRole("slider")).toHaveValue(paragraphIndex === 0 ? "4500" : "6500");
    fireEvent.click(screen.getByRole("button", { name: "暂停朗读" }));
    await act(async () => {});
    expect(voiceApi.updateProgress).toHaveBeenLastCalledWith(expect.objectContaining({ paragraph_index: 1, position_ms: paragraphIndex === 0 ? 500 : 2500 }));
  });

  it.each([
    { intent: "selection", localMs: 0, bufferedMetadata: false },
    { intent: "seek", localMs: 2000, bufferedMetadata: false },
    { intent: "recovery", localMs: 2500, bufferedMetadata: false },
    { intent: "selection", localMs: 0, bufferedMetadata: true },
    { intent: "seek", localMs: 2000, bufferedMetadata: true },
    { intent: "recovery", localMs: 2500, bufferedMetadata: true },
  ])("rebases pending scene $intent onto replacement chapter cues (bufferedMetadata=$bufferedMetadata)", async ({ intent, localMs, bufferedMetadata }) => {
    jest.useFakeTimers();
    const completion = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    const scenes = [
      { ...segments[0], audio_url: "/first.mp3" },
      { ...segments[1], start_ms: 0, end_ms: 5000, audio_url: "/second.mp3" },
    ];
    voiceApi.getProgress.mockResolvedValueOnce({ paragraph_index: intent === "recovery" ? 1 : 0, position_ms: 0 } as never);
    voiceApi.requestReading.mockResolvedValueOnce({ job_id: 19, status: "failed", segments: scenes } as never);
    voiceApi.requestReading.mockResolvedValueOnce({ job_id: 19, status: "processing", segments: scenes } as never);
    voiceApi.getJob.mockReturnValueOnce(completion.promise);
    renderExperience();
    const original = await waitFor(() => {
      expect(document.querySelector("audio")).toHaveAttribute("src", intent === "recovery" ? "/second.mp3" : "/first.mp3");
      return document.querySelector("audio")!;
    });
    Object.defineProperty(original, "duration", { configurable: true, value: intent === "recovery" ? 5 : 4 });
    fireEvent.loadedMetadata(original);
    original.currentTime = intent === "recovery" ? 2.5 : 1;
    fireEvent.playing(original);
    fireEvent.click(screen.getByRole("button", { name: "重试高质量语音" }));
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalled());

    if (intent === "selection") {
      fireEvent.click(screen.getByRole("button", { name: "查看正文" }));
      fireEvent.click(screen.getByRole("button", { name: "从第 2 段开始朗读" }));
    } else if (intent === "seek") {
      fireEvent.change(screen.getByRole("slider"), { target: { value: "6000" } });
    } else {
      fireEvent.stalled(original);
      await act(async () => { await jest.advanceTimersByTimeAsync(8000); });
      expect(load).toHaveBeenCalledTimes(1);
      original.currentTime = 0;
    }
    expect(document.querySelector("audio")).toHaveAttribute("src", "/second.mp3");
    if (bufferedMetadata) {
      jest.spyOn(HTMLMediaElement.prototype, "readyState", "get").mockReturnValue(HTMLMediaElement.HAVE_METADATA);
      jest.spyOn(HTMLMediaElement.prototype, "duration", "get").mockReturnValue(9);
    }
    await act(async () => completion.resolve({ job_id: 19, status: "ready", audio_url: "/chapter.mp3", segments: segments.map(segment => ({ ...segment, audio_url: "/chapter.mp3", asset_id: 3 })) } as never));
    const chapter = document.querySelector("audio")!;
    expect(chapter).toHaveAttribute("src", "/chapter.mp3");
    if (!bufferedMetadata) {
      Object.defineProperty(chapter, "duration", { configurable: true, value: 9 });
      fireEvent.loadedMetadata(chapter);
    }
    expect(chapter.currentTime).toBe((4000 + localMs) / 1000);
    expect(screen.getByText("第 2 段")).toBeInTheDocument();
    expect(screen.getByRole("slider")).toHaveValue(String(4000 + localMs));
    fireEvent.playing(chapter);
    fireEvent.click(screen.getByRole("button", { name: "暂停朗读" }));
    await act(async () => {});
    expect(voiceApi.updateProgress).toHaveBeenLastCalledWith(expect.objectContaining({ game_id: 42, day_index: 7, text_hash: "chapter-text-hash", paragraph_index: 1, position_ms: localMs }));
  });

  it("coalesces progress while a write is in flight and does not interrupt playback on failure", async () => {
    jest.spyOn(console, "warn").mockImplementation();
    const write = deferred<Awaited<ReturnType<typeof api.voice_reading.updateProgress>>>();
    voiceApi.updateProgress.mockReturnValueOnce(write.promise);
    renderExperience();
    const audio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    fireEvent.playing(audio);
    audio.currentTime = 1;
    fireEvent.timeUpdate(audio);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "2000" } });
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3000" } });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    await act(async () => { write.reject(new Error("store busy")); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    expect(voiceApi.updateProgress.mock.calls[1][0]).toMatchObject({ position_ms: 3000 });
    expect(document.querySelector("audio")).toBe(audio);
    expect(screen.queryByText("这一章暂时无法朗读")).not.toBeInTheDocument();
  });

  it.each(["paused", "completed"])("recovers the final %s progress snapshot after Retry-After without another media event", async (ending) => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    voiceApi.updateProgress.mockRejectedValueOnce(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy", retryAfterMs: 12_000 }));
    renderExperience();
    const audio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    fireEvent.playing(audio);
    audio.currentTime = 2;
    if (ending === "paused") fireEvent.click(screen.getByRole("button", { name: "暂停朗读" }));
    else fireEvent.ended(audio);
    await act(async () => { await jest.advanceTimersByTimeAsync(11_999); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    await act(async () => { await jest.advanceTimersByTimeAsync(1); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    expect(voiceApi.updateProgress.mock.calls[1][0]).toEqual({
      game_id: 42, day_index: 7, story_date: "2026-08-15", text_hash: "chapter-text-hash", voice_id: "female-shaonv", speed: 1,
      paragraph_index: ending === "paused" ? 0 : 1,
      position_ms: ending === "paused" ? 2000 : 5000,
      completed: ending === "completed",
    });
    expect(document.querySelector("audio")).toBe(audio);
    expect(play).not.toHaveBeenCalled();
    expect(screen.queryByText("浏览器语音")).not.toBeInTheDocument();
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
  });

  it("retries only the newest queued progress while keeping one write in flight", async () => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    const firstWrite = deferred<Awaited<ReturnType<typeof api.voice_reading.updateProgress>>>();
    const retryWrite = deferred<Awaited<ReturnType<typeof api.voice_reading.updateProgress>>>();
    voiceApi.updateProgress.mockReturnValueOnce(firstWrite.promise).mockReturnValueOnce(retryWrite.promise);
    renderExperience();
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.change(screen.getByRole("slider"), { target: { value: "1000" } });
    fireEvent.change(screen.getByRole("slider"), { target: { value: "2000" } });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    await act(async () => firstWrite.reject(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy", retryAfterMs: 2000 })));
    await act(async () => { await jest.advanceTimersByTimeAsync(1000); });
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3000" } });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    await act(async () => { await jest.advanceTimersByTimeAsync(1000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    expect(voiceApi.updateProgress.mock.calls[1][0]).toMatchObject({ position_ms: 3000 });
    fireEvent.change(screen.getByRole("slider"), { target: { value: "4000" } });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    await act(async () => retryWrite.resolve({} as never));
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(3);
    expect(voiceApi.updateProgress.mock.calls[2][0]).toMatchObject({ paragraph_index: 1, position_ms: 0 });
  });

  it("bounds repeated busy progress retries and accepts a later fresh snapshot", async () => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    voiceApi.updateProgress.mockRejectedValue(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy" }));
    renderExperience();
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.change(screen.getByRole("slider"), { target: { value: "1000" } });
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(4);
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(4);
    voiceApi.updateProgress.mockResolvedValue({} as never);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3000" } });
    await act(async () => {});
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(5);
    expect(voiceApi.updateProgress.mock.calls[4][0]).toMatchObject({ position_ms: 3000 });
  });

  it.each(["unmount", "story change"])("cancels delayed progress retries on %s", async (change) => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    voiceApi.updateProgress.mockRejectedValueOnce(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy", retryAfterMs: 2000 }));
    const view = renderExperience();
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.change(screen.getByRole("slider"), { target: { value: "1000" } });
    await act(async () => { await jest.advanceTimersByTimeAsync(1000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    if (change === "unmount") view.unmount();
    else view.rerender(<StoryListeningExperience context={{ ...context, day_index: 8 }} storyText="新的一天。" options={[]} onSelectChoice={jest.fn()} />);
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    if (change === "story change") {
      fireEvent.change(screen.getByRole("slider"), { target: { value: "2000" } });
      await act(async () => {});
      expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
      expect(voiceApi.updateProgress.mock.calls[1][0]).toMatchObject({ day_index: 8, position_ms: 2000 });
    }
  });

  it("discards old queued progress after identity changes while an old write is unresolved", async () => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    const oldWrite = deferred<Awaited<ReturnType<typeof api.voice_reading.updateProgress>>>();
    voiceApi.updateProgress.mockReturnValueOnce(oldWrite.promise);
    const view = renderExperience();
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.change(screen.getByRole("slider"), { target: { value: "1000" } });
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3000" } });
    view.rerender(<StoryListeningExperience context={{ ...context, day_index: 8 }} storyText="新的一天。" options={[]} onSelectChoice={jest.fn()} />);
    await act(async () => {});
    await act(async () => oldWrite.reject(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy", retryAfterMs: 2000 })));
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "2000" } });
    await act(async () => {});
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    expect(voiceApi.updateProgress.mock.calls[1][0]).toMatchObject({ day_index: 8, position_ms: 2000 });
  });

  it("finishes a bounded final-choice progress retry after immediate unmount", async () => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    const finalWrite = deferred<Awaited<ReturnType<typeof api.voice_reading.updateProgress>>>();
    voiceApi.updateProgress.mockReturnValueOnce(finalWrite.promise);
    const view = renderExperience();
    const audio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    audio.currentTime = 2;
    fireEvent.click(screen.getByRole("button", { name: /推开那扇门/ }));
    view.unmount();
    await act(async () => finalWrite.reject(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy", retryAfterMs: 2000 })));
    await act(async () => { await jest.advanceTimersByTimeAsync(1999); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    await act(async () => { await jest.advanceTimersByTimeAsync(1); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    expect(voiceApi.updateProgress.mock.calls[1][0]).toMatchObject({ day_index: 7, text_hash: "chapter-text-hash", position_ms: 2000 });
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
  });

  it("lets a remounted listener supersede an older retained choice snapshot for the same story", async () => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    voiceApi.updateProgress.mockRejectedValueOnce(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy", retryAfterMs: 2000 }));
    const view = renderExperience();
    const audio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    audio.currentTime = 1;
    fireEvent.click(screen.getByRole("button", { name: /推开那扇门/ }));
    view.unmount();
    await act(async () => { await jest.advanceTimersByTimeAsync(1000); });
    renderExperience();
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3000" } });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(1);
    await act(async () => { await jest.advanceTimersByTimeAsync(2000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    expect(voiceApi.updateProgress.mock.calls[1][0]).toMatchObject({ day_index: 7, position_ms: 3000 });
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
  });

  it("keeps a retained choice snapshot independent from another story session", async () => {
    jest.useFakeTimers();
    jest.spyOn(console, "warn").mockImplementation();
    voiceApi.updateProgress.mockRejectedValueOnce(Object.assign(new Error("busy"), { status: 503, code: "progress_store_busy", retryAfterMs: 2000 }));
    const oldView = renderExperience();
    const oldAudio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    oldAudio.currentTime = 1;
    fireEvent.click(screen.getByRole("button", { name: /推开那扇门/ }));
    oldView.unmount();
    await act(async () => { await jest.advanceTimersByTimeAsync(1000); });
    const nextView = render(<StoryListeningExperience context={{ ...context, day_index: 8 }} storyText="新的一天。" options={[]} onSelectChoice={jest.fn()} />);
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3000" } });
    await act(async () => {});
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(2);
    expect(voiceApi.updateProgress.mock.calls[1][0]).toMatchObject({ day_index: 8, position_ms: 3000 });
    nextView.unmount();
    await act(async () => { await jest.advanceTimersByTimeAsync(2000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(3);
    expect(voiceApi.updateProgress.mock.calls[2][0]).toMatchObject({ day_index: 7, position_ms: 1000 });
    await act(async () => { await jest.advanceTimersByTimeAsync(60_000); });
    expect(voiceApi.updateProgress).toHaveBeenCalledTimes(3);
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

  it("offers exactly one transcript action in each collapsed or expanded state", async () => {
    renderExperience();

    const openButtons = await screen.findAllByRole("button", { name: "查看正文" });
    expect(openButtons).toHaveLength(1);
    fireEvent.click(openButtons[0]);

    expect(screen.queryByRole("button", { name: "查看正文" })).not.toBeInTheDocument();
    const closeButtons = screen.getAllByRole("button", { name: "收起正文" });
    expect(closeButtons).toHaveLength(1);
    fireEvent.click(closeButtons[0]);

    expect(screen.getAllByRole("button", { name: "查看正文" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "收起正文" })).not.toBeInTheDocument();
  });

  it("keeps paragraph position separate from the playback status", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    fireEvent.playing(document.querySelector("audio") as HTMLAudioElement);

    expect(screen.getByText("第 1 段")).toBeInTheDocument();
    expect(screen.getByText("朗读中")).toBeInTheDocument();
    expect(screen.queryByText("正在朗读第 1 段")).not.toBeInTheDocument();
  });

  it("preserves a paragraph selection made before its chapter cues are ready", async () => {
    const readyJob = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    voiceApi.requestReading.mockResolvedValueOnce({
      job_id: 19,
      status: "queued",
      playback_mode: "unavailable",
      provider: "minimax",
      model: "speech-2.8-turbo",
      message: "",
      segments: segments.map((segment) => ({
        ...segment,
        status: "queued",
        audio_url: null,
        start_ms: null,
        end_ms: null,
      })),
    });
    voiceApi.getJob.mockReturnValueOnce(readyJob.promise);
    renderExperience();

    fireEvent.click((await screen.findByText("查看正文")).closest("button") as HTMLButtonElement);
    const secondParagraph = await screen.findByRole("button", {
      name: "从第 2 段开始朗读",
    });
    fireEvent.click(secondParagraph);
    expect(secondParagraph).toHaveAttribute("aria-current", "true");

    readyJob.resolve({
      job_id: 19,
      status: "ready",
      playback_mode: "audio",
      provider: "minimax",
      model: "speech-2.8-turbo",
      message: "",
      segments,
    });
    const audio = await waitFor(() => {
      const element = document.querySelector("audio") as HTMLAudioElement | null;
      expect(element).not.toBeNull();
      return element as HTMLAudioElement;
    });
    Object.defineProperty(audio, "duration", { configurable: true, value: 9 });
    fireEvent.loadedMetadata(audio);

    expect(audio.currentTime).toBe(4);
    expect(secondParagraph).toHaveAttribute("aria-current", "true");
  });

  it("stops narration immediately when a daily choice is selected", async () => {
    const { onSelectChoice } = renderExperience();
    await screen.findByRole("button", { name: /推开那扇门/ });
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
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
        model: "speech-2.8-turbo",
        error_code: "tts_generation_failed",
        message: "高质量语音生成失败",
        segments: [{ ...segments[0], status: "failed", audio_url: null }],
      })
      .mockResolvedValueOnce({
        job_id: 20,
        status: "ready",
        playback_mode: "audio",
        provider: "minimax",
        model: "speech-2.8-turbo",
        message: "",
        segments,
      });

    renderExperience();

    fireEvent.click(await screen.findByRole("button", { name: "重试高质量语音" }));

    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(2));
    expect(voiceApi.requestReading.mock.calls[1][0]).toEqual(
      expect.objectContaining({ force_retry: true }),
    );
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);
    await waitFor(() => expect(play).toHaveBeenCalled());
  });

  it("uses browser Chinese narration only after explicit selection", async () => {
    const spoken: Array<{
      text: string;
      lang: string;
      rate: number;
      onstart?: () => void;
      onend?: () => void;
    }> = [];
    const speechSynthesis = {
      cancel: jest.fn(),
      getVoices: jest.fn(() => []),
      speak: jest.fn((utterance: (typeof spoken)[number]) => {
        spoken.push(utterance);
      }),
    };
    const previousSynthesis = (window as Window & { speechSynthesis?: unknown }).speechSynthesis;
    const previousUtterance = (globalThis as { SpeechSynthesisUtterance?: unknown }).SpeechSynthesisUtterance;
    class TestSpeechSynthesisUtterance {
      text: string;
      lang = "";
      rate = 1;
      onstart?: () => void;
      onend?: () => void;

      constructor(text: string) {
        this.text = text;
      }
    }
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: speechSynthesis,
    });
    Object.defineProperty(globalThis, "SpeechSynthesisUtterance", {
      configurable: true,
      value: TestSpeechSynthesisUtterance,
    });
    voiceApi.requestReading.mockResolvedValueOnce({
      job_id: 20,
      status: "failed",
      playback_mode: "unavailable",
      provider: "minimax",
      model: "speech-2.8-turbo",
      error_code: "tts_generation_failed",
      message: "High-quality narration could not be generated",
      segments: [{ ...segments[0], status: "failed", audio_url: null }],
    });

    try {
      renderExperience();

      expect(await screen.findByRole("button", { name: "使用系统朗读" })).toBeInTheDocument();
      expect(speechSynthesis.speak).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: "播放朗读" })).toBeDisabled();
      fireEvent.click(screen.getByRole("button", { name: "使用系统朗读" }));
      const playButton = screen.getByRole("button", { name: "播放朗读" });
      expect(playButton).toBeEnabled();
      fireEvent.click(playButton);

      await waitFor(() => expect(speechSynthesis.speak).toHaveBeenCalledTimes(1));
      expect(spoken[0]).toMatchObject({ text: "第一段故事。", lang: "zh-CN", rate: 1 });
      act(() => spoken[0].onstart?.());
      expect(await screen.findByText("朗读中")).toBeInTheDocument();
      act(() => spoken[0].onend?.());
      expect(await screen.findByText("第 2 段")).toBeInTheDocument();
      expect(speechSynthesis.speak).toHaveBeenCalledTimes(2);
    } finally {
      if (previousSynthesis === undefined) delete (window as Window & { speechSynthesis?: unknown }).speechSynthesis;
      else Object.defineProperty(window, "speechSynthesis", { configurable: true, value: previousSynthesis });
      if (previousUtterance === undefined) delete (globalThis as { SpeechSynthesisUtterance?: unknown }).SpeechSynthesisUtterance;
      else Object.defineProperty(globalThis, "SpeechSynthesisUtterance", { configurable: true, value: previousUtterance });
    }
  });

  it("restores the original voice only at a browser paragraph boundary after explicit recovery", async () => {
    const response = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    voiceApi.getJob.mockReturnValue(response.promise);
    const spoken: SpeechSynthesisUtterance[] = [];
    const oldSpeech = window.speechSynthesis;
    const oldUtterance = window.SpeechSynthesisUtterance;
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { cancel: jest.fn(), getVoices: () => [], speak: (value: SpeechSynthesisUtterance) => spoken.push(value) } });
    Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: class { constructor(public text: string) {} } });
    try {
      renderExperience();
      fireEvent.click(await screen.findByRole("button", { name: "使用系统朗读" }));
      fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));
      act(() => spoken[0].onstart?.(new Event("start") as SpeechSynthesisEvent));
      await act(async () => response.resolve({ job_id: 19, status: "ready", segments } as never));
      expect(document.querySelector("audio")).toBeNull();
      fireEvent.click(await screen.findByRole("button", { name: "恢复原音色" }));
      expect(document.querySelector("audio")).toBeNull();
      act(() => spoken[0].onend?.(new Event("end") as SpeechSynthesisEvent));
      const audio = document.querySelector("audio")!;
      expect(audio).toHaveAttribute("src", "/api/voice-reading/audio/chapter.mp3");
      Object.defineProperty(audio, "duration", { configurable: true, value: 9 });
      fireEvent.loadedMetadata(audio);
      expect(audio.currentTime).toBe(4);
      expect(spoken).toHaveLength(1);
      expect(voiceApi.updateSettings).not.toHaveBeenCalled();
      expect(voiceApi.requestReading).toHaveBeenCalledTimes(1);
    } finally {
      Object.defineProperty(window, "speechSynthesis", { configurable: true, value: oldSpeech });
      Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: oldUtterance });
    }
  });

  it("waits for the immediate missing segment without replaying or skipping it", async () => {
    const next = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "processing", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], status: "queued", audio_url: null }] } as never);
    voiceApi.getJob.mockReturnValue(next.promise);
    renderExperience();
    const first = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    fireEvent.ended(first);
    expect(screen.getByText("准备中")).toBeInTheDocument();
    await act(async () => next.resolve({ job_id: 19, status: "ready", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], audio_url: "/second.mp3" }] } as never));
    const second = document.querySelector("audio")!;
    expect(second).toHaveAttribute("src", "/second.mp3");
    Object.defineProperty(second, "duration", { configurable: true, value: 5 });
    fireEvent.loadedMetadata(second);
    second.currentTime = 1;
    fireEvent.timeUpdate(second);
    expect(screen.getByText("第 2 段")).toBeInTheDocument();
    fireEvent.ended(second);
    expect(screen.getByText("已就绪")).toBeInTheDocument();
    await waitFor(() => expect(voiceApi.updateProgress).toHaveBeenLastCalledWith(expect.objectContaining({ paragraph_index: 1, completed: true })));
  });

  it("does not request a new story with the previous story hash", async () => {
    const { storyVoiceTextToHash } = await import("@/lib/storyVoiceTextHash");
    const newHash = deferred<string>();
    const view = renderExperience();
    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(1));
    (storyVoiceTextToHash as jest.Mock).mockReturnValueOnce(newHash.promise);
    view.rerender(<StoryListeningExperience context={{ ...context, day_index: 8 }} storyText="新的一天。" options={[]} onSelectChoice={jest.fn()} />);
    await act(async () => { await Promise.resolve(); });
    expect(voiceApi.requestReading).toHaveBeenCalledTimes(1);
    await act(async () => newHash.resolve("new-story-hash"));
    expect(voiceApi.requestReading).toHaveBeenLastCalledWith(expect.objectContaining({ context: expect.objectContaining({ text: "新的一天。", text_hash: "new-story-hash" }) }), expect.any(AbortSignal));
  });

  it("seeks using local media time in the second segment", async () => {
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "ready", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], start_ms: 0, end_ms: 5000, audio_url: "/second.mp3" }] } as never);
    renderExperience();
    await waitFor(() => expect(document.querySelector("audio")).not.toBeNull());
    const first = document.querySelector("audio")!;
    Object.defineProperty(first, "readyState", { configurable: true, value: HTMLMediaElement.HAVE_ENOUGH_DATA });
    first.currentTime = 1;
    fireEvent.change(screen.getByRole("slider"), { target: { value: "6000" } });
    const audio = document.querySelector("audio")!;
    Object.defineProperty(audio, "duration", { configurable: true, value: 5 });
    fireEvent.loadedMetadata(audio);
    expect(audio.currentTime).toBe(2);
    expect(first.currentTime).toBe(1);
    expect(screen.getByText("第 2 段")).toBeInTheDocument();
  });

  it("respects server poll backoff while retaining the current audio", async () => {
    jest.useFakeTimers();
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "processing", segments: [{ ...segments[0], audio_url: "/first.mp3" }] } as never);
    voiceApi.getJob.mockRejectedValueOnce(Object.assign(new Error("busy"), { status: 503, retryAfterMs: 12_000 }));
    renderExperience();
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await jest.advanceTimersByTimeAsync(11_000); });
    expect(voiceApi.getJob).toHaveBeenCalledTimes(1);
    expect(document.querySelector("audio")).toHaveAttribute("src", "/first.mp3");
    await act(async () => { await jest.advanceTimersByTimeAsync(1_000); });
    expect(voiceApi.getJob).toHaveBeenCalledTimes(2);
  });

  it("waits offline and refreshes the job immediately when online", async () => {
    jest.useFakeTimers();
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    try {
      renderExperience();
      await act(async () => { await Promise.resolve(); });
      await act(async () => { await jest.advanceTimersByTimeAsync(30_000); });
      expect(voiceApi.getJob).not.toHaveBeenCalled();
      Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
      await act(async () => { window.dispatchEvent(new Event("online")); });
      expect(document.querySelector("audio")).toHaveAttribute("src", "/api/voice-reading/audio/chapter.mp3");
    } finally {
      Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    }
  });

  it("retries missing generation without clearing audio already playing", async () => {
    voiceApi.requestReading.mockResolvedValueOnce({ job_id: 19, status: "failed", message: "后续段落失败", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], status: "failed", audio_url: null }] } as never);
    const retry = deferred<Awaited<ReturnType<typeof api.voice_reading.requestReading>>>();
    voiceApi.requestReading.mockReturnValueOnce(retry.promise);
    renderExperience();
    const audio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    fireEvent.playing(audio);
    audio.currentTime = 2;
    fireEvent.click(screen.getByRole("button", { name: "重试高质量语音" }));
    await act(async () => { await Promise.resolve(); });
    expect(document.querySelector("audio")).toBe(audio);
    expect(audio.currentTime).toBe(2);
    expect(screen.getByRole("button", { name: "暂停朗读" })).toBeEnabled();
  });

  it("continues into the assembled chapter at the next cue after a retained segment ends", async () => {
    const completion = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "processing", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], audio_url: null, status: "queued" }] } as never);
    voiceApi.getJob.mockReturnValue(completion.promise);
    renderExperience();
    const first = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    await act(async () => completion.resolve({ job_id: 19, status: "ready", audio_url: "/chapter.mp3", segments: segments.map(s => ({ ...s, audio_url: "/chapter.mp3" })) } as never));
    fireEvent.ended(first);
    const chapter = document.querySelector("audio")!;
    expect(chapter).toHaveAttribute("src", "/chapter.mp3");
    Object.defineProperty(chapter, "duration", { configurable: true, value: 9 });
    fireEvent.loadedMetadata(chapter);
    expect(chapter.currentTime).toBe(4);
    chapter.currentTime = 6;
    fireEvent.timeUpdate(chapter);
    expect(screen.getByRole("slider")).toHaveValue("6000");
    fireEvent.ended(chapter);
    expect(screen.getByText("已就绪")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));
    expect(document.querySelector("audio")).toHaveAttribute("src", "/first.mp3");
  });

  it("replays from the first source after the final independent scene ends", async () => {
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "failed", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], start_ms: 0, end_ms: 5000, audio_url: "/second.mp3" }] } as never);
    renderExperience();
    const first = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    fireEvent.ended(first);
    fireEvent.ended(document.querySelector("audio")!);
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));
    expect(document.querySelector("audio")).toHaveAttribute("src", "/first.mp3");
    expect(screen.getByText("第 1 段")).toBeInTheDocument();
  });

  it("stops old audio and rejects its events while a new story hash is pending", async () => {
    const { storyVoiceTextToHash } = await import("@/lib/storyVoiceTextHash");
    const hash = deferred<string>();
    const view = renderExperience();
    const oldAudio = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    fireEvent.playing(oldAudio);
    pause.mockClear();
    voiceApi.updateProgress.mockClear();
    (storyVoiceTextToHash as jest.Mock).mockReturnValueOnce(hash.promise);
    view.rerender(<StoryListeningExperience context={{ ...context, day_index: 8 }} storyText="新一天。" options={[]} onSelectChoice={jest.fn()} />);
    expect(pause).toHaveBeenCalled();
    oldAudio.currentTime = 3;
    fireEvent.timeUpdate(oldAudio);
    expect(voiceApi.updateProgress).not.toHaveBeenCalled();
    expect(document.querySelector("audio")).toBeNull();
  });

  it("keeps a selected chapter cue pending until its new source loads", async () => {
    const completion = deferred<Awaited<ReturnType<typeof api.voice_reading.getJob>>>();
    voiceApi.requestReading.mockResolvedValue({ job_id: 19, status: "processing", segments: [{ ...segments[0], audio_url: "/first.mp3" }, { ...segments[1], audio_url: null, status: "queued" }] } as never);
    voiceApi.getJob.mockReturnValue(completion.promise);
    renderExperience();
    const first = await waitFor(() => { expect(document.querySelector("audio")).not.toBeNull(); return document.querySelector("audio")!; });
    Object.defineProperty(first, "readyState", { configurable: true, value: HTMLMediaElement.HAVE_ENOUGH_DATA });
    first.currentTime = 1;
    await act(async () => completion.resolve({ job_id: 19, status: "ready", audio_url: "/chapter.mp3", segments: segments.map(s => ({ ...s, audio_url: "/chapter.mp3" })) } as never));
    fireEvent.click(screen.getByRole("button", { name: "查看正文" }));
    fireEvent.click(screen.getByRole("button", { name: "从第 2 段开始朗读" }));
    const chapter = document.querySelector("audio")!;
    expect(chapter).toHaveAttribute("src", "/chapter.mp3");
    Object.defineProperty(chapter, "duration", { configurable: true, value: 9 });
    fireEvent.loadedMetadata(chapter);
    expect(chapter.currentTime).toBe(4);
    expect(first.currentTime).toBe(1);
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
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "duration", { configurable: true, value: 9 });
    fireEvent.loadedMetadata(audio);
    expect(audio.currentTime).toBe(6);
    expect(screen.getByLabelText("朗读进度")).toHaveValue("6000");
    fireEvent.canPlay(audio);
    await waitFor(() => expect(play).toHaveBeenCalled());
  });

  it("respects a disabled next-chapter auto-read setting", async () => {
    voiceApi.getSettings.mockResolvedValue({
      ...(await voiceApi.getSettings()),
      auto_read_enabled: false,
    });

    renderExperience();

    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    expect(play).not.toHaveBeenCalled();
    expect(screen.getByRole("checkbox", { name: "下一章自动播放" })).not.toBeChecked();
  });

  it("shows a one-tap action when the browser blocks automatic playback", async () => {
    play.mockRejectedValueOnce(new Error("autoplay blocked"));
    renderExperience();

    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    fireEvent.canPlay(document.querySelector("audio") as HTMLAudioElement);

    expect(await screen.findByText("点击播放，开启自动朗读")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));

    await waitFor(() => expect(play).toHaveBeenCalledTimes(2));
  });

  it("persists voice and speed changes before rebuilding the chapter audio", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "查看全部中文音色" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "全部中文音色" })).getByRole("button", { name: "选择青涩青年音色" }));
    fireEvent.change(screen.getByLabelText("语速"), { target: { value: "1.25" } });

    expect(voiceApi.updateSettings).toHaveBeenCalledWith({ selected_voice_color: "male-qn-qingse" });
    expect(voiceApi.updateSettings).toHaveBeenCalledWith({ selected_speed: 1.25 });
    await waitFor(() => expect(voiceApi.requestReading).toHaveBeenLastCalledWith(expect.objectContaining({ voice_id: "male-qn-qingse", speed: 1.25 }), expect.any(AbortSignal)));
  });

  it("shows a clean Chinese voice picker with searchable Mandarin and Cantonese catalog", async () => {
    renderExperience();

    expect((await screen.findAllByText("少女音色")).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("warm_female")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看全部中文音色" }));
    expect(screen.getByRole("dialog", { name: "全部中文音色" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "温润" } });
    expect(screen.getByRole("button", { name: "选择温润男声" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "试听温润男声" })).toBeInTheDocument();
    expect(within(screen.getByRole("dialog", { name: "全部中文音色" })).queryByRole("button", { name: "选择青涩青年音色" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("tab", { name: "粤语" }));
    expect(screen.getByRole("button", { name: "选择温柔女声" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "试听温柔女声" })).toBeInTheDocument();
    expect(within(screen.getByRole("dialog", { name: "全部中文音色" })).queryByRole("button", { name: "选择青涩青年音色" })).not.toBeInTheDocument();
  });

  it("waits for metadata before applying a cross-paragraph seek and refines chapter duration from the media", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const firstAudio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(firstAudio, "currentTime", { configurable: true, writable: true, value: 0 });

    fireEvent.change(screen.getByLabelText("朗读进度"), { target: { value: "5000" } });

    expect(firstAudio.currentTime).toBe(0);
    const audio = document.querySelector("audio") as HTMLAudioElement;
    expect(audio).toBe(firstAudio);
    Object.defineProperty(audio, "duration", { configurable: true, value: 10 });

    fireEvent.loadedMetadata(audio);

    expect(audio.currentTime).toBe(5);
    expect(screen.getByLabelText("朗读进度")).toHaveAttribute("max", "10000");
  });

  it("applies a same-paragraph seek immediately and resumes when metadata is already available", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "readyState", {
      configurable: true,
      value: HTMLMediaElement.HAVE_METADATA,
    });
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 0.5,
    });
    fireEvent.canPlay(audio);
    fireEvent.playing(audio);
    play.mockClear();

    fireEvent.change(screen.getByLabelText("朗读进度"), { target: { value: "1000" } });

    expect(audio.currentTime).toBe(1);
    expect(play).toHaveBeenCalledTimes(1);
  });

  it("recovers one stalled paragraph after exactly eight seconds, then offers a manual continuation", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "duration", { configurable: true, value: 10 });
    fireEvent.loadedMetadata(audio);
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

  it("recovers when playback silently stops advancing without media stall events", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "duration", { configurable: true, value: 10 });
    fireEvent.loadedMetadata(audio);
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 1.75,
    });
    fireEvent.playing(audio);
    fireEvent.timeUpdate(audio);

    await act(async () => {
      jest.advanceTimersByTime(7_999);
    });
    expect(load).not.toHaveBeenCalled();

    await act(async () => {
      jest.advanceTimersByTime(1);
    });

    expect(load).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "网络不稳定，继续朗读" })).toBeInTheDocument();
    audio.currentTime = 0;
    fireEvent.loadedMetadata(audio);
    expect(audio.currentTime).toBe(1.75);
  });

  it("keeps extending the silent-stall deadline while playback advances", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 1,
    });
    fireEvent.playing(audio);
    fireEvent.timeUpdate(audio);
    await act(async () => {
      jest.advanceTimersByTime(7_000);
    });

    audio.currentTime = 2;
    fireEvent.timeUpdate(audio);
    await act(async () => {
      jest.advanceTimersByTime(7_000);
    });

    expect(load).not.toHaveBeenCalled();
  });

  it("stops automatic reload loops after a second silent stall and lets the listener retry", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "duration", { configurable: true, value: 10 });
    fireEvent.loadedMetadata(audio);
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 1.75,
    });
    fireEvent.playing(audio);
    fireEvent.timeUpdate(audio);
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });
    expect(load).toHaveBeenCalledTimes(1);

    audio.currentTime = 0;
    fireEvent.loadedMetadata(audio);
    fireEvent.canPlay(audio);
    fireEvent.playing(audio);
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).toHaveBeenCalledTimes(1);
    const retry = screen.getByRole("button", { name: "网络不稳定，继续朗读" });
    fireEvent.click(retry);
    expect(load).toHaveBeenCalledTimes(2);
    expect(play).toHaveBeenCalledTimes(2);
  });

  it("cancels the silent-stall deadline when the listener pauses", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.playing(audio);
    fireEvent.click(screen.getByRole("button", { name: "暂停朗读" }));
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).not.toHaveBeenCalled();
  });

  it("does not let a silent-stall deadline reload a newer paragraph", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const firstAudio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.playing(firstAudio);
    fireEvent.click(screen.getByText("查看正文").closest("button") as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "从第 2 段开始朗读" }));
    await waitFor(() => expect(screen.getByText("第 2 段", { exact: true })).toBeInTheDocument());
    const chapterAudio = document.querySelector('audio[data-active="true"]');
    expect(chapterAudio).toBe(firstAudio);
    expect(chapterAudio).toHaveAttribute("src", "/api/voice-reading/audio/chapter.mp3");
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).not.toHaveBeenCalled();
  });

  it("cancels the silent-stall deadline when the voice changes", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.playing(audio);
    fireEvent.click(screen.getByRole("button", { name: "查看全部中文音色" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "全部中文音色" })).getByRole("button", { name: "选择青涩青年音色" }));
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).not.toHaveBeenCalled();
  });

  it("cancels the silent-stall deadline when the speed changes", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const audio = document.querySelector("audio") as HTMLAudioElement;
    fireEvent.playing(audio);
    fireEvent.change(screen.getByLabelText("语速"), { target: { value: "1.25" } });
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).not.toHaveBeenCalled();
  });

  it("preserves a confirmed resume position across consecutive failures before metadata", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "duration", { configurable: true, value: 10 });
    fireEvent.loadedMetadata(audio);
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 1.75,
    });

    fireEvent.stalled(audio);
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });
    expect(load).toHaveBeenCalledTimes(1);

    audio.currentTime = 0;
    fireEvent.error(audio);
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });
    fireEvent.click(screen.getByRole("button", { name: "网络不稳定，继续朗读" }));
    expect(load).toHaveBeenCalledTimes(2);

    fireEvent.loadedMetadata(audio);

    expect(audio.currentTime).toBe(1.75);
    jest.useRealTimers();
  });

  it("does not postpone the eight-second watchdog when waiting, error, and stalled repeat", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
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
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.canPlay(audio);
    fireEvent.playing(audio);
    fireEvent.canPlay(audio);

    expect(play).toHaveBeenCalledTimes(1);
  });

  it("does not replay after a fulfilled request when the current media is already unpaused", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.canPlay(audio);
    await act(async () => {});
    Object.defineProperty(audio, "paused", { configurable: true, value: false });
    fireEvent.canPlay(audio);

    expect(play).toHaveBeenCalledTimes(1);
  });

  it("keeps a delayed autoplay promise from pausing a paragraph seek on the same chapter", async () => {
    const delayedPlay = deferred<void>();
    play.mockImplementationOnce(() => delayedPlay.promise).mockResolvedValueOnce(undefined);
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "readyState", {
      configurable: true,
      value: HTMLMediaElement.HAVE_METADATA,
    });
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 0,
    });

    fireEvent.canPlay(audio);
    expect(play).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("查看正文").closest("button") as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "从第 2 段开始朗读" }));
    expect(audio.currentTime).toBe(4);
    expect(play).toHaveBeenCalledTimes(2);

    pause.mockClear();
    await act(async () => {
      delayedPlay.resolve();
    });

    expect(pause).not.toHaveBeenCalled();
  });

  it("pauses delayed playback after a daily choice or unmount", async () => {
    const choicePlay = deferred<void>();
    play.mockImplementationOnce(() => choicePlay.promise);
    const { onSelectChoice, unmount } = renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
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

  it("does not let an old same-element recovery play promise pause a newer manual recovery", async () => {
    jest.useFakeTimers();
    const oldPlay = deferred<void>();
    const manualPlay = deferred<void>();
    play.mockImplementationOnce(() => oldPlay.promise).mockImplementationOnce(() => manualPlay.promise);
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.canPlay(audio);
    fireEvent.stalled(audio);
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });
    fireEvent.stalled(audio);
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });
    fireEvent.click(screen.getByRole("button", { name: "网络不稳定，继续朗读" }));
    expect(play).toHaveBeenCalledTimes(2);

    pause.mockClear();
    await act(async () => {
      oldPlay.resolve();
    });
    expect(pause).not.toHaveBeenCalled();

    await act(async () => {
      manualPlay.resolve();
      fireEvent.playing(audio);
    });
    expect(screen.getByRole("button", { name: "暂停朗读" })).toBeInTheDocument();
  });

  it("restarts the complete chapter when replay is selected after ended", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "currentTime", { configurable: true, writable: true, value: 9 });

    fireEvent.ended(audio);
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));

    expect(audio.currentTime).toBe(0);
    expect(play).toHaveBeenCalledTimes(1);
  });

  it("uses a user click to supersede pending autoplay without letting its old promise pause playback", async () => {
    const autoPlay = deferred<void>();
    const clickedPlay = deferred<void>();
    play.mockImplementationOnce(() => autoPlay.promise).mockImplementationOnce(() => clickedPlay.promise);
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.canPlay(audio);
    expect(play).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));
    expect(play).toHaveBeenCalledTimes(2);

    pause.mockClear();
    await act(async () => {
      autoPlay.resolve();
    });
    expect(pause).not.toHaveBeenCalled();

    await act(async () => {
      clickedPlay.resolve();
      fireEvent.playing(audio);
    });
    expect(screen.getByRole("button", { name: "暂停朗读" })).toBeInTheDocument();
  });

  it("keeps a same-element seek from letting an old play promise pause the new request", async () => {
    const oldPlay = deferred<void>();
    const seekPlay = deferred<void>();
    play.mockImplementationOnce(() => oldPlay.promise).mockImplementationOnce(() => seekPlay.promise);
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "readyState", {
      configurable: true,
      value: HTMLMediaElement.HAVE_METADATA,
    });
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 0,
    });

    fireEvent.canPlay(audio);
    fireEvent.change(screen.getByLabelText("朗读进度"), { target: { value: "1000" } });
    expect(audio.currentTime).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "播放朗读" }));
    expect(play).toHaveBeenCalledTimes(2);

    pause.mockClear();
    await act(async () => {
      oldPlay.resolve();
    });
    expect(pause).not.toHaveBeenCalled();
    await act(async () => {
      seekPlay.resolve();
      fireEvent.playing(audio);
    });
    expect(screen.getByRole("button", { name: "暂停朗读" })).toBeInTheDocument();
  });

  it("does not reload when a short waiting period returns to playing", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
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

  it("persists paragraph-local progress when the chapter clock crosses a cue", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 4.5,
    });

    fireEvent.timeUpdate(audio);

    expect(await screen.findByText("第 2 段")).toBeInTheDocument();
    expect(voiceApi.updateProgress).toHaveBeenCalledWith(
      expect.objectContaining({ paragraph_index: 1, position_ms: 500 }),
    );
  });

  it("keeps the first paragraph active during leading silence before its cue", async () => {
    voiceApi.getJob.mockResolvedValue({
      job_id: 19,
      status: "ready",
      playback_mode: "audio",
      provider: "minimax",
      model: "speech-2.8-turbo",
      message: "",
      segments: [
        { ...segments[0], start_ms: 250 },
        { ...segments[1], start_ms: 4_250 },
      ],
    });
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    fireEvent.click((await screen.findByText("查看正文")).closest("button") as HTMLButtonElement);
    const firstParagraph = await screen.findByRole("button", {
      name: "从第 1 段开始朗读",
    });
    const secondParagraph = await screen.findByRole("button", {
      name: "从第 2 段开始朗读",
    });
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 0.1,
    });

    fireEvent.timeUpdate(audio);

    expect(firstParagraph).toHaveAttribute("aria-current", "true");
    expect(secondParagraph).not.toHaveAttribute("aria-current", "true");
  });

  it("keeps one chapter audio playing while the active paragraph cue changes", async () => {
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));

    const [chapterAudio] = Array.from(document.querySelectorAll("audio"));
    expect(document.querySelectorAll("audio")).toHaveLength(1);
    expect(chapterAudio).toHaveAttribute("src", "/api/voice-reading/audio/chapter.mp3");
    Object.defineProperty(chapterAudio, "currentTime", {
      configurable: true,
      writable: true,
      value: 4.05,
    });
    play.mockClear();
    pause.mockClear();
    load.mockClear();

    fireEvent.timeUpdate(chapterAudio);

    await waitFor(() => expect(screen.getByText("第 2 段")).toBeInTheDocument());
    expect(document.querySelector("audio")).toBe(chapterAudio);
    expect(play).not.toHaveBeenCalled();
    expect(pause).not.toHaveBeenCalled();
    expect(load).not.toHaveBeenCalled();
  });

  it("keeps the silent-stall watchdog armed after crossing into the next paragraph cue", async () => {
    jest.useFakeTimers();
    renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 1,
    });
    fireEvent.playing(audio);
    fireEvent.timeUpdate(audio);

    audio.currentTime = 4.1;
    fireEvent.timeUpdate(audio);
    expect(await screen.findByText("第 2 段")).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).toHaveBeenCalledTimes(1);
  });

  it("cancels a pending recovery when the listener selects a daily choice", async () => {
    jest.useFakeTimers();
    const { onSelectChoice } = renderExperience();
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.playing(audio);
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
    await waitFor(() => expect(voiceApi.getJob).toHaveBeenCalledWith(19, expect.any(AbortSignal)));
    const audio = document.querySelector("audio") as HTMLAudioElement;

    fireEvent.playing(audio);
    unmount();
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });

    expect(load).not.toHaveBeenCalled();
    jest.useRealTimers();
  });
});
