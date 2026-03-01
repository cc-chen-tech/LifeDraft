/**
 * StoryAdjuster Component Tests
 * Tests all interactive elements of the story adjuster component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StoryAdjuster } from '@/components/game/StoryAdjuster';

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
    return { completed: true };
  }),
  streamRegenerate: jest.fn(),
}));

// Mock useGameStore
jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: () => ({
      syncState: jest.fn().mockResolvedValue(undefined),
      roundInfo: { current_round: 1 },
      storyText: 'Test story',
    }),
  },
}));

import { streamRewrite } from '@/lib/sse';

describe('StoryAdjuster', () => {
  const mockOnOpenChange = jest.fn();
  const mockOnRewriteComplete = jest.fn();
  const mockOnRegenerateComplete = jest.fn();

  const defaultProps = {
    open: true,
    onOpenChange: mockOnOpenChange,
    gameId: 1,
    fullStory: 'This is the full story text.',
    onRewriteComplete: mockOnRewriteComplete,
    onRegenerateComplete: mockOnRegenerateComplete,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders when open is true', () => {
      render(<StoryAdjuster {...defaultProps} />);
      
      expect(screen.getByText('故事调整')).toBeInTheDocument();
      expect(screen.getByText('告诉我你希望如何修改这段故事')).toBeInTheDocument();
    });

    it('does not render content when open is false', () => {
      render(<StoryAdjuster {...defaultProps} open={false} />);
      
      expect(screen.queryByText('故事调整')).not.toBeInTheDocument();
    });

    it('renders action buttons', () => {
      render(<StoryAdjuster {...defaultProps} />);
      
      expect(screen.getByText('改写故事')).toBeInTheDocument();
      expect(screen.getByText('重新生成')).toBeInTheDocument();
    });
  });

  describe('Instruction input', () => {
    it('allows typing in instruction textarea', async () => {
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Make it more dramatic');
      
      expect(textarea).toHaveValue('Make it more dramatic');
    });
  });

  describe('Rewrite functionality', () => {
    it('calls SSE streamRewrite when clicking rewrite button', async () => {
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Make it more dramatic');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        expect(streamRewrite).toHaveBeenCalled();
      });
    });

    it('calls onRewriteComplete with new story', async () => {
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        expect(mockOnRewriteComplete).toHaveBeenCalled();
      });
    });

    it('closes sheet after successful rewrite', async () => {
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      });
    });

    it('disables rewrite button when no instruction', () => {
      render(<StoryAdjuster {...defaultProps} />);
      
      const rewriteButton = screen.getByText('改写故事').closest('button');
      expect(rewriteButton).toBeDisabled();
    });
  });

  describe('Regenerate functionality', () => {
    it('calls onRegenerateComplete when clicking regenerate button', async () => {
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      await user.click(screen.getByText('重新生成'));
      
      await waitFor(() => {
        expect(mockOnRegenerateComplete).toHaveBeenCalled();
      });
    });

    it('closes sheet after regenerating', async () => {
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      await user.click(screen.getByText('重新生成'));
      
      await waitFor(() => {
        expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      });
    });
  });

  describe('Loading states', () => {
    it('disables textarea while rewriting', async () => {
      // Make the SSE call hang
      (streamRewrite as jest.Mock).mockImplementation(() => new Promise(() => {}));
      
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      
      await user.click(screen.getByText('改写故事'));
      
      // Should be disabled during loading
      await waitFor(() => {
        expect(textarea).toBeDisabled();
      });
    });

    it('disables buttons while processing', async () => {
      // Make the SSE call hang
      (streamRewrite as jest.Mock).mockImplementation(() => new Promise(() => {}));
      
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        const regenerateButton = screen.getByText('重新生成').closest('button');
        expect(regenerateButton).toBeDisabled();
      });
    });

    it('shows loading toast when rewrite starts', async () => {
      // Make the SSE call hang to see loading state
      (streamRewrite as jest.Mock).mockImplementation(() => new Promise(() => {}));
      
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      
      await user.click(screen.getByText('改写故事'));
      
      // Should show loading toast
      await waitFor(() => {
        expect(screen.getByText('正在改写中...')).toBeInTheDocument();
      });
    });

    it('shows success toast after successful rewrite', async () => {
      // Reset the mock to ensure it returns the correct value
      (streamRewrite as jest.Mock).mockImplementation(async (_gameId, _fullStory, _instruction, _segment, _lang, callbacks) => {
        if (callbacks?.onComplete) {
          callbacks.onComplete({ new_story: 'Rewritten story' });
        }
        return { completed: true };
      });
      
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      
      await user.click(screen.getByText('改写故事'));
      
      // Wait for the success toast to appear using findByText with longer timeout
      const toast = await screen.findByText('故事已改写', {}, { timeout: 5000 });
      expect(toast).toBeInTheDocument();
    });
  });

  describe('Session recovery', () => {
    it('restores session and retries on 404 error', async () => {
      const user = userEvent.setup();
      const mockSyncState = jest.fn().mockResolvedValue(undefined);
      
      // Import the mocked useGameStore to update the mock
      const { useGameStore } = require('@/stores/useGameStore');
      useGameStore.getState = () => ({ syncState: mockSyncState, roundInfo: { current_round: 1 }, storyText: 'Test' });
      
      // First call fails with 404, second call succeeds
      (streamRewrite as jest.Mock)
        .mockRejectedValueOnce({ 
          status: 404, 
          message: 'No active game session for game_id=1. Load the game first.' 
        })
        .mockImplementation(async (_gameId, _fullStory, _instruction, _segment, _lang, callbacks) => {
          if (callbacks?.onComplete) {
            callbacks.onComplete({ new_story: 'Rewritten after recovery' });
          }
          return { completed: true };
        });
      
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        // Should have called syncState to restore session
        expect(mockSyncState).toHaveBeenCalled();
        // Should have retried the rewrite
        expect(streamRewrite).toHaveBeenCalledTimes(2);
      });
    });

    it('shows error toast if session restore fails', async () => {
      const user = userEvent.setup();
      const mockSyncState = jest.fn().mockRejectedValue(new Error('Restore failed'));
      
      const { useGameStore } = require('@/stores/useGameStore');
      useGameStore.getState = () => ({ syncState: mockSyncState, roundInfo: { current_round: 1 }, storyText: 'Test' });
      
      (streamRewrite as jest.Mock).mockRejectedValueOnce({
        status: 404,
        message: 'No active game session for game_id=1. Load the game first.',
      });
      
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        // Should show error toast
        expect(screen.getByText('改写失败，请重试')).toBeInTheDocument();
      });
    });

    it('shows loading toast during session restore', async () => {
      const user = userEvent.setup();
      // Make syncState hang to see loading toast
      const mockSyncState = jest.fn().mockImplementation(() => new Promise(() => {}));
      
      const { useGameStore } = require('@/stores/useGameStore');
      useGameStore.getState = () => ({ syncState: mockSyncState, roundInfo: { current_round: 1 }, storyText: 'Test' });
      
      (streamRewrite as jest.Mock).mockRejectedValueOnce({
        status: 404,
        message: 'No active game session for game_id=1. Load the game first.',
      });
      
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        expect(screen.getByText('恢复会话中...')).toBeInTheDocument();
      });
    });

    it('shows error toast for non-404 errors', async () => {
      const user = userEvent.setup();
      
      (streamRewrite as jest.Mock).mockRejectedValueOnce({
        status: 500,
        message: 'Internal server error',
      });
      
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        expect(screen.getByText('改写失败，请重试')).toBeInTheDocument();
      });
    });

    it('does not retry more than once', async () => {
      const user = userEvent.setup();
      const mockSyncState = jest.fn().mockResolvedValue(undefined);
      
      const { useGameStore } = require('@/stores/useGameStore');
      useGameStore.getState = () => ({ syncState: mockSyncState, roundInfo: { current_round: 1 }, storyText: 'Test' });
      
      // Both calls fail with 404
      (streamRewrite as jest.Mock)
        .mockRejectedValueOnce({
          status: 404,
          message: 'No active game session for game_id=1. Load the game first.',
        })
        .mockRejectedValueOnce({
          status: 404,
          message: 'No active game session for game_id=1. Load the game first.',
        });
      
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      
      await user.click(screen.getByText('改写故事'));
      
      await waitFor(() => {
        // Should only call twice (initial + one retry)
        expect(streamRewrite).toHaveBeenCalledTimes(2);
        // Should show error toast
        expect(screen.getByText('改写失败，请重试')).toBeInTheDocument();
      });
    });

    it('closes sheet when SSE returns empty result', async () => {
      const user = userEvent.setup();
      
      // Return empty result - mock to call onComplete with empty object
      (streamRewrite as jest.Mock).mockImplementation(async (_gameId, _fullStory, _instruction, _segment, _lang, callbacks) => {
        // Don't call onStory, just call onComplete with empty
        if (callbacks?.onComplete) {
          callbacks.onComplete({});
        }
        return { completed: true };
      });
      
      render(<StoryAdjuster {...defaultProps} />);
      
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      
      await user.click(screen.getByText('改写故事'));
      
      // The component should close the sheet even with empty result
      await waitFor(() => {
        expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      }, { timeout: 3000 });
    });
  });
});
