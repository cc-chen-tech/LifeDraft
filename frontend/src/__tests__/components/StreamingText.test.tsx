/**
 * StreamingText Component Tests
 * Tests for the streaming text display component
 */
import { render, screen, waitFor, act } from '@testing-library/react';
import { StreamingText, formatNarrativeMarkdownForDisplay } from '@/components/game/StreamingText';

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

    it('continues typing when isStreaming becomes false (no flash)', async () => {
      const { rerender, container } = render(
        <StreamingText
          text="Hello World"
          isStreaming={true}
          charsPerFrame={5}
          frameInterval={50}
        />
      );

      // Let it type a bit: "Hello" (5 chars)
      act(() => {
        jest.advanceTimersByTime(50);
      });
      expect(container.textContent).toContain('Hello');

      // Switch to non-streaming — should NOT instantly show all text
      rerender(
        <StreamingText
          text="Hello World"
          isStreaming={false}
          charsPerFrame={5}
          frameInterval={50}
        />
      );

      // Immediately after rerender, should still only show "Hello"
      expect(container.textContent).toContain('Hello');

      // Advance timers to finish typing
      act(() => {
        jest.advanceTimersByTime(100);
      });

      await waitFor(() => {
        expect(container.textContent).toContain('Hello World');
      });
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

    it('preserves a comma-rich Chinese narrative as one authored paragraph', async () => {
      const text = '林见微推开档案室的门，冷白灯光落在一排排旧案卷上。她发现赵家船行的账册缺了三页，页角却留下同一枚铜钥匙的压痕。窗外的无人机巡逻声越来越近，陆子衿压低声音提醒她马上离开。林见微没有退后，而是把账册拍照上传到加密云端，准备追查科技公司背后的黑幕。';

      const formatted = formatNarrativeMarkdownForDisplay(text);
      expect(formatted).toBe(text);

      const { container } = render(<StreamingText text={text} isStreaming={false} narrative />);

      await waitFor(() => {
        expect(container.textContent).toContain('林见微推开档案室的门');
      });
    });

    it('preserves a punctuation-less single-line narrative as one authored paragraph', async () => {
      const longText =
        '林见微推开档案室的门冷白灯光落在一排排旧案卷上她发现赵家船行的账册缺了三页页角却留下同一枚铜钥匙的压痕窗外的无人机巡逻声越来越近陆子衿压低声音提醒她马上离开林见微没有退后而是把账册拍照上传到加密云端准备追查科技公司背后的黑幕';
      const formatted = formatNarrativeMarkdownForDisplay(longText);
      expect(formatted).toBe(longText);

      const { container } = render(<StreamingText text={longText} isStreaming={false} narrative />);
      expect(container.textContent).toContain(longText);
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

    it('allows calm narrative pages to suppress the typewriter cursor', () => {
      const { container } = render(
        <StreamingText text="Test" isStreaming showCursor={false} />
      );

      expect(container.querySelector('.typewriter-cursor')).not.toBeInTheDocument();
    });
  });
});
