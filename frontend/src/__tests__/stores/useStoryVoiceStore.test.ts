import { webcrypto } from "node:crypto";
import { api } from "@/lib/api";
import type { ReadingContext, StoryVoiceReadingResponse } from "@/lib/types";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";

const baseContext: ReadingContext = {
  source_type: "current_story",
  game_id: 101,
  week: 3,
  round_number: 2,
  stage: "event",
  attempt_id: "attempt-1",
  text: "雨夜  码头\n旧账册被翻开",
};

const readyResponse: StoryVoiceReadingResponse = {
  job_id: 42,
  status: "ready",
  audio_url: "/api/voice-reading/audio/voice-42.wav",
  asset_id: 7,
  duration_ms: 1200,
  error_code: null,
  message: "ready",
};

function resetStoryVoiceStore() {
  useStoryVoiceStore.setState({
    readingState: "idle",
    currentSource: "",
    currentContextLabel: "",
    currentAudioUrl: "",
    currentJobId: null,
    errorMessage: "",
    queueText: "",
    autoReadEnabled: false,
    musicDuckState: "idle",
    musicWasPlaying: false,
    userChangedMusic: false,
  });
}

describe("useStoryVoiceStore", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "crypto", {
      configurable: true,
      value: webcrypto,
    });
    resetStoryVoiceStore();
    jest.restoreAllMocks();
  });

  it("requests backend reading with normalized text hash and stores ready audio state", async () => {
    const requestReading = jest
      .spyOn(api.voice_reading, "requestReading")
      .mockResolvedValue(readyResponse);

    await useStoryVoiceStore.getState().startReading(baseContext);

    const request = requestReading.mock.calls[0][0];
    expect(request.voice_id).toBe("warm_female");
    expect(request.auto_play).toBe(true);
    expect(request.context.text_hash).toMatch(/^[a-f0-9]{64}$/);
    expect(request.context.text_hash).not.toBe(baseContext.text);

    expect(useStoryVoiceStore.getState()).toMatchObject({
      readingState: "playing",
      currentSource: "current_story",
      currentContextLabel: "week=3 round=2 stage=event",
      currentAudioUrl: "/api/voice-reading/audio/voice-42.wav",
      currentJobId: 42,
      errorMessage: "",
    });
  });

  it("records failure and retries by resubmitting the last reading context", async () => {
    const requestReading = jest
      .spyOn(api.voice_reading, "requestReading")
      .mockRejectedValueOnce(new Error("provider unavailable"))
      .mockResolvedValueOnce({ ...readyResponse, job_id: 43 });

    await useStoryVoiceStore.getState().startReading(baseContext);
    expect(useStoryVoiceStore.getState()).toMatchObject({
      readingState: "failed",
      errorMessage: "provider unavailable",
    });

    await useStoryVoiceStore.getState().retryReading();

    expect(requestReading).toHaveBeenCalledTimes(2);
    expect(requestReading.mock.calls[1][0].context).toMatchObject({
      source_type: "current_story",
      game_id: 101,
      week: 3,
      round_number: 2,
      stage: "event",
      attempt_id: "attempt-1",
      text: baseContext.text,
    });
    expect(useStoryVoiceStore.getState()).toMatchObject({
      readingState: "playing",
      currentJobId: 43,
      errorMessage: "",
    });
  });

  it("restores ducked music on stop unless the user changed music manually", async () => {
    jest.spyOn(api.voice_reading, "requestReading").mockResolvedValue(readyResponse);

    useStoryVoiceStore.getState().simulateMusicPlaying();
    await useStoryVoiceStore.getState().startReading(baseContext);
    expect(useStoryVoiceStore.getState().musicDuckState).toBe("ducked");

    useStoryVoiceStore.getState().stopReading();
    expect(useStoryVoiceStore.getState().musicDuckState).toBe("restored");

    useStoryVoiceStore.getState().simulateMusicPlaying();
    await useStoryVoiceStore.getState().startReading(baseContext);
    useStoryVoiceStore.getState().userPauseMusicDuringReading();
    useStoryVoiceStore.getState().stopReading();

    expect(useStoryVoiceStore.getState().musicDuckState).toBe("user_paused");
  });
});
