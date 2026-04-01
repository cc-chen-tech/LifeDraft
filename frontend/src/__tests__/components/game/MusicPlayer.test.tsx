/**
 * MusicPlayer 组件测试 - 基础版本
 * 
 * 由于组件直接导入 API 函数，mock 比较复杂
 * 这里只测试基本的渲染行为
 */
import { render, screen, waitFor } from '@testing-library/react';
import { MusicPlayer } from '@/components/game/MusicPlayer';

// Mock Audio API
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
  it('应该渲染音乐播放器', async () => {
    render(<MusicPlayer storyText="Test story" />);

    // 验证组件渲染（即使 API 调用失败，也应该显示播放器框架）
    await waitFor(() => {
      expect(screen.getByText('场景音乐')).toBeInTheDocument();
    });
  });

  it('没有故事文本时不应该渲染', () => {
    const { container } = render(<MusicPlayer storyText="" />);
    expect(container.firstChild).toBeNull();
  });
});
