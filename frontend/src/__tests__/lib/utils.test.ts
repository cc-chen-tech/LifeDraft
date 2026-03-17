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
      // Completely remove clipboard API to force fallback
      Object.defineProperty(navigator, 'clipboard', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      // Track appendChild and removeChild calls
      const appendChildCalls: HTMLElement[] = [];
      const removeChildCalls: HTMLElement[] = [];

      const originalAppendChild = document.body.appendChild;
      const originalRemoveChild = document.body.removeChild;

      document.body.appendChild = jest.fn((node: Node) => {
        appendChildCalls.push(node as HTMLElement);
        return node;
      }) as unknown as typeof document.body.appendChild;

      document.body.removeChild = jest.fn((node: Node) => {
        removeChildCalls.push(node as HTMLElement);
        return node;
      }) as unknown as typeof document.body.removeChild;

      document.execCommand = jest.fn().mockReturnValue(true);

      await copyToClipboard('test fallback');

      // Verify textarea was created and removed
      expect(appendChildCalls.length).toBeGreaterThanOrEqual(1);
      expect(removeChildCalls.length).toBeGreaterThanOrEqual(1);

      // Restore originals
      document.body.appendChild = originalAppendChild;
      document.body.removeChild = originalRemoveChild;
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
