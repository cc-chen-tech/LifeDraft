require('@testing-library/jest-dom');

// Polyfill TextEncoder/TextDecoder for jsdom (used by real SSE parsing)
const { TextEncoder: NodeTextEncoder, TextDecoder: NodeTextDecoder } = require('util');
if (typeof global.TextEncoder === 'undefined') {
  global.TextEncoder = NodeTextEncoder;
}
if (typeof global.TextDecoder === 'undefined') {
  global.TextDecoder = NodeTextDecoder;
}

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn().mockResolvedValue(undefined),
    readText: jest.fn().mockResolvedValue(''),
  },
});

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  observe() { return null; }
  unobserve() { return null; }
  disconnect() { return null; }
};

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock Element.scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// Mock Element.scrollTo
Element.prototype.scrollTo = jest.fn();

// Suppress console errors in tests (optional, remove if you want to see them)
// global.console.error = jest.fn();

// Mock react-markdown
jest.mock('react-markdown', () => {
  const React = require('react');
  return function ReactMarkdown({ children }) {
    return React.createElement('div', { className: 'markdown-mock' }, children);
  };
});

// Mock remark-gfm
jest.mock('remark-gfm', () => ({
  __esModule: true,
  default: function() { return {}; },
}));

// Default fetch mock — individual tests override via helpers/fetch.ts
global.fetch = jest.fn().mockImplementation(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve("{}"),
    headers: new Map(),
  })
);

