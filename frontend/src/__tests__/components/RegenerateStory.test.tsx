/**
 * 测试重新生成故事的组件集成
 * 
 * 测试覆盖：
 * 1. StoryAdjuster 组件调用 regenerate 回调
 * 2. ChatBar 组件调用 regenerate 回调
 * 
 * 注意：重新生成现在使用 SSE 流式生成，组件只触发回调
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StoryAdjuster } from '@/components/game/StoryAdjuster';
import { ChatBar } from '@/components/game/ChatBar';

// Mock SSE functions
jest.mock('@/lib/sse', () => ({
  streamRewrite: jest.fn().mockImplementation(async (_gameId, _fullStory, _instruction, _segment, _lang, callbacks) => {
    // Simulate streaming story
    if (callbacks?.onStory) {
      callbacks.onStory('Rewritten ');
      callbacks.onStory('story');
    }
    if (callbacks?.onComplete) {
      callbacks.onComplete({ new_story: 'Rewritten story' });
    }
  }),
  streamRegenerate: jest.fn(),
}));

// Mock useGameStore
jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(() => ({
      roundInfo: { current_round: 1 },
      storyText: 'Test story',
    })),
  },
}));

describe('StoryAdjuster 重新生成测试', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  it('点击重新生成按钮应该调用回调函数', async () => {
    const mockOnRegenerateComplete = jest.fn();
    const mockOnOpenChange = jest.fn();
    
    render(
      <StoryAdjuster
        open={true}
        onOpenChange={mockOnOpenChange}
        gameId={1}
        fullStory="Original story content"
        onRewriteComplete={jest.fn()}
        onRegenerateComplete={mockOnRegenerateComplete}
      />
    );
    
    const regenerateButton = screen.getByText('重新生成');
    fireEvent.click(regenerateButton);
    
    await waitFor(() => {
      // 应该关闭 Sheet 并触发回调
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      expect(mockOnRegenerateComplete).toHaveBeenCalled();
    });
  });
  
  it('点击改写按钮应该触发 SSE 流式改写', async () => {
    const mockOnRewriteComplete = jest.fn();
    const { streamRewrite } = require('@/lib/sse');
    
    // Setup mock to simulate SSE streaming
    (streamRewrite as jest.Mock).mockImplementation(async () => {
      return { completed: true };
    });
    
    render(
      <StoryAdjuster
        open={true}
        onOpenChange={jest.fn()}
        gameId={1}
        fullStory="Original story"
        onRewriteComplete={mockOnRewriteComplete}
        onRegenerateComplete={jest.fn()}
      />
    );
    
    const textarea = screen.getByPlaceholderText(/描述你想要的修改/);
    fireEvent.change(textarea, { target: { value: '让它更温馨' } });
    
    const rewriteButton = screen.getByText('改写故事');
    fireEvent.click(rewriteButton);
    
    // Wait for SSE to be called
    await waitFor(() => {
      expect(streamRewrite).toHaveBeenCalled();
    }, { timeout: 3000 });
  });
});

describe('ChatBar 重新生成测试', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  it('点击重新生成按钮应该调用回调函数', async () => {
    const user = userEvent.setup();
    const mockOnRegenerate = jest.fn();
    
    render(
      <ChatBar
        gameId={1}
        onSave={jest.fn()}
        onAdjustStory={jest.fn()}
        onRegenerate={mockOnRegenerate}
        isSaving={false}
      />
    );
    
    // ChatBar 初始为收起状态，点击展开按钮
    const expandButton = screen.getByRole('button');
    await user.click(expandButton);
    
    // 等待展开后找到重新生成按钮
    const regenerateButton = await screen.findByText('重新生成');
    await user.click(regenerateButton);
    
    await waitFor(() => {
      expect(mockOnRegenerate).toHaveBeenCalled();
    });
  });
});
