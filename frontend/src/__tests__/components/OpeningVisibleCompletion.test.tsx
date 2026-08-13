import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StreamingText } from '@/components/game/StreamingText';
import { OpeningCompletionGate } from '@/components/game/OpeningCompletionGate';

describe('opening visible completion', () => {
  it('reports completion only after the exact final text is visible', async () => {
    const completedTexts: string[] = [];

    render(
      <StreamingText
        text="这是完整开场。"
        isStreaming={false}
        charsPerFrame={1}
        frameInterval={10}
        onDisplayComplete={(text) => completedTexts.push(text)}
      />,
    );

    await waitFor(() => {
      expect(completedTexts).toEqual(['这是完整开场。']);
    });
  });

  it('keeps start disabled until backend and visible completion both match', async () => {
    let starts = 0;
    const user = userEvent.setup();
    const { rerender } = render(
      <OpeningCompletionGate
        backendComplete={true}
        visibleComplete={false}
        onStart={() => {
          starts += 1;
        }}
      />,
    );

    const startButton = screen.getByRole('button', { name: '开始我的人生' });
    expect(startButton).toBeDisabled();
    await user.click(startButton);
    expect(starts).toBe(0);

    rerender(
      <OpeningCompletionGate
        backendComplete={true}
        visibleComplete={true}
        onStart={() => {
          starts += 1;
        }}
      />,
    );

    expect(startButton).toBeEnabled();
    await user.click(startButton);
    expect(starts).toBe(1);
  });

  it('exposes a muted native-disabled busy state until the story is ready', () => {
    render(
      <OpeningCompletionGate
        backendComplete={true}
        visibleComplete={false}
        onStart={() => undefined}
      />,
    );

    const startButton = screen.getByRole('button', { name: '开始我的人生' });
    expect(startButton).toBeDisabled();
    expect(startButton).toHaveAttribute('aria-disabled', 'true');
    expect(startButton).toHaveAttribute('aria-busy', 'true');
    expect(startButton).toHaveClass(
      'disabled:bg-[var(--surface-raised)]',
      'disabled:text-[var(--text-secondary)]',
      'disabled:cursor-not-allowed',
    );
    expect(screen.getByRole('status')).toHaveTextContent('正在显示完整故事...');
  });
});
