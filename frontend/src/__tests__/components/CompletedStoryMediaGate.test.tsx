import { render, waitFor } from '@testing-library/react';
import { CompletedStoryMediaGate } from '@/components/game/CompletedStoryMediaGate';
import { useMusicStore } from '@/stores/useMusicStore';
import { useStoryVoiceStore } from '@/stores/useStoryVoiceStore';

const context = {
  source_type: 'current_story' as const,
  game_id: 71,
  week: 3,
  round_number: 1,
  stage: 'event' as const,
  attempt_id: '3-1',
  text_hash: 'final-hash',
  text: '最终完成的故事文本。',
};

describe('CompletedStoryMediaGate without mocks', () => {
  beforeEach(() => {
    useMusicStore.setState({ activeStoryText: null, activeGameId: null });
    useStoryVoiceStore.setState({
      readingState: 'idle',
      currentSource: '',
      currentAudioUrl: '',
      activeReadingContext: null,
      activeAutoReadText: '',
      activeAutoReadReady: false,
    });
  });

  it('publishes the same final text to voice and music only when complete', async () => {
    render(
      <CompletedStoryMediaGate
        text={context.text}
        context={context}
        storyReady
        storyBusy={false}
        isViewingHistory={false}
      />,
    );

    await waitFor(() => {
      expect(useMusicStore.getState().activeStoryText).toBe(context.text);
      expect(useStoryVoiceStore.getState().activeAutoReadText).toBe(context.text);
      expect(useStoryVoiceStore.getState().activeAutoReadReady).toBe(true);
    });
  });

  it('stops stale current-story narration and clears both targets during regeneration', async () => {
    useMusicStore.setState({ activeStoryText: '旧故事文本', activeGameId: 71 });
    useStoryVoiceStore.setState({
      readingState: 'playing',
      currentSource: 'current_story',
      currentAudioUrl: '/api/voice-reading/audio/old.mp3',
      activeReadingContext: { ...context, text: '旧故事文本' },
      activeAutoReadText: '旧故事文本',
      activeAutoReadReady: true,
    });

    render(
      <CompletedStoryMediaGate
        text="尚未完成的替换文本"
        context={{ ...context, text: '尚未完成的替换文本' }}
        storyReady={false}
        storyBusy
        isViewingHistory={false}
      />,
    );

    await waitFor(() => {
      expect(useStoryVoiceStore.getState().readingState).toBe('idle');
      expect(useStoryVoiceStore.getState().currentAudioUrl).toBe('');
      expect(useStoryVoiceStore.getState().activeReadingContext).toBeNull();
      expect(useStoryVoiceStore.getState().activeAutoReadReady).toBe(false);
      expect(useMusicStore.getState().activeStoryText).toBeNull();
    });
  });

  it('keeps history text out of generated-music targeting', async () => {
    render(
      <CompletedStoryMediaGate
        text="历史正文"
        context={{ ...context, source_type: 'history_round', text: '历史正文' }}
        storyReady={false}
        storyBusy={false}
        isViewingHistory
      />,
    );

    await waitFor(() => {
      expect(useMusicStore.getState().activeStoryText).toBeNull();
      expect(useStoryVoiceStore.getState().activeReadingContext?.source_type).toBe('history_round');
      expect(useStoryVoiceStore.getState().activeAutoReadReady).toBe(false);
    });
  });
});
