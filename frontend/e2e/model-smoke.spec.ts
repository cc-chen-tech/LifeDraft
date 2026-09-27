import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test.describe('protected real-provider release smoke evidence', () => {
  test('delivers the persisted daily opening through authenticated play and reload', async ({ page, context }) => {
    const reportPath = process.env.MODEL_SMOKE_REPORT;
    const screenshotPath = process.env.MODEL_SMOKE_SCREENSHOT;
    test.skip(!reportPath, 'MODEL_SMOKE_REPORT is only set by the protected model-smoke flow');
    expect(reportPath, 'MODEL_SMOKE_REPORT must be provided').toBeTruthy();


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
        expect.objectContaining({ name: 'daily_opening_delivery', outcome: 'passed' }),
        expect.objectContaining({ name: 'story_origin_generation', outcome: 'passed' }),
        expect.objectContaining({ name: 'image_generation_persistence_and_resource', outcome: 'passed' }),
        expect.objectContaining({ name: 'tts_generation_persistence_and_playability', outcome: 'passed' }),
        expect.objectContaining({ name: 'daily_world_projection_persistence', outcome: 'passed' }),
      ]),
    );
    expect(report.model_events.count).toBeGreaterThan(0);
    expect(report.model_events.fallback_count).toBe(0);
    expect(report.model_events.unknown_error_count).toBe(0);
    const sessionPath = path.join(path.dirname(reportPath as string), 'data/model-smoke/smoke-browser-session.json');
    const session = JSON.parse(fs.readFileSync(sessionPath, 'utf8')) as { game_id: number; auth_token: string };
    const origin = `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
    await context.addCookies([{ name: 'auth_token', value: session.auth_token, url: origin, httpOnly: true, sameSite: 'Lax' }]);
    // Use normal owned API and production UI, with no intercepted success payloads.
    const settings = await context.request.patch(`${origin}/api/voice-reading/settings`, { data: { auto_read_enabled: false } });
    expect(settings.ok()).toBeTruthy();
    const saved = await context.request.get(`${origin}/api/games/${session.game_id}`);
    expect(saved.ok()).toBeTruthy();
    const body = await saved.json();
    const event = body.current_event as { event_id: string; story_date: string; event_description: string; options: Array<{ text: string }> };
    expect(event.options).toHaveLength(3);
    expect(event.story_date).toBe("1421-04-15");
    expect(event.event_description).toContain("于谦");
    expect(body.constraint_level).toBe("master");
    const paragraphs = event.event_description.split(/\n\s*\n/).filter(Boolean);
    expect(paragraphs.length).toBeGreaterThanOrEqual(2);
    for (let visit = 0; visit < 2; visit += 1) {
      if (visit === 0) await page.goto(`/play?gameId=${session.game_id}`);
      else await page.reload();
      const expand = page.getByRole('button', { name: '查看故事正文' }).first();
      await expect(expand).toBeVisible();
      await expand.click();
      const storyRegion = page.getByRole('region', { name: '故事正文' });
      await expect(storyRegion).toContainText(paragraphs[0]);
      for (const option of event.options) {
        await expect(page.getByRole('button', { name: option.text, exact: true })).toBeVisible();
      }
    }
    if (screenshotPath) await page.screenshot({ path: screenshotPath, fullPage: true });
  });
});
