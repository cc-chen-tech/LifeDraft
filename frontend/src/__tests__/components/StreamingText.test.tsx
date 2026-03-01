/**
 * StreamingText Component Tests
 * Tests for the streaming text display component
 */
import { render, screen, waitFor, act } from '@testing-library/react';
import { StreamingText } from '@/components/game/StreamingText';

// Mock scrollTo
Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
  value: jest.fn(),
  writable: true,
});

Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
  get() { return 100; },
  configurable: true,
});

Object.defineProperty(HTMLElement.prototype, 'scrollTop', {
  get() { return 0; },
  configurable: true,
});

Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
  get() { return 100; },
  configurable: true,
});

describe('StreamingText', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('rendering', () => {
    it('renders text when not streaming', () => {
      render(
        <StreamingText text="Hello World" isStreaming={false} />
      );

      expect(screen.getByText('Hello World')).toBeInTheDocument();
    });

    it('returns null when no text and not streaming', () => {
      const { container } = render(
        <StreamingText text="" isStreaming={false} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('shows cursor when streaming with empty text', () => {
      const { container } = render(
        <StreamingText text="" isStreaming={true} />
      );

      // Should show cursor element
      const cursor = container.querySelector('.typewriter-cursor');
      expect(cursor).toBeInTheDocument();
    });
  });

  describe('streaming behavior', () => {
    it('displays text immediately when not streaming', () => {
      const { rerender } = render(
        <StreamingText text="" isStreaming={false} />
      );

      rerender(
        <StreamingText text="Full text" isStreaming={false} />
      );

      expect(screen.getByText('Full text')).toBeInTheDocument();
    });

    it('gradually displays text when streaming', async () => {
      const { container } = render(
        <StreamingText
          text="Hello World"
          isStreaming={true}
          charsPerFrame={5}
          frameInterval={50}
        />
      );

      // Initially should show cursor
      expect(container.querySelector('.typewriter-cursor')).toBeInTheDocument();

      // Advance timers
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Should have displayed some text
      await waitFor(() => {
        expect(container.textContent).toContain('Hello');
      });
    });

    it('stops streaming when isStreaming becomes false', async () => {
      const { rerender, container } = render(
        <StreamingText
          text="Hello World"
          isStreaming={true}
          charsPerFrame={5}
          frameInterval={50}
        />
      );

      // Switch to non-streaming
      rerender(
        <StreamingText
          text="Hello World"
          isStreaming={false}
          charsPerFrame={5}
          frameInterval={50}
        />
      );

      // Should display full text immediately
      expect(screen.getByText('Hello World')).toBeInTheDocument();
    });
  });

  describe('paragraph handling', () => {
    it('splits text into paragraphs', () => {
      // Use template literal to ensure proper newline handling
      const text = `First paragraph

Second paragraph`;
      
      render(
        <StreamingText
          text={text}
          isStreaming={false}
        />
      );

      // Component splits by \n\n, check the content is displayed
      const container = screen.getByText(/First paragraph/);
      expect(container).toBeInTheDocument();
    });

    it('handles single paragraph', () => {
      render(
        <StreamingText text="Single paragraph" isStreaming={false} />
      );

      expect(screen.getByText('Single paragraph')).toBeInTheDocument();
    });
  });

  describe('customization', () => {
    it('applies custom className', () => {
      const { container } = render(
        <StreamingText
          text="Test"
          isStreaming={false}
          className="custom-class"
        />
      );

      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('applies narrative class by default', () => {
      const { container } = render(
        <StreamingText text="Test" isStreaming={false} />
      );

      expect(container.firstChild).toHaveClass('prose-story');
    });

    it('disables narrative class when narrative is false', () => {
      const { container } = render(
        <StreamingText text="Test" isStreaming={false} narrative={false} />
      );

      expect(container.firstChild).not.toHaveClass('prose-story');
    });
  });
});
