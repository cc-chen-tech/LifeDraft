import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test.describe('protected real-provider release smoke evidence', () => {
  test('publishes a passing smoke report and renders the production shell', async ({ page }) => {
    const reportPath = process.env.MODEL_SMOKE_REPORT;
    const screenshotPath = process.env.MODEL_SMOKE_SCREENSHOT;
    test.skip(!reportPath, 'MODEL_SMOKE_REPORT is only set by the protected model-smoke flow');
    expect(reportPath, 'MODEL_SMOKE_REPORT must be provided').toBeTruthy();

    await page.goto('/');
    await expect(page).toHaveURL(/\/$/);
    if (screenshotPath) {
      await page.screenshot({ path: screenshotPath, fullPage: true });
    }

    const report = JSON.parse(fs.readFileSync(reportPath as string, 'utf8')) as {
      schema_version: number;
      status: string;
      checks: Array<{ name: string; outcome: string }>;
      model_events: { count: number; fallback_count: number; unknown_error_count: number };
    };
    expect(report.schema_version).toBe(1);
    expect(report.status).toBe('passed');
    expect(report.checks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: 'text_generation_and_constraints', outcome: 'passed' }),
        expect.objectContaining({ name: 'image_generation_persistence_and_resource', outcome: 'passed' }),
        expect.objectContaining({ name: 'tts_generation_persistence_and_playability', outcome: 'passed' }),
        expect.objectContaining({ name: 'daily_world_projection_persistence', outcome: 'passed' }),
      ]),
    );
    expect(report.model_events.count).toBeGreaterThan(0);
    expect(report.model_events.fallback_count).toBe(0);
    expect(report.model_events.unknown_error_count).toBe(0);
  });
});
