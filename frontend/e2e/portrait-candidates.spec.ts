import { expect, test, type Page } from '@playwright/test';
import type { PortraitCandidateState } from '../src/lib/api';

type SlotStatus = 'ready' | 'running' | 'failed' | 'queued';
type PortraitFixture = {
  enqueueCount: number;
  retryBodies: number[];
  selections: number[];
  reads: number;
  batch: PortraitCandidateState | null;
  selectedImageId: number | null;
  advance: (slots: SlotStatus[], status: string) => void;
  releaseSelection: () => void;
};
const fixtures = new WeakMap<Page, PortraitFixture>();
const origin = {
  revision: 1, start_date: '0960-01-01', starting_age: 20,
  era_description: '北宋初年的州城', life_stage_description: '初入成年', world_context: '驿路与坊市',
};

async function installPortraitRoutes(page: Page, options: {
  enqueueDisconnects?: boolean; slots: SlotStatus[]; selectedImageId: number;
}) {
  let settings: Record<string, unknown> = {};
  let imageBase = 41;
  let selectionResolve: (() => void) | undefined;
  const selectionGate = new Promise<void>(resolve => { selectionResolve = resolve; });
  const fixture: PortraitFixture = {
    enqueueCount: 0, retryBodies: [], selections: [], reads: 0,
    batch: null, selectedImageId: options.selectedImageId,
    releaseSelection: () => selectionResolve?.(),
    advance(slots, status) {
      if (!fixture.batch) throw new Error('No accepted batch');
      fixture.batch.status = status;
      fixture.batch.slots = slots.map((slotStatus, slot_index) => ({
        slot_index, status: slotStatus, image_id: slotStatus === 'ready' ? imageBase + slot_index : null,
      }));
      fixture.batch.completed_count = slots.filter(value => value === 'ready').length;
    },
  };
  fixtures.set(page, fixture);
  // Every API request is intercepted, including unexpected mutations: no provider is reachable.
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/character/story-origin') return json(origin);
    if (path === '/api/character/setting') {
      const type = route.request().postDataJSON().setting_type;
      return json(type === 'gender' ? { gender: '女', gender_description: '女性' }
        : type === 'world' ? { world_type: '历史现实', world_description: '州城世界' }
        : type === 'family' ? { family_description: '坊市人家' } : { traits_description: '坚毅' });
    }
    if (path === '/api/character/relationship') return json({ name: '友人', role: '朋友', relationship: '相识多年' });
    if (path === '/api/character/relationships-summary') return json({ relationships_description: '坊市旧友' });
    if (path === '/api/games' && method === 'POST') {
      settings = route.request().postDataJSON().character_settings;
      return json({ game_id: 701, player_state: {}, progress: {}, round_info: {}, current_event: null, constraint_level: 'expert' });
    }
    if (path === '/api/games/701') return json({
      game_id: 701, player_state: { player_name: '阿衡', life_vision: '', character_settings: settings },
      progress: {}, round_info: {}, current_event: null, constraint_level: 'expert',
    });
    if (path === '/api/images/character/candidates') {
      if (method === 'POST') {
        fixture.enqueueCount += 1;
        const body = route.request().postDataJSON();
        expect(body.game_id).toBe(701);
        const fresh = body.mode === 'fresh';
        imageBase = fresh ? 51 : 41;
        fixture.batch = {
          batch_id: fresh ? 12 : 11, job_id: fresh ? 22 : 21, game_id: 701,
          origin_revision: 1, mode: body.mode, status: 'running', completed_count: 0,
          selected_image_id: fixture.selectedImageId, slots: [],
        };
        fixture.advance(fresh ? ['queued', 'queued', 'queued'] : options.slots,
          !fresh && options.slots.every(slot => slot === 'ready') ? 'succeeded' : 'running');
        if (options.enqueueDisconnects && !fresh) return route.abort('connectionreset');
      } else fixture.reads += 1;
      return json(fixture.batch);
    }
    if (path === '/api/images/character/candidates/11/retry') {
      fixture.retryBodies.push(11);
      return json(fixture.batch);
    }
    if (path === '/api/images/character/selection') {
      if (method === 'PUT') {
        const body = route.request().postDataJSON();
        expect(body.game_id).toBe(701);
        fixture.selections.push(body.image_id);
        await selectionGate;
        fixture.selectedImageId = body.image_id;
        if (fixture.batch) fixture.batch.selected_image_id = body.image_id;
      }
      return json({ game_id: 701, image_id: fixture.selectedImageId });
    }
    if (path === '/api/images/character/jobs/latest') return json(null);
    if (path === '/api/images/game/701') {
      const ids = new Set([options.selectedImageId, ...(fixture.batch?.slots.flatMap(slot => slot.image_id ? [slot.image_id] : []) ?? [])]);
      return json({ images: [...ids].sort((a, b) => b - a).map(image_id => ({ image_id, image_url: `/portrait-fixture/${image_id}.svg`, image_type: 'character', entity_key: 'player_main', entity_name: '阿衡' })), total: ids.size });
    }
    if (path.startsWith('/api/auth/')) return json({ user: null });
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: `Unmocked ${method} ${path}` }) });
  });
  await page.route('**/portrait-fixture/*.svg', route => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="90" height="170"><rect width="90" height="170" fill="tan"/></svg>',
  }));
  return fixture;
}

async function reachPortraitStep(page: Page) {
  await page.getByPlaceholder('输入你的角色名').fill('阿衡');
  await expect(page.getByTestId('story-origin-summary')).toBeVisible();
  await page.getByRole('button', { name: '下一步', exact: true }).click();
  await expect(page.getByText('女性', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '下一步', exact: true }).click();
  await expect(page.getByText('州城世界', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '下一步', exact: true }).click();
  await expect(page.getByRole('heading', { name: '人物形象', exact: true })).toBeVisible();
}

async function portraitEnqueueCount(page: Page) { return fixtures.get(page)!.enqueueCount; }

test('restores three candidates after a disconnected enqueue and reload, then retries only missing slots', async ({ page }) => {
  const fixture = await installPortraitRoutes(page, { enqueueDisconnects: true, slots: ['ready', 'running', 'failed'], selectedImageId: 41 });
  await page.goto('/create');
  await reachPortraitStep(page);
  await expect(page.getByText('已完成 1/3')).toBeVisible();
  expect(await portraitEnqueueCount(page)).toBe(1);
  await page.clock.install();
  const readsBeforeWait = fixture.reads;
  await page.clock.fastForward(65_000);
  await expect.poll(() => fixture.reads).toBeGreaterThan(readsBeforeWait);
  await expect(page.getByText('正在生成', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '重试未完成的形象', exact: true })).toHaveCount(0);
  expect(await portraitEnqueueCount(page)).toBe(1);
  await page.reload();
  await expect(page.getByRole('button', { name: '选择人物形象 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('已完成 1/3')).toBeVisible();
  expect(await portraitEnqueueCount(page)).toBe(1);
  fixture.advance(['ready', 'failed', 'failed'], 'failed');
  await page.getByRole('button', { name: '刷新状态', exact: true }).click();
  await page.getByRole('button', { name: '重试未完成的形象', exact: true }).click();
  expect(fixture.retryBodies).toEqual([11]);
  expect(await portraitEnqueueCount(page)).toBe(1);
  await expect(page.getByRole('button', { name: '选择人物形象 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
});

test('stages fresh candidates while retaining the old selected portrait until the server confirms a choice', async ({ page }) => {
  const fixture = await installPortraitRoutes(page, { slots: ['ready', 'ready', 'ready'], selectedImageId: 42 });
  await page.goto('/create');
  await reachPortraitStep(page);
  const current = page.getByRole('img', { name: '阿衡', exact: true });
  await expect(current).toHaveAttribute('src', '/portrait-fixture/42.svg');
  await page.getByRole('button', { name: '完全重新生成（三张新形象）', exact: true }).click();
  await expect(page.getByText('已完成 0/3')).toBeVisible();
  await expect(current).toHaveAttribute('src', '/portrait-fixture/42.svg');
  fixture.advance(['ready', 'running', 'failed'], 'running');
  await page.getByRole('button', { name: '刷新状态', exact: true }).click();
  await expect(page.getByText('已完成 1/3')).toBeVisible();
  await expect(current).toHaveAttribute('src', '/portrait-fixture/42.svg');
  expect(fixture.selections).toEqual([]);
  await page.reload();
  await expect(page.getByText('已完成 1/3')).toBeVisible();
  await expect(current).toHaveAttribute('src', '/portrait-fixture/42.svg');
  expect(await portraitEnqueueCount(page)).toBe(2);
  await page.getByRole('button', { name: '选择人物形象 1', exact: true }).click();
  await expect.poll(() => fixture.selections).toEqual([51]);
  await expect(current).toHaveAttribute('src', '/portrait-fixture/42.svg');
  fixture.releaseSelection();
  await expect(page.getByRole('button', { name: '选择人物形象 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(current).toHaveAttribute('src', '/portrait-fixture/51.svg');
  expect(await portraitEnqueueCount(page)).toBe(2);
});


test('revisiting an old game without a candidate batch never enqueues portraits', async ({ page }) => {
  await installPortraitRoutes(page, { slots: ['ready', 'ready', 'ready'], selectedImageId: 41 });
  await page.addInitScript(() => {
    localStorage.setItem('game-store', JSON.stringify({ state: { gameId: 701, playerState: null }, version: 0 }));
  });
  await page.goto('/create');
  await expect.poll(() => fixtures.get(page)!.reads).toBeGreaterThan(0);
  await expect(page.getByPlaceholder('输入你的角色名')).toBeVisible();
  expect(await portraitEnqueueCount(page)).toBe(0);
});

test('an unavailable saved game does not enqueue another batch', async ({ page }) => {
  await installPortraitRoutes(page, { slots: ['ready', 'ready', 'ready'], selectedImageId: 41 });
  await page.goto('/create');
  await reachPortraitStep(page);
  await expect(page.getByText('已完成 3/3')).toBeVisible();
  await page.route('**/api/games/701', route => route.fulfill({
    status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Game not found' }),
  }));
  const unavailable = page.waitForResponse(response => response.url().endsWith('/api/games/701') && response.status() === 404);
  await page.reload();
  await unavailable;
  await expect(page.getByPlaceholder('输入你的角色名')).toBeVisible();
  await expect(page.getByRole('heading', { name: '故事起点', exact: true })).toBeVisible();
  expect(await portraitEnqueueCount(page)).toBe(1);
});
