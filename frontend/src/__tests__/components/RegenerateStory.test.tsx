/**
 * 测试重新生成故事的组件集成
 *
 * 注意：重新生成现在使用 SSE 流式生成，组件只触发回调
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatBar } from '@/components/game/ChatBar';
import { useGameStore } from '@/stores/useGameStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

const STORE_METHODS = ['syncState'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useGameStore.setState({
    roundInfo: { current_round: 1 },
    storyText: 'Test story',
  });
}

describe('ChatBar 内联改写测试', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.resetAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  it('点击改写按钮应该触发 SSE 流式改写', async () => {
    const user = userEvent.setup();
    const mockOnRewriteComplete = jest.fn();
    (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
      'data: [DONE]\n\n',
    ]));

    render(
      <ChatBar
        gameId={1}
        onSave={jest.fn()}
        onRegenerate={jest.fn()}
        storyText="Original story"
        onRewriteComplete={mockOnRewriteComplete}
      />
    );

    await user.click(screen.getByLabelText('打开聊天'));
    await user.click(await screen.findByTestId('rewrite-button'));

    const textarea = screen.getByPlaceholderText(/描述你想要的修改/);
    fireEvent.change(textarea, { target: { value: '让它更温馨' } });

    const rewriteButton = screen.getByText('改写故事');
    fireEvent.click(rewriteButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/rewrite-stream'),
        expect.anything()
      );
    }, { timeout: 3000 });
  });

  it('每日改写完成后返回新选项和递增 revision', async () => {
    const user = userEvent.setup();
    const mockOnRewriteComplete = jest.fn();
    (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
      'event: complete\n',
      'data: {"new_story":"新正文","event":{"event_id":"daily-1","revision":2,"story_date":"2026-08-13","options":[{"text":"新选项A"},{"text":"新选项B"}]}}\n\n',
      'data: [DONE]\n\n',
    ]));

    render(
      <ChatBar
        gameId={1}
        storyText="旧正文"
        isDailyTimeline
        onRewriteComplete={mockOnRewriteComplete}
      />
    );

    await user.click(screen.getByLabelText('打开聊天'));
    await user.click(await screen.findByTestId('rewrite-button'));
    fireEvent.change(screen.getByPlaceholderText(/描述你想要的修改/), {
      target: { value: '重写今天' },
    });
    fireEvent.click(screen.getByText('改写故事'));

    await waitFor(() => {
      expect(mockOnRewriteComplete).toHaveBeenCalledWith(
        '新正文',
        expect.objectContaining({
          event_id: 'daily-1',
          revision: 2,
          options: [{ text: '新选项A' }, { text: '新选项B' }],
        }),
      );
    });
  });
});

describe('ChatBar 重新生成测试', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.resetAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  it('点击重新生成按钮应该调用回调函数', async () => {
    const user = userEvent.setup();
    const mockOnRegenerate = jest.fn();

    render(
      <ChatBar
        gameId={1}
        onSave={jest.fn()}
        onRegenerate={mockOnRegenerate}
        isSaving={false}
      />
    );

    const expandButton = screen.getByLabelText('打开聊天');
    await user.click(expandButton);

    const regenerateButton = await screen.findByText('重新生成');
    await user.click(regenerateButton);

    await waitFor(() => {
      expect(mockOnRegenerate).toHaveBeenCalled();
    });
  });
});
