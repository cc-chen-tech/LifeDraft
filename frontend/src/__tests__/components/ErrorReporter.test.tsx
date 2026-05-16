/**
 * components/ErrorReporter.tsx Tests
 * Tests for error reporter component
 */

import React from 'react';
import { render } from '@testing-library/react';
import ErrorReporter from '@/components/ErrorReporter';

describe('ErrorReporter', () => {
  it('renders null', () => {
    const { container } = render(<ErrorReporter />);
    expect(container.firstChild).toBeNull();
  });

  it('installs global error reporter on mount', () => {
    const spy = jest.spyOn(window, 'addEventListener');
    render(<ErrorReporter />);
    expect(spy).toHaveBeenCalledWith('error', expect.any(Function));
    expect(spy).toHaveBeenCalledWith('unhandledrejection', expect.any(Function));
    spy.mockRestore();
  });
});
