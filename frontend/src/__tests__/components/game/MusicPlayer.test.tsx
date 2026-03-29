/**
 * MusicPlayer 组件测试 - 极简版
 * 
 * 原则：只验证用户可见的行为，不验证内部实现
 */
import { render, screen, waitFor } from '@testing-library/react';
import { MusicPlayer } from '@/components/game/MusicPlayer';

// 只 mock Audio API
global.Audio = class MockAudio {
  src = '';
  paused = true;
  play = jest.fn().mockResolvedValue(undefined);
  pause = jest.fn();
  constructor(url?: string) {
    this.src = url || '';
  }
} as any;

describe('MusicPlayer', () => {
  it('应该渲染音乐播放器组件', async () => {
    render(<MusicPlayer storyText="Test story" />);

    // 验证组件渲染
    await waitFor(() => {
      expect(screen.getByText('场景音乐')).toBeInTheDocument();
    });
  });

  it('没有故事文本时不应该渲染', () => {
    const { container } = render(<MusicPlayer storyText="" />);
    expect(container.firstChild).toBeNull();
  });
});
