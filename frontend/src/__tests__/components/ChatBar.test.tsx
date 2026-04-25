/**
 * ChatBar Component Tests
 * Tests all interactive elements of the chat bar component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatBar } from '@/components/game/ChatBar';

// Mock the API
jest.mock('@/lib/api', () => ({
  api: {
    story: {
      chat: jest.fn().mockResolvedValue({ reply: 'Test AI response' }),
    },
    gameplay: {
      generateSummary: jest.fn().mockResolvedValue({
        summary_text: 'Test summary content',
        start_week: 1,
        end_week: 10,
      }),
    },
  },
}));

// Mock useGameStore
jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: () => ({
      syncState: jest.fn().mockResolvedValue(undefined),
    }),
  },
}));

import { api } from '@/lib/api';

describe('ChatBar', () => {
  const mockOnSave = jest.fn();
  const mockOnAdjustStory = jest.fn();
  const mockOnRegenerate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Collapsed state', () => {
    it('renders collapsed button when not expanded', () => {
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      // Should show the expand button (MessageCircle icon)
      const expandButton = screen.getByLabelText('打开聊天');
      expect(expandButton).toBeInTheDocument();
    });

    it('does not render when gameId is null', () => {
      const { container } = render(
        <ChatBar
          gameId={null}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Expanded state', () => {
    it('expands when clicking the expand button', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      const expandButton = screen.getByLabelText('打开聊天');
      await user.click(expandButton);

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
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));

      await waitFor(() => {
        expect(screen.getByText('保存')).toBeInTheDocument();
        expect(screen.getByText('改写')).toBeInTheDocument();
        expect(screen.getByText('重新生成')).toBeInTheDocument();
        expect(screen.getByText('总结')).toBeInTheDocument();
      });
    });

    it('collapses when clicking close button', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      // Expand first
      await user.click(screen.getByLabelText('打开聊天'));
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });

      // Find and click close button (X icon)
      const buttons = screen.getAllByRole('button');
      const closeButton = buttons.find(btn => btn.querySelector('svg.lucide-x'));
      if (closeButton) {
        await user.click(closeButton);
      }
    });
  });

  describe('Quick action buttons', () => {
    beforeEach(async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );
      
      // Expand the chat bar
      await user.click(screen.getByLabelText('打开聊天'));
      await waitFor(() => {
        expect(screen.getByText('保存')).toBeInTheDocument();
      });
    });

    it('calls onSave when clicking save button', async () => {
      const user = userEvent.setup();
      await user.click(screen.getByText('保存'));
      expect(mockOnSave).toHaveBeenCalled();
    });

    it('calls onAdjustStory when clicking adjust button', async () => {
      const user = userEvent.setup();
      await user.click(screen.getByText('改写'));
      expect(mockOnAdjustStory).toHaveBeenCalled();
    });

    it('calls onRegenerate when clicking regenerate button', async () => {
      const user = userEvent.setup();
      await user.click(screen.getByText('重新生成'));
      expect(mockOnRegenerate).toHaveBeenCalled();
    });

    it('calls API when clicking summary button', async () => {
      const user = userEvent.setup();
      await user.click(screen.getByText('总结'));
      
      await waitFor(() => {
        expect(api.gameplay.generateSummary).toHaveBeenCalledWith(1, { weeks: 52 });
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
          onAdjustStory={mockOnAdjustStory}
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
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Hello AI');

      // Find send button (last button in the expanded view)
      const buttons = screen.getAllByRole('button');
      const sendButton = buttons[buttons.length - 1];
      await user.click(sendButton);

      await waitFor(() => {
        expect(api.story.chat).toHaveBeenCalledWith(1, { message: 'Hello AI' });
      });
    });

    it('sends message on Enter key', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
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
        expect(api.story.chat).toHaveBeenCalled();
      });
    });

    it('displays user message in chat history', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
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
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
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
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
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
    it('disables save button when isSaving is true', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
          isSaving={true}
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));
      
      await waitFor(() => {
        expect(screen.getByText('保存')).toBeInTheDocument();
      });

      const saveButton = screen.getByText('保存').closest('button');
      expect(saveButton).toBeDisabled();
    });
  });

  describe('Clear chat history', () => {
    it('shows clear button when there are messages', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/向剧情助手提问/i)).toBeInTheDocument();
      });

      // Send a message first
      const input = screen.getByPlaceholderText(/向剧情助手提问/i);
      await user.type(input, 'Test');
      fireEvent.keyDown(input, { key: 'Enter' });

      await waitFor(() => {
        expect(screen.getByText('Test')).toBeInTheDocument();
      });

      // Look for trash button (clear history)
      const trashButton = screen.getByTitle('清空对话');
      expect(trashButton).toBeInTheDocument();
    });
  });

  describe('Summary functionality', () => {
    it('displays summary in chat history when clicking summary button', async () => {
      const user = userEvent.setup();
      render(
        <ChatBar
          gameId={1}
          onSave={mockOnSave}
          onAdjustStory={mockOnAdjustStory}
          onRegenerate={mockOnRegenerate}
        />
      );

      await user.click(screen.getByLabelText('打开聊天'));
      
      await waitFor(() => {
        expect(screen.getByText('总结')).toBeInTheDocument();
      });

      await user.click(screen.getByText('总结'));

      // Check user request message appears
      await waitFor(() => {
        expect(screen.getByText('请总结我的人生故事')).toBeInTheDocument();
      });

      // Check summary response appears
      await waitFor(() => {
        expect(screen.getByText(/人生总结/)).toBeInTheDocument();
        expect(screen.getByText(/Test summary content/)).toBeInTheDocument();
      });
    });
  });
});
