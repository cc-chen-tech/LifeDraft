import React from 'react';
import { webcrypto } from 'node:crypto';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StoryVoiceControls } from '@/components/game/StoryVoiceControls';
import type { ReadingContext } from '@/lib/types';
import { useStoryVoiceStore } from '@/stores/useStoryVoiceStore';
import { errorResponse, jsonResponse } from '@/__tests__/helpers/fetch';

const currentContext: ReadingContext = {
  source_type: 'current_story',
  game_id: 1,
  week: 1,
  round_number: 1,
  stage: 'event',
  attempt_id: '1-1',
  text_hash: 'hash',
  text: '一段当前故事。',
};

const originalStartReading = useStoryVoiceStore.getState().startReading;

describe('StoryVoiceControls', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'crypto', {
      value: webcrypto,
      configurable: true,
    });
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(jsonResponse({
          auto_read_enabled: false,
          selected_voice_color: 'warm_female',
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    jest.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
    jest.spyOn(window.HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
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
      musicDuckState: 'idle',
      musicWasPlaying: false,
      userChangedMusic: false,
      startReading: originalStartReading,
    });
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  function installSpeechSynthesisMock(voices: Array<Partial<SpeechSynthesisVoice>> = []) {
    const spoken: SpeechSynthesisUtterance[] = [];
    const speech = {
      cancel: jest.fn(),
      pause: jest.fn(),
      resume: jest.fn(),
      speak: jest.fn((utterance: SpeechSynthesisUtterance) => {
        spoken.push(utterance);
      }),
      getVoices: jest.fn(() => voices as SpeechSynthesisVoice[]),
    };
    class FakeSpeechSynthesisUtterance {
      text: string;
      lang = '';
      rate = 1;
      voice: SpeechSynthesisVoice | null = null;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(text: string) {
        this.text = text;
      }
    }
    Object.defineProperty(window, 'speechSynthesis', {
      value: speech,
      configurable: true,
    });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', {
      value: FakeSpeechSynthesisUtterance,
      configurable: true,
    });
    Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', {
      value: FakeSpeechSynthesisUtterance,
      configurable: true,
    });
    return { speech, spoken };
  }

  it('shows a polished unavailable preview instead of raw playback diagnostics by default', () => {
    render(<StoryVoiceControls currentContext={currentContext} compact />);

    expect(screen.getByRole('region', { name: '故事朗读预览' })).toBeInTheDocument();
    expect(screen.getByText('故事朗读')).toBeInTheDocument();
    expect(screen.getByText(/高质量 TTS 声音模型接入后可用/)).toBeInTheDocument();
    expect(screen.queryByText(/Job:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Audio:/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '朗读当前故事' })).not.toBeInTheDocument();
  });

  it('keeps diagnostic controls opt-in for tests', () => {
    render(<StoryVoiceControls currentContext={currentContext} showTestControls />);

    expect(screen.getByTestId('voice-reading-state')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '朗读故事' })).toBeInTheDocument();
  });

  it('renders production playback controls without raw diagnostics when enabled', () => {
    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    expect(screen.getByRole('region', { name: '故事朗读' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '朗读故事' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '停止朗读' })).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: '自动朗读' })).toBeInTheDocument();
    expect(screen.queryByText('即将开放')).not.toBeInTheDocument();
    expect(screen.queryByText(/高质量 TTS 声音模型接入后可用/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Job:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Audio:/)).not.toBeInTheDocument();
  });

  it('disables reading while the current story is still generating', () => {
    render(
      <StoryVoiceControls
        currentContext={currentContext}
        enablePlaybackControls
        compact
        isStoryReady={false}
      />
    );

    const readButton = screen.getByRole('button', { name: '故事生成完成后可朗读' });
    expect(readButton).toBeDisabled();
  });

  it('labels backend audio preparation without pretending playback already started', () => {
    useStoryVoiceStore.setState({
      readingState: 'loading',
      currentSource: 'current_story',
      playbackMode: 'none',
    });

    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    expect(screen.getByRole('button', { name: '正在生成语音' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: '朗读故事' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '正在朗读' })).not.toBeInTheDocument();
  });

  it('uses the primary button for pause while backend audio is playing', () => {
    useStoryVoiceStore.setState({
      readingState: 'playing',
      currentSource: 'current_story',
      currentAudioUrl: '/api/voice-reading/audio/job-1.mp3',
      playbackMode: 'audio',
    });

    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    expect(screen.getByRole('button', { name: '暂停朗读' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: '朗读故事' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '正在朗读' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '停止' })).toBeInTheDocument();
  });

  it('keeps retry available when a failed audio attempt later emits ended', () => {
    render(<StoryVoiceControls currentContext={currentContext} showTestControls />);

    act(() => {
      useStoryVoiceStore.setState({
        readingState: 'playing',
        currentAudioUrl: '/api/voice-reading/audio/job-1.wav',
        currentJobId: 1,
        playbackMode: 'audio',
        musicDuckState: 'ducked',
      });
    });

    act(() => {
      useStoryVoiceStore.getState().failReading();
    });

    expect(screen.getByTestId('voice-reading-state')).toHaveTextContent('failed');
    expect(screen.getByTestId('voice-reading-audio-url')).toBeEmptyDOMElement();
    expect(screen.getByRole('button', { name: '重试朗读' })).toBeVisible();

    fireEvent.ended(screen.getByTestId('voice-reading-audio-player'));

    expect(screen.getByTestId('voice-reading-state')).toHaveTextContent('failed');
    expect(screen.getByRole('button', { name: '重试朗读' })).toBeVisible();
  });

  it('keeps generated backend audio ready when autoplay is blocked', async () => {
    const playSpy = window.HTMLMediaElement.prototype.play as jest.Mock;
    playSpy.mockRejectedValue(new DOMException('autoplay blocked', 'NotAllowedError'));
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(jsonResponse({
          auto_read_enabled: false,
          selected_voice_color: 'warm_female',
        }));
      }
      if (url.includes('/voice-reading/read')) {
        return Promise.resolve(jsonResponse({
          job_id: 1,
          status: 'ready',
          audio_url: '/api/voice-reading/audio/test.mp3',
          playback_mode: 'audio',
          provider: 'minimax',
          media_type: 'audio/mpeg',
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });

    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    fireEvent.click(screen.getByRole('button', { name: '朗读故事' }));

    await waitFor(() => {
      expect(useStoryVoiceStore.getState().readingState).toBe('ready');
    });
    expect(playSpy).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '播放语音' })).toBeEnabled();
    expect(useStoryVoiceStore.getState().currentAudioUrl).toBe(
      '/api/voice-reading/audio/test.mp3'
    );
    expect(screen.queryByRole('button', { name: '重试朗读' })).not.toBeInTheDocument();

  });

  it('uses the selected browser speech voice when backend audio falls back to browser speech', async () => {
    const { speech, spoken } = installSpeechSynthesisMock([
      { name: 'Chinese Xiaoxiao Natural', lang: 'zh-CN' },
      { name: 'Chinese Yunxi Male Natural', lang: 'zh-CN' },
      { name: 'English Narrator', lang: 'en-US' },
    ]);
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(jsonResponse({
          auto_read_enabled: false,
          selected_voice_color: 'calm_male',
        }));
      }
      if (url.includes('/voice-reading/read')) {
        return Promise.resolve(jsonResponse({
          job_id: 7,
          status: 'ready',
          audio_url: null,
          playback_mode: 'browser_speech',
          provider: 'browser',
          media_type: 'text/plain',
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    useStoryVoiceStore.setState({ selectedVoiceId: 'calm_male' });

    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    fireEvent.click(screen.getByRole('button', { name: '朗读故事' }));

    await waitFor(() => {
      expect(speech.speak).toHaveBeenCalledTimes(1);
    });
    expect(spoken[0].voice?.name).toBe('Chinese Yunxi Male Natural');
    expect(useStoryVoiceStore.getState().playbackMode).toBe('browser_speech');
  });

  it('falls back to browser speech when the backend voice request is unavailable', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    const { speech } = installSpeechSynthesisMock([
      { name: 'Chinese Xiaoxiao Natural', lang: 'zh-CN' },
    ]);
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(jsonResponse({
          auto_read_enabled: false,
          selected_voice_color: 'warm_female',
        }));
      }
      if (url.includes('/voice-reading/read')) {
        return Promise.resolve(errorResponse(503, 'MiniMax TTS unavailable'));
      }
      return Promise.resolve(jsonResponse({}));
    });

    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    await user.click(screen.getByRole('button', { name: '朗读故事' }));
    await act(async () => {
      jest.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    await act(async () => {
      jest.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(speech.speak).toHaveBeenCalledTimes(1);
    });
    expect(useStoryVoiceStore.getState().readingState).toBe('playing');
    expect(useStoryVoiceStore.getState().currentProvider).toBe('browser');
    expect(useStoryVoiceStore.getState().errorMessage).toBe('');
  });

  it('regenerates the active reading immediately when voice changes mid-playback', async () => {
    const playSpy = window.HTMLMediaElement.prototype.play as jest.Mock;
    playSpy.mockResolvedValue(undefined);
    (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(jsonResponse({
          auto_read_enabled: false,
          selected_voice_color: 'warm_female',
        }));
      }
      if (url.includes('/voice-reading/read')) {
        const payload = JSON.parse(String(init?.body ?? '{}'));
        return Promise.resolve(jsonResponse({
          job_id: payload.voice_id === 'calm_male' ? 2 : 1,
          status: 'ready',
          audio_url: `/api/voice-reading/audio/${payload.voice_id}.mp3`,
          playback_mode: 'audio',
          provider: 'minimax',
          media_type: 'audio/mpeg',
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });

    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    fireEvent.click(screen.getByRole('button', { name: '朗读故事' }));
    await waitFor(() => {
      expect(useStoryVoiceStore.getState().readingState).toBe('playing');
    });

    fireEvent.change(screen.getByRole('combobox', { name: '选择朗读声音' }), {
      target: { value: 'calm_male' },
    });

    await waitFor(() => {
      const readCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
        String(url).includes('/voice-reading/read')
      );
      expect(readCalls.length).toBeGreaterThanOrEqual(2);
      const latestPayload = JSON.parse(String(readCalls.at(-1)?.[1]?.body ?? '{}'));
      expect(latestPayload.voice_id).toBe('calm_male');
    });
    expect(useStoryVoiceStore.getState().currentAudioUrl).toBe(
      '/api/voice-reading/audio/calm_male.mp3'
    );
  });

  it('sends a backend-compatible SHA-256 text hash when auto-reading completed story text', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes('/voice-reading/settings')) {
        return Promise.resolve(jsonResponse({
          auto_read_enabled: true,
          selected_voice_color: 'warm_female',
        }));
      }
      if (url.includes('/voice-reading/read')) {
        return Promise.resolve(jsonResponse({
          job_id: 1,
          status: 'ready',
          audio_url: '/api/voice-reading/audio/test.mp3',
          playback_mode: 'audio',
          provider: 'minimax',
          media_type: 'audio/mpeg',
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    useStoryVoiceStore.setState({
      autoReadEnabled: true,
    } as never);

    render(
      <StoryVoiceControls
        currentContext={currentContext}
        autoReadText="一段当前故事。"
        autoReadReady
        enablePlaybackControls
      />
    );

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.some(([url]) =>
        String(url).includes('/voice-reading/read')
      )).toBe(true);
    });
    const readCall = (global.fetch as jest.Mock).mock.calls.find(([url]) =>
      String(url).includes('/voice-reading/read')
    );
    const payload = JSON.parse(String(readCall?.[1]?.body ?? '{}'));
    expect(payload.context).toMatchObject({
      text: '一段当前故事。',
      text_hash: '95813215c6b945ae5e1746a1219579a9884fd99997cf398d046f071a819c149e',
    });
  });

  it('keeps a local auto-read toggle when stale settings finish loading later', async () => {
    let resolveSettings: (value: Response) => void = () => undefined;
    const settingsPromise = new Promise<Response>((resolve) => {
      resolveSettings = resolve;
    });
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/voice-reading/settings')) {
        return settingsPromise;
      }
      if (url.includes('/voice-reading/read')) {
        return Promise.resolve(jsonResponse({
          job_id: 1,
          status: 'ready',
          audio_url: '/api/voice-reading/audio/test.mp3',
          playback_mode: 'audio',
          provider: 'minimax',
          media_type: 'audio/mpeg',
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });

    const { rerender } = render(
      <StoryVoiceControls
        currentContext={currentContext}
        autoReadText=""
        autoReadReady={false}
        showTestControls
      />
    );

    fireEvent.click(screen.getByRole('checkbox', { name: '自动朗读' }));
    resolveSettings(jsonResponse({
      auto_read_enabled: false,
      selected_voice_color: 'warm_female',
    }));
    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.some(([url]) =>
        String(url).includes('/voice-reading/settings')
      )).toBe(true);
    });

    rerender(
      <StoryVoiceControls
        currentContext={currentContext}
        autoReadText="一段当前故事。"
        autoReadReady
        showTestControls
      />
    );

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.some(([url]) =>
        String(url).includes('/voice-reading/read')
      )).toBe(true);
    });
  });
});
