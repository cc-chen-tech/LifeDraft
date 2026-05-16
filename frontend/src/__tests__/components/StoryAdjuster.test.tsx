/**
 * StoryAdjuster Component Tests
 * Tests all interactive elements of the story adjuster component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StoryAdjuster } from '@/components/game/StoryAdjuster';
import { useGameStore } from '@/stores/useGameStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

// -- SSE scenario helpers --
function makeRewriteSuccessResponse() {
  return createSSEMockResponse([
    'event: story\ndata: Rewritten \n\n',
    'event: story\ndata: story\n\n',
    'event: complete\ndata: {"new_story":"Rewritten story"}\n\n',
  ]);
}

function errorFetchResponse(status: number): Response {
  return {
    ok: false,
    status,
    statusText: status === 404 ? 'Not Found' : 'Server Error',
    headers: new Headers({ 'content-type': 'application/json' }),
    json: () => Promise.resolve({ detail: 'error' }),
    text: () => Promise.resolve('error'),
    body: null,
  } as Response;
}

const STORE_METHODS = ['syncState'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useGameStore.setState({
    roundInfo: { current_round: 1 },
    storyText: 'Test story',
  });
}

describe('StoryAdjuster', () => {
  let storeSpy: StoreSpy;
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
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
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
      (global.fetch as jest.Mock).mockResolvedValue(makeRewriteSuccessResponse());
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Make it more dramatic');
      await user.click(screen.getByText('改写故事'));
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/rewrite-stream'),
          expect.anything()
        );
      });
    });

    it('calls onRewriteComplete with new story', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(makeRewriteSuccessResponse());
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
      (global.fetch as jest.Mock).mockResolvedValue(makeRewriteSuccessResponse());
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
      (global.fetch as jest.Mock).mockReturnValue(new Promise(() => {}));
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      await user.click(screen.getByText('改写故事'));
      await waitFor(() => {
        expect(textarea).toBeDisabled();
      });
    });

    it('disables buttons while processing', async () => {
      (global.fetch as jest.Mock).mockReturnValue(new Promise(() => {}));
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
      (global.fetch as jest.Mock).mockReturnValue(new Promise(() => {}));
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      await user.click(screen.getByText('改写故事'));
      await waitFor(() => {
        expect(screen.getByText('正在改写中...')).toBeInTheDocument();
      });
    });

    it('shows success toast after successful rewrite', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
        'event: complete\ndata: {"new_story":"Rewritten story"}\n\n',
      ]));
      const user = userEvent.setup();
      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test');
      await user.click(screen.getByText('改写故事'));
      const toast = await screen.findByText('故事已改写', {}, { timeout: 5000 });
      expect(toast).toBeInTheDocument();
    });
  });

  describe('Session recovery', () => {
    it('restores session and retries on 404 error', async () => {
      const user = userEvent.setup();
      storeSpy.spies.syncState.mockResolvedValue(undefined);

      let callCount = 0;
      (global.fetch as jest.Mock).mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve(errorFetchResponse(404));
        }
        return Promise.resolve(createSSEMockResponse([
          'event: complete\ndata: {"new_story":"Rewritten after recovery"}\n\n',
        ]));
      });

      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      await user.click(screen.getByText('改写故事'));

      await waitFor(() => {
        expect(storeSpy.spies.syncState).toHaveBeenCalled();
        const rewriteCalls = (global.fetch as jest.Mock).mock.calls.filter(
          (call: unknown[]) => typeof call[0] === 'string' && (call[0] as string).includes('/rewrite-stream')
        );
        expect(rewriteCalls.length).toBe(2);
      });
    });

    it('shows error toast if session restore fails', async () => {
      const user = userEvent.setup();
      storeSpy.spies.syncState.mockRejectedValue(new Error('Restore failed'));

      (global.fetch as jest.Mock).mockResolvedValue(errorFetchResponse(404));

      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      await user.click(screen.getByText('改写故事'));

      await waitFor(() => {
        expect(screen.getByText('改写失败，请重试')).toBeInTheDocument();
      });
    });

    it('shows loading toast during session restore', async () => {
      const user = userEvent.setup();
      storeSpy.spies.syncState.mockImplementation(() => new Promise(() => {}));

      (global.fetch as jest.Mock).mockResolvedValue(errorFetchResponse(404));

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
      (global.fetch as jest.Mock).mockResolvedValue(errorFetchResponse(500));

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
      storeSpy.spies.syncState.mockResolvedValue(undefined);

      (global.fetch as jest.Mock).mockResolvedValue(errorFetchResponse(404));

      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      await user.click(screen.getByText('改写故事'));

      await waitFor(() => {
        const rewriteCalls = (global.fetch as jest.Mock).mock.calls.filter(
          (call: unknown[]) => typeof call[0] === 'string' && (call[0] as string).includes('/rewrite-stream')
        );
        expect(rewriteCalls.length).toBe(2);
        expect(screen.getByText('改写失败，请重试')).toBeInTheDocument();
      });
    });

    it('closes sheet when SSE returns empty result', async () => {
      const user = userEvent.setup();
      (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
        'data: [DONE]\n\n',
      ]));

      render(<StoryAdjuster {...defaultProps} />);
      const textarea = screen.getByPlaceholderText(/描述你想要的修改/i);
      await user.type(textarea, 'Test instruction');
      await user.click(screen.getByText('改写故事'));

      await waitFor(() => {
        expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      }, { timeout: 3000 });
    });
  });
});
