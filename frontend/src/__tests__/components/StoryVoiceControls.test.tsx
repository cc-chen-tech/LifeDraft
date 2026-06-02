import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { StoryVoiceControls } from '@/components/game/StoryVoiceControls';
import type { ReadingContext } from '@/lib/types';
import { useStoryVoiceStore } from '@/stores/useStoryVoiceStore';

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

describe('StoryVoiceControls', () => {
  beforeEach(() => {
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
});
