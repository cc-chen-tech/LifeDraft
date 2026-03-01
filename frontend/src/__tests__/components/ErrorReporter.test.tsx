/**
 * components/ErrorReporter.tsx Tests
 * Tests for error reporter component
 */

import React from 'react';
import { render } from '@testing-library/react';
import ErrorReporter from '@/components/ErrorReporter';

// Mock remote-log
jest.mock('@/lib/remote-log', () => ({
  installGlobalErrorReporter: jest.fn(),
}));

describe('ErrorReporter', () => {
  it('renders null', () => {
    const { container } = render(<ErrorReporter />);
    expect(container.firstChild).toBeNull();
  });

  it('installs global error reporter on mount', () => {
    const { installGlobalErrorReporter } = require('@/lib/remote-log');
    render(<ErrorReporter />);
    expect(installGlobalErrorReporter).toHaveBeenCalled();
  });
});
