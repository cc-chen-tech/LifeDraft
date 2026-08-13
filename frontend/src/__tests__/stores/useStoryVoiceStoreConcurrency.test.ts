import { act } from '@testing-library/react';
import { webcrypto } from 'node:crypto';
import { useMusicStore } from '@/stores/useMusicStore';
import { useStoryVoiceStore } from '@/stores/useStoryVoiceStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

type MockUtterance = SpeechSynthesisUtterance & { text: string };

function installSpeechMocks() {
  const originalSpeechSynthesis = window.speechSynthesis;
  const originalSpeechUtterance = global.SpeechSynthesisUtterance;
  const utterances: MockUtterance[] = [];
  const speech = {
    speak: jest.fn((utterance: MockUtterance) => utterances.push(utterance)),
    cancel: jest.fn(),
    pause: jest.fn(),
    resume: jest.fn(),
    getVoices: jest.fn(() => []),
  };

  class SpeechUtterance {
    text: string;
    lang = '';
    voice: SpeechSynthesisVoice | null = null;
    rate = 1;
    onend: ((this: SpeechSynthesisUtterance, event: SpeechSynthesisEvent) => void) | null = null;
    onerror: ((this: SpeechSynthesisUtterance, event: SpeechSynthesisErrorEvent) => void) | null = null;

    constructor(text: string) {
      this.text = text;
    }
  }

  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: speech,
    writable: true,
  });
  Object.defineProperty(global, 'SpeechSynthesisUtterance', {
    configurable: true,
    value: SpeechUtterance,
    writable: true,
  });

  return {
    speech,
    utterances,
    restore: () => {
      Object.defineProperty(window, 'speechSynthesis', {
        configurable: true,
        value: originalSpeechSynthesis,
        writable: true,
      });
      Object.defineProperty(global, 'SpeechSynthesisUtterance', {
        configurable: true,
        value: originalSpeechUtterance,
        writable: true,
      });
    },
  };
}

function resetStore() {
  useStoryVoiceStore.setState({
    readingState: 'idle',
    currentSource: '',
    currentContextLabel: '',
    currentAudioUrl: '',
    currentJobId: null,
    currentProvider: '',
    playbackMode: 'none',
    spokenTextLength: 0,
    currentSpeechText: '',
    errorMessage: '',
    queueText: '',
    autoReadEnabled: false,
    selectedVoiceId: 'warm_female',
    ttsProvider: '',
    backendAudioEnabled: true,
    musicDuckState: 'idle',
    musicWasPlaying: false,
    userChangedMusic: false,
  });
  useMusicStore.getState().reset();
  window.localStorage.removeItem('story_voice_e2e_provider');
}

const context = (attemptId: string, text: string) => ({
  source_type: 'current_story' as const,
  game_id: 610,
  week: 3,
  round_number: 2,
  stage: 'event',
  attempt_id: attemptId,
  text_hash: `hash-${attemptId}`,
  text,
});

describe('useStoryVoiceStore concurrency contracts', () => {
  let restoreSpeech: (() => void) | null = null;
  let speechFixture: ReturnType<typeof installSpeechMocks>;

  beforeEach(() => {
    Object.defineProperty(globalThis, 'crypto', {
      value: webcrypto,
      configurable: true,
    });
    resetStore();
    speechFixture = installSpeechMocks();
    restoreSpeech = speechFixture.restore;
  });

  afterEach(() => {
    act(() => {
      useStoryVoiceStore.getState().stopReading();
    });
    restoreSpeech?.();
    useMusicStore.getState().reset();
  });

  it('uses one settings request and lets only the newest waiting attempt start speech', async () => {
    let resolveSettings!: (response: Response) => void;
    const pendingSettings = new Promise<Response>((resolve) => {
      resolveSettings = resolve;
    });
    const fetchMock = jest.fn((input: RequestInfo | URL) => {
      if (String(input).includes('/voice-reading/settings')) return pendingSettings;
      throw new Error(`Unexpected request: ${String(input)}`);
    });
    global.fetch = fetchMock as typeof fetch;

    const older = useStoryVoiceStore.getState().startReading(context('older', '旧故事'));
    const newer = useStoryVoiceStore.getState().startReading(context('newer', '新故事'));

    await act(async () => {
      resolveSettings!(jsonResponse({ tts_provider: 'browser', backend_audio_enabled: false }));
      await Promise.all([older, newer]);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(speechFixture.speech.speak).toHaveBeenCalledTimes(1);
    expect(speechFixture.utterances[0].text).toBe('新故事');
    expect(useStoryVoiceStore.getState()).toMatchObject({
      readingState: 'playing',
      currentSpeechText: '新故事',
      currentProvider: 'browser',
    });
  });

  it('finishes each long browser-speech chunk before completing the reading', async () => {
    window.localStorage.setItem('story_voice_e2e_provider', 'browser');
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse({
        job_id: 91,
        status: 'ready',
        audio_url: null,
        playback_mode: 'browser_speech',
        provider: 'browser',
      })
    ) as typeof fetch;
    const longText = `${'甲'.repeat(205)}。${'乙'.repeat(205)}。`;

    await act(async () => {
      await useStoryVoiceStore.getState().startReading(context('long-text', longText));
    });

    expect(useStoryVoiceStore.getState().readingState).toBe('playing');
    expect(speechFixture.utterances).toHaveLength(1);
    while (speechFixture.utterances.length < 4) {
      const utterance = speechFixture.utterances.at(-1)!;
      act(() => {
        (utterance.onend as unknown as () => void)();
      });
      expect(useStoryVoiceStore.getState().readingState).toBe('playing');
    }

    act(() => {
      const utterance = speechFixture.utterances.at(-1)!;
      (utterance.onend as unknown as () => void)();
    });

    expect(speechFixture.utterances.map((utterance) => utterance.text).join('')).toBe(longText);
    expect(useStoryVoiceStore.getState()).toMatchObject({
      readingState: 'idle',
      playbackMode: 'browser_speech',
      currentSpeechText: longText,
      spokenTextLength: longText.length,
    });
  });
});
