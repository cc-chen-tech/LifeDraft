import { defineConfig } from '@playwright/test';

// Standalone config for story101.live exploration
// Does NOT start any local servers
export default defineConfig({
  testDir: './e2e',
  testMatch: 'story101-exploration.spec.ts',
  timeout: 600_000, // 10 min per test
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'exploration-report/html' }]],
  use: {
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'on',
    video: 'on',
    trace: 'on',
  },
});
