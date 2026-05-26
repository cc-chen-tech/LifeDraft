import React from 'react';
import { render, screen } from '@testing-library/react';
import { StoryVoiceControls } from '@/components/game/StoryVoiceControls';
import type { ReadingContext } from '@/lib/types';

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
});
