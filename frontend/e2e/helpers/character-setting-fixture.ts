import type { Page } from '@playwright/test';

export const FRONTEND_ORIGIN = `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;

export const STORY_ORIGIN = {
  revision: 1,
  start_date: '2026-08-13',
  starting_age: 26,
  era_description: '2020年代中期的现代都市',
  life_stage_description: '职业与生活都需要重新判断的阶段',
  world_context: '一个允许重新选择人生方向的世界',
};

export type StoryOriginRequest = {
  method: string;
  origin: string;
  path: string;
  search: string;
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

export async function installStoryOriginGenerationFixture(page: Page, delayMs = 250) {
  const requests: StoryOriginRequest[] = [];

  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname !== '/api/character/story-origin') return;
    requests.push({
      method: request.method(),
      origin: url.origin,
      path: url.pathname,
      search: url.search,
    });
  });

  await page.route(/\/api\/character\/story-origin(?:\?.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const body = parseRequestBody(request.postData());
    if (
      request.method() !== 'POST' ||
      url.origin !== FRONTEND_ORIGIN ||
      url.pathname !== '/api/character/story-origin' ||
      url.search !== '' ||
      typeof body.player_name !== 'string' ||
      body.player_name.trim() === ''
    ) {
      await route.fulfill({
        status: 418,
        contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify({ message: 'Unexpected story origin fixture request' }),
      });
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(STORY_ORIGIN),
    });
  });

  return requests;
}

export async function installCharacterSettingGenerationFixture(page: Page) {
  await page.route(/\/api\/character\/setting(?:\?.*)?$/, async (route) => {
    const body = parseRequestBody(route.request().postData());
    const settingType = String(body.setting_type ?? '');
    const responses: Record<string, Record<string, unknown>> = {
      gender: {
        gender: '女性',
        gender_description: '她习惯先观察，再作出自己的判断',
      },
      world: {
        world_description: '2026 年的现代都市，工作与个人生活都在快速变化。',
        technology_level: '当代',
        social_system: '现代城市社会',
        economy: '稳定而充满变化',
      },
    };
    const response = responses[settingType];
    if (route.request().method() !== 'POST' || !response) {
      await route.fulfill({
        status: 418,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Unexpected character setting fixture request' }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });
}
