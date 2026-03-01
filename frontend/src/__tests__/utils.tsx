/**
 * Test utilities and render helpers
 */
import React from 'react';
import { render, RenderOptions } from '@testing-library/react';

// Custom render with providers if needed
const customRender = (
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { ...options });

// Re-export everything from testing-library
export * from '@testing-library/react';
export { customRender as render };

// Wait helper for async operations
export const waitForMs = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Create mock router push function
export const createMockRouter = () => {
  const push = jest.fn();
  const replace = jest.fn();
  const back = jest.fn();
  
  return {
    push,
    replace,
    back,
    forward: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn().mockResolvedValue(undefined),
  };
};
