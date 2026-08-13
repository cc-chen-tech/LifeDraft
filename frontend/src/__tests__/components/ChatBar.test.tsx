/**
 * ChatBar Component Tests
 * Tests all interactive elements of the chat bar component
 */
import React from 'react';
import { ReadableStream } from 'node:stream/web';
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatBar } from '@/components/game/ChatBar';
import { INPUT_LIMITS } from '@/types/input-limits.generated';
import { useGameStore } from '@/stores/useGameStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

const STORE_METHODS = ['syncState'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function createControlledSSEStream() {
  const encoder = new TextEncoder();
  let controllerRef: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controllerRef = controller;
    },
  });

  return {
    stream,
    enqueue(chunk: string) {
      controllerRef?.enqueue(encoder.encode(chunk));
    },
    close() {
      controllerRef?.close();
    },
    error(error: Error) {
      controllerRef?.error(error);
    },
  };
}

function setupDefaultState() {
  useGameStore.setState({
    roundInfo: { current_round: 1 },
    storyText: 'Test story',
  });
}

describe('ChatBar', () => {
  let storeSpy: StoreSpy;
  const mockOnSave = jest.fn();
  const mockOnRegenerate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({}));
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  describe('Collapsed state', () => {
    it('renders collapsed quick action buttons when not expanded', () => {
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      const expandButton = screen.getByLabelText('打开聊天');
      expect(expandButton).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重新生成' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '改写' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '人生总结' })).toBeInTheDocument();
    });

    it('does not render when gameId is null', () => {
      const { container } = render(
        <ChatBar
          gameId={null}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      expect(container.firstChild).toBeNull();
    });

    it('calls onRegenerate from collapsed quick action', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Test story"
        />
      );

      await user.click(screen.getByRole('button', { name: '重新生成' }));

      expect(mockOnRegenerate).toHaveBeenCalled();
    });

    it('hides every chat control while busy, then restores the mounted chat history when ready', async () => {
      const user = userEvent.setup();
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: '助手回复' }));
      const { rerender } = render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Partial streamed story"
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));
      await user.type(screen.getByPlaceholderText('向剧情助手提问...'), '这段故事怎么样？');
      await user.click(screen.getByLabelText('发送消息'));
      expect(await screen.findByText('这段故事怎么样？')).toBeInTheDocument();

      const rewriteButton = screen
        .getAllByTestId('rewrite-button')
        .find((button) => !button.hasAttribute('disabled'));
      expect(rewriteButton).toBeDefined();
      await user.click(rewriteButton!);
      expect(await screen.findByTestId('inline-rewrite-sheet')).toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Partial streamed story"
          isStoryBusy
        />
      );

      expect(screen.queryByTestId('chat-bar-launcher')).not.toBeInTheDocument();
      expect(screen.queryByTestId('chat-bar-panel')).not.toBeInTheDocument();
      expect(screen.queryByTestId('inline-rewrite-sheet')).not.toBeInTheDocument();
      expect(screen.queryByTestId('life-summary-panel')).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '打开聊天' })).not.toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Partial streamed story"
        />
      );

      expect(await screen.findByTestId('chat-bar-launcher')).toBeInTheDocument();
      await user.click(screen.getByLabelText('打开聊天'));
      expect(await screen.findByTestId('chat-bar-panel')).toBeInTheDocument();
      expect(screen.getByText('这段故事怎么样？')).toBeInTheDocument();
    });

    it('stays mounted but hides every control in history view, then restores chat history', async () => {
      const user = userEvent.setup();
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: '助手回复' }));
      const { rerender } = render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Current story"
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));
      await user.type(screen.getByPlaceholderText('向剧情助手提问...'), '请记住这段对话');
      await user.click(screen.getByLabelText('发送消息'));
      expect(await screen.findByText('请记住这段对话')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '改写' }));
      expect(await screen.findByTestId('inline-rewrite-sheet')).toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Current story"
          isViewingHistory
        />
      );

      expect(screen.queryByTestId('chat-bar-launcher')).not.toBeInTheDocument();
      expect(screen.queryByTestId('chat-bar-panel')).not.toBeInTheDocument();
      expect(screen.queryByTestId('inline-rewrite-sheet')).not.toBeInTheDocument();
      expect(screen.queryByTestId('life-summary-panel')).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '打开聊天' })).not.toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Current story"
        />
      );

      expect(await screen.findByTestId('chat-bar-launcher')).toBeInTheDocument();
      await user.click(screen.getByLabelText('打开聊天'));
      expect(await screen.findByTestId('chat-bar-panel')).toBeInTheDocument();
      expect(screen.getByText('请记住这段对话')).toBeInTheDocument();
      expect(screen.queryByTestId('inline-rewrite-sheet')).not.toBeInTheDocument();
    });

    it('closes an open summary panel during busy work and fades the launcher and panel back without reopening it', async () => {
      const user = userEvent.setup();
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: '这一周的总结。',
        start_week: 4,
        end_week: 4,
      }));
      const { rerender } = render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Partial streamed story"
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));
      expect(await screen.findByTestId('life-summary-panel')).toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Partial streamed story"
          isStoryBusy
        />
      );

      expect(screen.queryByTestId('life-summary-panel')).not.toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Partial streamed story"
        />
      );

      await screen.findByTestId('chat-bar-launcher');
      expect(screen.queryByTestId('life-summary-panel')).not.toBeInTheDocument();

      await user.click(screen.getByLabelText('打开聊天'));
      expect((await screen.findByTestId('chat-bar-panel'))).toHaveAttribute(
        'data-variant',
        'overlay',
      );
    });

    it('opens rewrite sheet from collapsed quick action', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Test story"
        />
      );

      await user.click(screen.getByRole('button', { name: '改写' }));

      expect(await screen.findByTestId('inline-rewrite-sheet')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '改写故事' })).toBeInTheDocument();
    });

    it('surfaces rewrite stream progress messages instead of a static loading toast', async () => {
      const rewriteStream = createControlledSSEStream();
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        body: rewriteStream.stream,
      });

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="原始故事。"
        />
      );

      await user.click(screen.getByRole('button', { name: '改写' }));
      await user.type(
        await screen.findByPlaceholderText(/描述你想要的修改/),
        '增加对话'
      );
      await user.click(screen.getByRole('button', { name: '改写故事' }));

      const rewriteRequest = (global.fetch as jest.Mock).mock.calls[0][1] as RequestInit;
      expect(JSON.parse(String(rewriteRequest.body))).toMatchObject({
        full_story: '原始故事。',
        segment_to_replace: '',
        user_instruction: '增加对话',
      });

      act(() => {
        rewriteStream.enqueue(
          'data: {"type":"status","status":{"phase":"analyzing","message":"正在理解改写要求"}}\n\n'
        );
      });
      expect((await screen.findAllByText('正在理解改写要求')).length).toBeGreaterThan(0);
      act(() => {
        rewriteStream.enqueue(
          'data: {"type":"status","status":{"phase":"rewriting","message":"正在生成改写文本"}}\n\n'
        );
      });
      expect((await screen.findAllByText('正在生成改写文本')).length).toBeGreaterThan(0);
    });

    it('replaces streamed rewrite text when the server retries the rewrite', async () => {
      const rewriteStream = createControlledSSEStream();
      const onRewriteComplete = jest.fn();
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        body: rewriteStream.stream,
      });

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="原始故事。"
          onRewriteComplete={onRewriteComplete}
        />
      );

      await user.click(screen.getByRole('button', { name: '改写' }));
      await user.type(
        await screen.findByPlaceholderText(/描述你想要的修改/),
        '增加对话'
      );
      await user.click(screen.getByRole('button', { name: '改写故事' }));

      act(() => {
        rewriteStream.enqueue('data: {"type":"story_chunk","content":"首稿"}\n\n');
        rewriteStream.enqueue('data: {"type":"status","status":{"phase":"retry"}}\n\n');
        rewriteStream.enqueue('data: {"type":"story_chunk","content":"重写稿"}\n\n');
      });

      await waitFor(() => {
        expect(onRewriteComplete).toHaveBeenLastCalledWith('重写稿');
      });
      expect(onRewriteComplete).not.toHaveBeenCalledWith('首稿重写稿');
    });

    it('opens dedicated summary panel and calls summary API from collapsed quick action', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Test summary content',
        start_week: 1,
        end_week: 10,
      }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Test story"
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));

      expect(await screen.findByTestId('life-summary-panel')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-bar-panel')).not.toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/向剧情助手提问/i)).not.toBeInTheDocument();
      expect(mockOnRegenerate).not.toHaveBeenCalled();
      await waitFor(() => {
        const calls = (global.fetch as jest.Mock).mock.calls;
        const summaryCall = calls.find((c: unknown[]) => (c[0] as string).includes('/summary'));
        expect(summaryCall).toBeDefined();
      });
    });

    it('clears summary loading and displays a retryable error when the request aborts', async () => {
      const abortError = new Error('The operation was aborted.');
      abortError.name = 'AbortError';
      (global.fetch as jest.Mock).mockRejectedValue(abortError);

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          storyText="Test story"
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));

      expect(await screen.findByText('生成总结时出了点问题，请稍后再试。')).toBeInTheDocument();
      expect(screen.queryByText('正在生成总结...')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: '人生总结' })).toBeEnabled();
    });
  });

  describe('Expanded state', () => {
    it('uses the generated story-dialogue limit and shows remaining characters', async () => {
      const user = userEvent.setup();
      render(<ChatBar gameId={1} storyText="Test story" />);

      await user.click(screen.getByLabelText('打开聊天'));

      expect(screen.getByPlaceholderText('向剧情助手提问...')).not.toHaveAttribute('maxlength');
      expect(screen.getByText(`还可输入 ${INPUT_LIMITS.storyDialogue} 字`)).toBeInTheDocument();
    });
    it('expands when clicking the expand button', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
    });

    it('shows quick action buttons when expanded', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByText('重新生成')).toBeInTheDocument();
        expect(screen.getByText('人生总结')).toBeInTheDocument();
      });
    });

    it('collapses when clicking close button', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const buttons = screen.getAllByRole('button');
      const closeButton = buttons.find(btn => btn.querySelector('svg.lucide-x'));
      if (closeButton) {
        await user.click(closeButton);
      }

      await waitFor(() => {
        expect(screen.queryByPlaceholderText(/向剧情助手提问/i)).not.toBeInTheDocument();
      });
    });

    it('uses a bounded expanded panel so it does not cover the custom choice area', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));

      const panel = await screen.findByTestId('chat-bar-panel');
      expect(panel).toHaveClass('right-4');
      expect(panel).toHaveClass('max-w-md');
      expect(panel).not.toHaveClass('left-0');
    });
  });

  describe('Quick action buttons', () => {
    it('uses the generated rewrite-instruction limit and shows remaining characters', async () => {
      const user = userEvent.setup();
      render(<ChatBar gameId={1} storyText="Test story" />);

      const rewriteButton = screen
        .getAllByTestId('rewrite-button')
        .find((button) => !button.hasAttribute('disabled'));
      expect(rewriteButton).toBeDefined();
      await user.click(rewriteButton!);

      const instruction = await screen.findByPlaceholderText(/描述你想要的修改/);
      expect(instruction).not.toHaveAttribute('maxlength');
      expect(
        within(screen.getByTestId('inline-rewrite-sheet')).getByText(
          `还可输入 ${INPUT_LIMITS.rewriteInstruction} 字`,
        ),
      ).toBeInTheDocument();
    });
    beforeEach(async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByText('重新生成')).toBeInTheDocument();
      });
    });

    it('calls onRegenerate when clicking regenerate button', async () => {
      const user = userEvent.setup();
      await user.click(screen.getByText('重新生成'));
      expect(mockOnRegenerate).toHaveBeenCalled();
    });

    it('calls API when clicking summary button', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Test summary content',
        start_week: 1,
        end_week: 10,
      }));

      const user = userEvent.setup();
      await user.click(screen.getByText('人生总结'));
      await waitFor(() => {
        const calls = (global.fetch as jest.Mock).mock.calls;
        const summaryCall = calls.find((c: unknown[]) => (c[0] as string).includes('/summary'));
        expect(summaryCall).toBeDefined();
        expect(summaryCall[0]).toBe('/api/games/1/summary');
        expect(JSON.parse(summaryCall[1].body)).toEqual({ weeks: 52 });
      });
    });
  });

  describe('Chat functionality', () => {
    it('allows typing a message', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Hello AI');
      expect(input).toHaveValue('Hello AI');
    });

    it('sends message when clicking send button', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: 'Test AI response' }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Hello AI');
      const buttons = screen.getAllByRole('button');
      const sendButton = buttons[buttons.length - 1];
      await user.click(sendButton);
      await waitFor(() => {
        const calls = (global.fetch as jest.Mock).mock.calls;
        const chatCall = calls.find((c: unknown[]) => (c[0] as string).includes('/chat'));
        expect(chatCall).toBeDefined();
        expect(chatCall[0]).toBe('/api/games/1/chat');
        expect(JSON.parse(chatCall[1].body)).toEqual({ message: 'Hello AI' });
      });
    });

    it('sends message on Enter key', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: 'Test AI response' }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Hello AI');
      fireEvent.keyDown(input, { key: 'Enter' });
      await waitFor(() => {
        const calls = (global.fetch as jest.Mock).mock.calls;
        const chatCall = calls.find((c: unknown[]) => (c[0] as string).includes('/chat'));
        expect(chatCall).toBeDefined();
      });
    });

    it('displays user message in chat history', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: 'Test AI response' }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Test message');
      fireEvent.keyDown(input, { key: 'Enter' });
      await waitFor(() => {
        expect(screen.getByText('Test message')).toBeInTheDocument();
      });
    });

    it('displays AI response in chat history', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: 'Test AI response' }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Test');
      fireEvent.keyDown(input, { key: 'Enter' });
      await waitFor(() => {
        expect(screen.getByText('Test AI response')).toBeInTheDocument();
      });
    });

    it('clears input after sending message', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: 'Test AI response' }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Test');
      fireEvent.keyDown(input, { key: 'Enter' });
      await waitFor(() => {
        expect(input).toHaveValue('');
      });
    });
  });

  describe('Loading states', () => {
    it('renders regenerate button in enabled state', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByText('重新生成')).toBeInTheDocument();
      });
      const regenButton = screen.getByText('重新生成').closest('button');
      expect(regenButton).not.toBeDisabled();
    });
  });

  describe('Clear chat history', () => {
    it('shows clear button when there are messages', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ reply: 'Test AI response' }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Test');
      fireEvent.keyDown(input, { key: 'Enter' });
      await waitFor(() => {
        expect(screen.getByText('Test')).toBeInTheDocument();
      });
      const trashButton = screen.getByTitle('清空对话');
      expect(trashButton).toBeInTheDocument();
    });
  });

  describe('Summary functionality', () => {
    it('displays summary in dedicated panel when clicking expanded summary button', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Test summary content',
        start_week: 1,
        end_week: 10,
      }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByText('人生总结')).toBeInTheDocument();
      });
      await user.click(screen.getByText('人生总结'));
      await waitFor(() => {
        expect(screen.getByText(/Test summary content/)).toBeInTheDocument();
      });
      expect(screen.getByTestId('life-summary-panel')).toBeInTheDocument();
      expect(screen.getAllByText(/人生总结/).length).toBeGreaterThan(0);
      expect(screen.queryByText('请总结我的人生故事')).not.toBeInTheDocument();
    });

    it('presents collapsed summary as a dedicated action instead of opening story assistant', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Dedicated summary content',
        start_week: 1,
        end_week: 4,
      }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));

      expect(await screen.findByTestId('life-summary-panel')).toBeInTheDocument();
      expect(screen.queryByTestId('chat-bar-panel')).not.toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/向剧情助手提问/i)).not.toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByText(/Dedicated summary content/)).toBeInTheDocument();
      });
      expect(screen.getAllByText(/人生总结/).length).toBeGreaterThan(0);
      expect(screen.queryByText('请总结我的人生故事')).not.toBeInTheDocument();
    });

    it('renders a single-week summary title as 第N周', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Single week summary',
        start_week: 1,
        end_week: 1,
      }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));

      expect(await screen.findByText('第1周')).toBeInTheDocument();
    });

    it('normalizes invalid end week to start week before rendering', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Recovered weekly summary',
        start_week: 3,
        end_week: 0,
      }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));

      expect(await screen.findByText('第3周')).toBeInTheDocument();
    });

    it('normalizes end week smaller than start week to start week', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Range-corrected summary',
        start_week: 3,
        end_week: 2,
      }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));

      expect(await screen.findByText('第3周')).toBeInTheDocument();
    });

    it('normalizes invalid start week to 1 and keeps label readable', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: 'Fallback summary',
        start_week: 0,
        end_week: 0,
      }));

      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByRole('button', { name: '人生总结' }));

      expect(await screen.findByText('第1周')).toBeInTheDocument();
    });
  });

  describe('External tool commands', () => {
    it('stays mounted without rendering the legacy floating launcher', () => {
      const { rerender } = render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          showLauncher={false}
        />
      );

      expect(screen.queryByTestId('chat-bar-launcher')).not.toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          showLauncher={false}
          command={{ id: 1, action: 'chat' }}
        />
      );

      expect(screen.getByTestId('chat-bar-panel')).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
    });

    it('renders the unified assistant as one story101 overlay without duplicate story tools', () => {
      render(
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          showLauncher={false}
          command={{ id: 1, action: 'chat' }}
        />
      );

      const panel = screen.getByTestId('chat-bar-panel');
      expect(panel).toHaveAttribute('data-presentation', 'unified');
      expect(panel).toHaveAttribute('data-variant', 'overlay');
      expect(panel).not.toHaveClass('bg-card/95');
      expect(panel).not.toHaveClass('backdrop-blur-sm');
      expect(panel).not.toHaveClass('rounded-lg');
      expect(within(panel).queryByRole('button', { name: '保存' })).not.toBeInTheDocument();
      expect(within(panel).queryByRole('button', { name: '改写' })).not.toBeInTheDocument();
      expect(within(panel).queryByRole('button', { name: '重新生成' })).not.toBeInTheDocument();
      expect(within(panel).queryByRole('button', { name: '人生总结' })).not.toBeInTheDocument();
      expect(within(panel).getByRole('textbox', { name: '剧情助手问题' })).toHaveAttribute(
        'data-control-size',
        'touch',
      );
      expect(within(panel).getByRole('button', { name: '关闭剧情助手' })).toHaveAttribute(
        'data-size',
        'icon-touch',
      );
    });

    it('uses a labelled touch rewrite form inside the story101 overlay', () => {
      render(
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          showLauncher={false}
          command={{ id: 1, action: 'rewrite' }}
        />
      );

      const sheet = screen.getByTestId('inline-rewrite-sheet');
      expect(sheet).toHaveClass('z-[61]');
      expect(sheet).not.toHaveClass('bg-card');
      const instruction = within(sheet).getByRole('textbox', { name: '改写要求' });
      expect(instruction).toHaveAttribute('data-control-size', 'touch');
      expect(instruction).toHaveAttribute('aria-describedby');
      expect(within(sheet).getByRole('button', { name: '改写故事' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it('keeps rewrite progress inside the open sheet instead of stacking a fixed notice over it', async () => {
      const rewriteStream = createControlledSSEStream();
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        body: rewriteStream.stream,
      });
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          storyText="原始故事。"
          showLauncher={false}
          command={{ id: 1, action: 'rewrite' }}
        />
      );

      await user.type(screen.getByPlaceholderText(/描述你想要的修改/), '增加一段对话');
      await user.click(screen.getByRole('button', { name: '改写故事' }));

      expect(screen.getByTestId('rewrite-progress-message')).toHaveTextContent(
        '正在准备改写...',
      );
      expect(
        screen.getByTestId('inline-rewrite-sheet').querySelector('.play-feedback'),
      ).toBeNull();
      expect(document.querySelector('.play-feedback')).toBeNull();
    });

    it('keeps an in-flight unified rewrite in its sheet and reports stream failure inline', async () => {
      const rewriteStream = createControlledSSEStream();
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        body: rewriteStream.stream,
      });
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          storyText="原始故事。"
          showLauncher={false}
          command={{ id: 1, action: 'rewrite' }}
        />
      );

      await user.type(screen.getByPlaceholderText(/描述你想要的修改/), '增加一段对话');
      await user.click(screen.getByRole('button', { name: '改写故事' }));
      const close = screen.getByRole('button', { name: '关闭故事调整' });
      expect(close).toBeDisabled();
      await user.click(close);

      expect(screen.getByTestId('inline-rewrite-sheet')).toBeInTheDocument();
      expect(document.querySelector('.play-feedback')).toBeNull();

      act(() => rewriteStream.error(new Error('改写流失败')));

      expect(await screen.findByRole('alert')).toHaveTextContent('改写流失败');
      expect(document.querySelector('.play-feedback')).toBeNull();
    });

    it('preserves an in-flight unified rewrite when a parent close command arrives', async () => {
      const rewriteStream = createControlledSSEStream();
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        body: rewriteStream.stream,
      });
      const user = userEvent.setup();
      const rendered = render(
        <ChatBar
          gameId={1}
          storyText="原始故事。"
          showLauncher={false}
          command={{ id: 1, action: 'rewrite' }}
        />
      );

      await user.type(screen.getByPlaceholderText(/描述你想要的修改/), '增加一段对话');
      await user.click(screen.getByRole('button', { name: '改写故事' }));
      rendered.rerender(
        <ChatBar
          gameId={1}
          storyText="原始故事。"
          showLauncher={false}
          command={{ id: 2, action: 'close' }}
        />
      );

      expect(screen.getByTestId('inline-rewrite-sheet')).toBeInTheDocument();
      expect(screen.getByTestId('rewrite-progress-message')).toHaveTextContent(
        '正在准备改写...',
      );
      expect(document.querySelector('.play-feedback')).toBeNull();
    });

    it('claims the unified live-region owner before summary progress mounts', async () => {
      (global.fetch as jest.Mock).mockImplementation(
        () => new Promise(() => undefined),
      );
      const openSnapshots: Array<'before' | 'after'> = [];
      const onSurfaceOpenChange = jest.fn((open: boolean) => {
        if (open) {
          openSnapshots.push(
            screen.queryByText('正在生成总结...') ? 'after' : 'before',
          );
        }
      });
      const rendered = render(
        <ChatBar
          gameId={1}
          storyText="当前故事。"
          showLauncher={false}
          onSurfaceOpenChange={onSurfaceOpenChange}
        />,
      );

      rendered.rerender(
        <ChatBar
          gameId={1}
          storyText="当前故事。"
          showLauncher={false}
          command={{ id: 1, action: 'summary' }}
          onSurfaceOpenChange={onSurfaceOpenChange}
        />,
      );

      expect(await screen.findByText('正在生成总结...')).toBeInTheDocument();
      expect(openSnapshots).toEqual(['before']);
    });

    it('announces unified rewrite success inside the sheet before it closes', async () => {
      const rewriteStream = createControlledSSEStream();
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        body: rewriteStream.stream,
      });
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          storyText="原始故事。"
          showLauncher={false}
          command={{ id: 1, action: 'rewrite' }}
        />
      );

      await user.type(screen.getByPlaceholderText(/描述你想要的修改/), '增加一段对话');
      await user.click(screen.getByRole('button', { name: '改写故事' }));
      const timeoutSpy = jest.spyOn(global, 'setTimeout');
      await act(async () => {
        rewriteStream.enqueue(
          'data: {"type":"complete","data":{"new_story":"改写后的故事。"}}\n\n'
        );
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByRole('status')).toHaveTextContent('故事已改写');
      expect(screen.getByTestId('inline-rewrite-sheet')).toBeInTheDocument();
      expect(document.querySelector('.play-feedback')).toBeNull();
      expect(timeoutSpy.mock.calls.map((call) => call[1])).not.toContain(500);
      timeoutSpy.mockRestore();
    });

    it('does not open or submit rewrite when the real story exceeds the generated limit', () => {
      const overLimitStory = '字'.repeat(INPUT_LIMITS.fullStory + 1);
      const { rerender } = render(
        <ChatBar
          gameId={1}
          storyText={overLimitStory}
          showLauncher={false}
        />,
      );

      rerender(
        <ChatBar
          gameId={1}
          storyText={overLimitStory}
          showLauncher={false}
          command={{ id: 1, action: 'rewrite' }}
        />,
      );

      expect(screen.queryByTestId('inline-rewrite-sheet')).not.toBeInTheDocument();
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('closes every assistant surface from a parent coordination command', async () => {
      const { rerender } = render(
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          showLauncher={false}
          command={{ id: 1, action: 'chat' }}
        />,
      );
      expect(screen.getByTestId('chat-bar-panel')).toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          showLauncher={false}
          command={{ id: 2, action: 'close' }}
        />,
      );

      await waitFor(() => {
        expect(screen.queryByTestId('chat-bar-panel')).not.toBeInTheDocument();
        expect(screen.queryByTestId('inline-rewrite-sheet')).not.toBeInTheDocument();
        expect(screen.queryByTestId('life-summary-panel')).not.toBeInTheDocument();
      });
    });

    it('renders unified chat messages as flat divided rows, not nested colored cards', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        jsonResponse({ reply: '沿着档案编号继续查找。' }),
      );
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          showLauncher={false}
          command={{ id: 1, action: 'chat' }}
        />,
      );

      const input = screen.getByRole('textbox', { name: '剧情助手问题' });
      await user.type(input, '下一步应该做什么？');
      await user.click(screen.getByRole('button', { name: '发送消息' }));

      const userMessage = await screen.findByText('下一步应该做什么？');
      const assistantMessage = await screen.findByText('沿着档案编号继续查找。');
      for (const message of [userMessage, assistantMessage].map((node) =>
        node.closest('[data-slot="chat-message"]'),
      )) {
        expect(message).toHaveAttribute('data-slot', 'chat-message');
        expect(message).toHaveClass('rounded-none', 'bg-transparent');
        expect(message).not.toHaveClass('rounded-lg', 'bg-primary/20', 'bg-secondary');
      }
    });

    it('returns focus to the prior tools trigger after the unified chat closes', async () => {
      const user = userEvent.setup();
      const renderTree = (command: { id: number; action: 'chat' } | null) => (
        <>
          <button type="button">工具入口</button>
          <ChatBar
            gameId={1}
            storyText="保留在常驻助手里的故事"
            showLauncher={false}
            command={command}
          />
        </>
      );
      const { rerender } = render(renderTree(null));
      const trigger = screen.getByRole('button', { name: '工具入口' });
      trigger.focus();

      rerender(renderTree({ id: 1, action: 'chat' }));
      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: '剧情助手问题' })).toHaveFocus();
      });
      await user.click(screen.getByRole('button', { name: '关闭剧情助手' }));
      await waitFor(() => expect(trigger).toHaveFocus());
    });

    it('returns focus to the prior tools trigger when a parent asynchronously closes the focused assistant', async () => {
      const renderTree = (command: { id: number; action: 'chat' | 'close' } | null) => (
        <>
          <button type="button">工具入口</button>
          <ChatBar
            gameId={1}
            storyText="保留在常驻助手里的故事"
            showLauncher={false}
            command={command}
          />
        </>
      );
      const { rerender } = render(renderTree(null));
      const trigger = screen.getByRole('button', { name: '工具入口' });
      trigger.focus();

      rerender(renderTree({ id: 1, action: 'chat' }));
      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: '剧情助手问题' })).toHaveFocus();
      });

      rerender(renderTree({ id: 2, action: 'close' }));
      await waitFor(() => expect(trigger).toHaveFocus());
    });

    it('moves focus into an externally opened summary and returns it on close', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        jsonResponse({ summary_text: '这一阶段的回望', start_week: 1, end_week: 1 }),
      );
      const renderTree = (command: { id: number; action: 'summary' } | null) => (
        <>
          <button type="button">工具入口</button>
          <ChatBar
            gameId={1}
            storyText="保留在常驻助手里的故事"
            showLauncher={false}
            command={command}
          />
        </>
      );
      const { rerender } = render(renderTree(null));
      const trigger = screen.getByRole('button', { name: '工具入口' });
      trigger.focus();

      rerender(renderTree({ id: 1, action: 'summary' }));
      const close = await screen.findByRole('button', { name: '关闭人生总结' });
      await waitFor(() => expect(close).toHaveFocus());

      await userEvent.click(close);
      await waitFor(() => expect(trigger).toHaveFocus());
    });

    it('reopens the same in-flight summary surface without duplicating its request', async () => {
      const pendingSummary = new Promise<Response>(() => undefined);
      (global.fetch as jest.Mock).mockReturnValue(pendingSummary);
      const renderTree = (command: { id: number; action: 'summary' | 'close' } | null) => (
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          showLauncher={false}
          command={command}
        />
      );
      const { rerender } = render(renderTree(null));

      rerender(renderTree({ id: 1, action: 'summary' }));
      expect(await screen.findByText('正在生成总结...')).toBeInTheDocument();

      rerender(renderTree({ id: 2, action: 'close' }));
      expect(screen.queryByTestId('life-summary-panel')).not.toBeInTheDocument();

      rerender(renderTree({ id: 3, action: 'summary' }));
      expect(await screen.findByText('正在生成总结...')).toBeInTheDocument();
      expect(
        (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
          String(url).includes('/api/games/1/summary'),
        ),
      ).toHaveLength(1);
    });

    it('opens rewrite and summary surfaces from distinct commands without a launcher click', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary_text: '工具面板触发的人生总结',
        start_week: 1,
        end_week: 2,
      }));

      const { rerender } = render(
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          showLauncher={false}
          command={{ id: 1, action: 'rewrite' }}
        />
      );

      expect(screen.getByTestId('inline-rewrite-sheet')).toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          storyText="保留在常驻助手里的故事"
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          showLauncher={false}
          command={{ id: 2, action: 'summary' }}
        />
      );

      expect(await screen.findByTestId('life-summary-panel')).toBeInTheDocument();
      expect(await screen.findByText('工具面板触发的人生总结')).toBeInTheDocument();
      const summaryPanel = screen.getByTestId('life-summary-panel');
      expect(summaryPanel).toHaveAttribute('data-variant', 'overlay');
      expect(summaryPanel).toHaveClass('play-chat-surface');
      expect(summaryPanel).not.toHaveClass('bg-card/95');
      expect(summaryPanel).not.toHaveClass('backdrop-blur-sm');
      expect(summaryPanel).not.toHaveClass('rounded-lg');
      expect(within(summaryPanel).getByRole('button', { name: '关闭人生总结' })).toHaveAttribute(
        'data-size',
        'icon-touch',
      );
    });

    it('ignores external commands while busy and accepts a fresh command after recovery', () => {
      const { rerender } = render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          isStoryBusy
          showLauncher={false}
          command={{ id: 1, action: 'chat' }}
        />
      );

      expect(screen.queryByTestId('chat-bar-panel')).not.toBeInTheDocument();

      rerender(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onRegenerate={mockOnRegenerate}
          showLauncher={false}
          command={{ id: 2, action: 'chat' }}
        />
      );

      expect(screen.getByTestId('chat-bar-panel')).toBeInTheDocument();
    });
  });
});
