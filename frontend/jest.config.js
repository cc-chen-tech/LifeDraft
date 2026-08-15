/** @type {import('jest').Config} */
const config = {
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  // ★ 使用项目内的缓存目录，避免 macOS 沙箱权限问题
  cacheDirectory: '<rootDir>/.jest-cache',
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: 'tsconfig.json',
      useESM: true,
    }],
  },
  testMatch: ['**/__tests__/**/*.(test|spec).(ts|tsx)', '**/*.(test|spec).(ts|tsx)'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/types.ts',
    '!src/**/__tests__/**',
  ],
  // Repository-owned coverage policy; enforced directly by Jest.
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70,
    },
  },
  transformIgnorePatterns: [
    'node_modules/(?!(zustand|react-markdown|remark-gfm|unist-util-stringify-position|unist-util-position|unist-util-generated|unist-util-is|devlop|html-url-attributes|mdast-util-|markdown-|micromark-|remark-|trim-lines|vfile|space-separated-tokens|property-information|comma-separated-tokens|bail|is-plain-obj|decode-named-character-reference|character-entities|ccount|escape-string-regexp)/)',
  ],
  testPathIgnorePatterns: ['<rootDir>/node_modules/', '<rootDir>/.next/', '<rootDir>/e2e/'],
};

module.exports = config;
