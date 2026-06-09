/**
 * ChatBar Component Tests
 * Tests all interactive elements of the chat bar component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatBar } from '@/components/game/ChatBar';
import { useGameStore } from '@/stores/useGameStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

const STORE_METHODS = ['syncState'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

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
  });

  describe('Expanded state', () => {
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
  });
});
