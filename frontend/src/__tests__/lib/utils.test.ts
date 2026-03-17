/**
 * lib/utils.ts Tests
 * Tests for utility functions
 */
import { cn, copyToClipboard } from '@/lib/utils';

// Use real clsx and tailwind-merge (no mocks needed)

describe('utils', () => {
  describe('cn', () => {
    it('merges class names', () => {
      const result = cn('foo', 'bar');
      expect(result).toBe('foo bar');
    });

    it('handles conditional classes', () => {
      const result = cn('base', false && 'hidden', 'visible');
      expect(result).toBe('base visible');
    });

    it('handles undefined and null', () => {
      const result = cn('base', undefined, null, 'end');
      expect(result).toBe('base end');
    });

    it('handles empty strings', () => {
      const result = cn('base', '', 'end');
      // Empty strings are filtered out by twMerge
      expect(result).toBe('base end');
    });

    it('handles arrays', () => {
      const result = cn(['foo', 'bar'], 'baz');
      expect(result).toBe('foo bar baz');
    });

    it('handles objects', () => {
      const result = cn({ active: true, disabled: false });
      expect(result).toBe('active');
    });
  });

  describe('copyToClipboard', () => {
    // Mock clipboard API
    const originalClipboard = navigator.clipboard;
    const originalExecCommand = document.execCommand;

    beforeEach(() => {
      // Reset mocks
      jest.clearAllMocks();
    });

    afterEach(() => {
      // Restore originals
      Object.defineProperty(navigator, 'clipboard', {
        value: originalClipboard,
        writable: true,
        configurable: true,
      });
      document.execCommand = originalExecCommand;
    });

    it('uses modern clipboard API when available', async () => {
      const mockWriteText = jest.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: mockWriteText },
        writable: true,
        configurable: true,
      });

      const result = await copyToClipboard('test text');
      expect(mockWriteText).toHaveBeenCalledWith('test text');
      expect(result).toBe(true);
    });

    it('returns false when clipboard API fails and fallback fails', async () => {
      const mockWriteText = jest.fn().mockRejectedValue(new Error('Permission denied'));
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: mockWriteText },
        writable: true,
        configurable: true,
      });

      // Mock fallback failure
      document.execCommand = jest.fn().mockReturnValue(false);

      const result = await copyToClipboard('test text');
      expect(result).toBe(false);
    });

    it('uses fallback when clipboard API is not available', async () => {
      Object.defineProperty(navigator, 'clipboard', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      // Mock successful fallback
      document.execCommand = jest.fn().mockReturnValue(true);
      document.body.appendChild = jest.fn();
      document.body.removeChild = jest.fn();

      const result = await copyToClipboard('test text');
      expect(result).toBe(true);
    });

    it('handles clipboard API not existing', async () => {
      Object.defineProperty(navigator, 'clipboard', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      document.execCommand = jest.fn().mockReturnValue(true);
      document.body.appendChild = jest.fn();
      document.body.removeChild = jest.fn();

      const result = await copyToClipboard('fallback test');
      expect(document.execCommand).toHaveBeenCalledWith('copy');
      expect(result).toBe(true);
    });

    it('creates and removes textarea for fallback', async () => {
      Object.defineProperty(navigator, 'clipboard', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      const mockTextArea = {
        value: '',
        style: { position: '', left: '', top: '' },
        setAttribute: jest.fn(),
        setSelectionRange: jest.fn(),
      } as unknown as HTMLTextAreaElement;

      const originalCreateElement = document.createElement;
      document.createElement = jest.fn().mockReturnValue(mockTextArea);
      document.execCommand = jest.fn().mockReturnValue(true);
      document.body.appendChild = jest.fn();
      document.body.removeChild = jest.fn();

      const createRangeSpy = jest.spyOn(document, 'createRange').mockReturnValue({
        selectNodeContents: jest.fn(),
      } as unknown as Range);

      const getSelectionSpy = jest.spyOn(window, 'getSelection').mockReturnValue({
        removeAllRanges: jest.fn(),
        addRange: jest.fn(),
      } as unknown as Selection);

      await copyToClipboard('test fallback');

      expect(document.createElement).toHaveBeenCalledWith('textarea');
      expect(mockTextArea.value).toBe('test fallback');
      expect(document.body.appendChild).toHaveBeenCalled();
      expect(document.body.removeChild).toHaveBeenCalled();

      createRangeSpy.mockRestore();
      getSelectionSpy.mockRestore();
      document.createElement = originalCreateElement;
    });

    it('returns false when fallback throws an error', async () => {
      Object.defineProperty(navigator, 'clipboard', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      document.createElement = jest.fn().mockImplementation(() => {
        throw new Error('Failed to create element');
      });

      const result = await copyToClipboard('test text');
      expect(result).toBe(false);
    });
  });
});
