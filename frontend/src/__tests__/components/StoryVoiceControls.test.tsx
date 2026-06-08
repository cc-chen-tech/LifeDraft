import React from 'react';
import { webcrypto } from 'node:crypto';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StoryVoiceControls } from '@/components/game/StoryVoiceControls';
import type { ReadingContext } from '@/lib/types';
import { useStoryVoiceStore } from '@/stores/useStoryVoiceStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';

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
    useStoryVoiceStore.setState({
      readingState: 'idle',
      currentSource: '',
      currentContextLabel: '',
      currentAudioUrl: '',
      currentJobId: null,
      playbackMode: 'none',
      spokenTextLength: 0,
      currentSpeechText: '',
      errorMessage: '',
      queueText: '',
      autoReadEnabled: false,
      musicDuckState: 'idle',
      musicWasPlaying: false,
      userChangedMusic: false,
      startReading: originalStartReading,
    });
  });

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
    expect(screen.getByRole('button', { name: '朗读当前故事' })).toBeInTheDocument();
  });

  it('renders production playback controls without raw diagnostics when enabled', () => {
    render(<StoryVoiceControls currentContext={currentContext} enablePlaybackControls compact />);

    expect(screen.getByRole('region', { name: '故事朗读' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '朗读当前故事' })).toBeInTheDocument();
    expect(screen.queryByText('即将开放')).not.toBeInTheDocument();
    expect(screen.queryByText(/高质量 TTS 声音模型接入后可用/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Job:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Audio:/)).not.toBeInTheDocument();
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
});
