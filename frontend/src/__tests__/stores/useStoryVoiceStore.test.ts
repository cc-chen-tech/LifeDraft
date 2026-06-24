import { act } from '@testing-library/react';
import { webcrypto } from 'node:crypto';
import { useStoryVoiceStore } from '@/stores/useStoryVoiceStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

describe('useStoryVoiceStore', () => {
  const baseContext = {
    source_type: 'current_story',
    game_id: 101,
    week: 2,
    round_number: 3,
    stage: 'event',
    attempt_id: '2-3',
    text_hash: 'pending-client-hash',
    text: '这是一段很长的故事文本，用于确保一次完整阅读不会被截断或改写，并用于验证重复请求去重。',
  };

  const prepareSpeechMocks = () => {
    const originalSpeechSynthesis = window.speechSynthesis;
    const originalSpeechUtterance = global.SpeechSynthesisUtterance;

    class MockSpeechUtterance {
      constructor(public text: string) {}
      onend: ((this: SpeechSynthesisUtterance, event: SpeechSynthesisEvent) => void) | null = null;
      onerror: ((this: SpeechSynthesisUtterance, event: SpeechSynthesisErrorEvent) => void) | null = null;
    }

    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: {
        speak: jest.fn(),
        cancel: jest.fn(),
        pending: false,
        speaking: false,
      },
      writable: true,
    });

    Object.defineProperty(global, 'SpeechSynthesisUtterance', {
      configurable: true,
      value: MockSpeechUtterance,
      writable: true,
    });

    return () => {
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
    };
  };

  let restoreSpeechMocks: (() => void) | null = null;

  beforeEach(() => {
    Object.defineProperty(globalThis, 'crypto', {
      value: webcrypto,
      configurable: true,
    });

    jest.restoreAllMocks();
    useStoryVoiceStore.setState((state) => ({
      ...state,
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
    }));
    window.localStorage.removeItem('story_voice_e2e_provider');
    delete (global as typeof globalThis & { fetch?: unknown }).fetch;
    restoreSpeechMocks = prepareSpeechMocks();
  });

  afterEach(() => {
    restoreSpeechMocks?.();
  });

  it('dedupes repeated startReading calls for the same context while request is in flight', async () => {
    const fetchMock = jest.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/voice-reading/read')) {
        return Promise.resolve(
          jsonResponse({
            job_id: 1,
            status: 'ready',
            audio_url: '/api/voice-reading/audio/test.mp3',
            playback_mode: 'audio',
            provider: 'local',
            media_type: 'audio/mpeg',
          })
        ) as Response;
      }
      return Promise.resolve(jsonResponse({}));
    }) as jest.Mock;

    global.fetch = fetchMock;

    const { startReading } = useStoryVoiceStore.getState();

    await act(async () => {
      const p1 = startReading(baseContext);
      const p2 = startReading(baseContext);
      await p1;
      await p2;
    });

    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/voice-reading/read')).length).toBe(1);
  });

  it('uses story text as request body and keeps browser speech mode without audio URL', async () => {
    const fetchMock = jest.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes('/voice-reading/read')) {
        return Promise.resolve(
          jsonResponse({
            job_id: 7,
            status: 'ready',
            audio_url: null,
            playback_mode: 'browser_speech',
            provider: 'browser',
          })
        ) as Response;
      }
      return Promise.resolve(jsonResponse({}));
    }) as jest.Mock;

    global.fetch = fetchMock;
    window.localStorage.setItem('story_voice_e2e_provider', 'browser');

    await act(async () => {
      await useStoryVoiceStore.getState().startReading(baseContext);
    });

    const readCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/voice-reading/read'));
    expect(readCall).toBeDefined();
    const payload = JSON.parse(String((readCall?.[1] as RequestInit | undefined)?.body));
    expect(payload.context.text).toBe(baseContext.text);

    const { currentAudioUrl, currentSpeechText, playbackMode } = useStoryVoiceStore.getState();
    expect(playbackMode).toBe('browser_speech');
    expect(currentAudioUrl).toBe('');
    expect(currentSpeechText).toBe(baseContext.text);
  });

  it('loads runtime settings before first read so browser fallback starts without a backend read roundtrip', async () => {
    const fetchMock = jest.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(
          jsonResponse({
            tts_provider: 'browser',
            backend_audio_enabled: false,
            auto_read_enabled: false,
            selected_voice_color: 'warm_female',
            uploaded_voice_available: false,
            available_voice_colors: ['warm_female', 'calm_male', 'clear_neutral'],
          })
        ) as Response;
      }
      if (url.includes('/voice-reading/read')) {
        return Promise.resolve(
          jsonResponse({
            job_id: 99,
            status: 'ready',
            audio_url: '/api/voice-reading/audio/should-not-be-used.mp3',
            playback_mode: 'audio',
            provider: 'minimax',
          })
        ) as Response;
      }
      return Promise.resolve(jsonResponse({}));
    }) as jest.Mock;

    global.fetch = fetchMock;

    await act(async () => {
      await useStoryVoiceStore.getState().startReading(baseContext);
    });

    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/voice-reading/settings'))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/voice-reading/read'))).toBe(false);
    expect(window.speechSynthesis.speak).toHaveBeenCalled();
    expect(useStoryVoiceStore.getState()).toMatchObject({
      readingState: 'playing',
      currentProvider: 'browser',
      playbackMode: 'browser_speech',
      currentSpeechText: baseContext.text,
    });
  });
});
