import type { Page } from '@playwright/test';

export const FRONTEND_ORIGIN = `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;

export const ERA_SETTING = {
  year: 2026,
  era_name: '现代',
  era_description: '当代城市生活',
  world_context: '一个允许重新选择人生方向的世界',
};

export type CharacterSettingRequest = {
  method: string;
  origin: string;
  path: string;
  search: string;
  settingType: string;
};

function parseRequestBody(rawBody: string | null): Record<string, unknown> {
  if (!rawBody) return {};
  try {
    const parsed = JSON.parse(rawBody) as unknown;
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

export async function installEraGenerationFixture(page: Page, delayMs = 250) {
  const requests: CharacterSettingRequest[] = [];

  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname !== '/api/character/setting') return;
    const body = parseRequestBody(request.postData());
    requests.push({
      method: request.method(),
      origin: url.origin,
      path: url.pathname,
      search: url.search,
      settingType: String(body.setting_type ?? ''),
    });
  });

  await page.route(/\/api\/character\/setting(?:\?.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const body = parseRequestBody(request.postData());
    if (
      request.method() !== 'POST' ||
      url.origin !== FRONTEND_ORIGIN ||
      url.pathname !== '/api/character/setting' ||
      url.search !== '' ||
      body.setting_type !== 'era'
    ) {
      await route.fulfill({
        status: 418,
        contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify({ message: 'Unexpected character setting fixture request' }),
      });
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(ERA_SETTING),
    });
  });

  return requests;
}
