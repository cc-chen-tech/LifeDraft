import {
  expect,
  test,
  type Frame,
  type Page,
  type Request,
  type TestInfo,
} from '@playwright/test';

type NarrativeFixtureState =
  | 'initial'
  | 'partial'
  | 'delayed'
  | 'reconnecting'
  | 'polling'
  | 'failed';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT = { width: 390, height: 844 };
const FORBIDDEN_LOADING_COPY = /\d+\s*(秒|分)|预计|快速生成|质量|\bAI\b/i;

const fixture = (page: Page) => page.getByTestId('narrative-loading-fixture');

function viewportFor(testInfo: TestInfo) {
  return testInfo.project.name === 'Mobile Safari' ? MOBILE_VIEWPORT : DESKTOP_VIEWPORT;
}

function viewportLabel(testInfo: TestInfo) {
  const viewport = viewportFor(testInfo);
  return `${viewport.width}x${viewport.height}`;
}

async function openState(page: Page, state: NarrativeFixtureState) {
  await page.goto(`/e2e-regression?narrativeLoading=${state}`);
  await expect(fixture(page)).toBeVisible();
  await expect(fixture(page).getByTestId('narrative-loading-fixture-state')).toHaveText(state);
}

async function expectNoHorizontalOverflow(page: Page) {
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
}

async function expectSharedContract(page: Page) {
  await expect(fixture(page).getByRole('status')).toHaveCount(1);
  await expect(fixture(page)).not.toContainText(FORBIDDEN_LOADING_COPY);
  await expectNoHorizontalOverflow(page);
}

test.beforeEach(async ({ page }, testInfo) => {
  await page.setViewportSize(viewportFor(testInfo));
});

test('server-renders legacy content immediately when narrative loading is absent or unsupported', async ({
  request,
}) => {
  for (const url of ['/e2e-regression', '/e2e-regression?narrativeLoading=unknown']) {
    const response = await request.get(url);
    expect(response.ok()).toBe(true);
    const responseBody = await response.text();

    expect(responseBody).toContain('data-testid="e2e-regression-legacy"');
    expect(responseBody).not.toContain('data-testid="narrative-loading-fixture"');
  }
});

test('server-renders only the allowlisted narrative fixture without client JavaScript', async ({
  request,
}) => {
  for (const state of [
    'initial',
    'partial',
    'delayed',
    'reconnecting',
    'polling',
    'failed',
  ] as const) {
    const response = await request.get(`/e2e-regression?narrativeLoading=${state}`);
    expect(response.ok()).toBe(true);
    const responseBody = await response.text();

    expect(responseBody).toContain('data-testid="narrative-loading-fixture"');
    expect(responseBody).not.toContain('data-testid="e2e-regression-legacy"');
  }
});

test('renders the six deterministic narrative loading states and captures visual evidence', async ({
  page,
}, testInfo) => {
  const applicationRequests: string[] = [];
  page.on('request', (request) => {
    const requestPath = new URL(request.url()).pathname;
    if (requestPath.startsWith('/api/')) applicationRequests.push(requestPath);
  });

  const visualStates: NarrativeFixtureState[] = [
    'initial',
    'partial',
    'delayed',
    'reconnecting',
    'failed',
  ];

  for (const state of visualStates) {
    await openState(page, state);
    await expectSharedContract(page);

    if (state === 'initial') {
      await expect(fixture(page).getByTestId('narrative-loading-screen')).toBeVisible();
      await expect(fixture(page).getByTestId('narrative-loading-inline')).toHaveCount(0);
      await expect(fixture(page).getByText('人生开篇，正在落笔')).toBeVisible();
      await expect(fixture(page).getByText('正在写作', { exact: true })).toBeVisible();
      await expect(fixture(page).getByRole('button', { name: /重新连接|重试/ })).toHaveCount(0);
    }

    if (state === 'partial') {
      await expect(fixture(page).getByText('首段正文已经抵达。')).toBeVisible();
      await expect(fixture(page).getByTestId('narrative-loading-inline')).toBeVisible();
      await expect(fixture(page).getByTestId('narrative-loading-screen')).toHaveCount(0);
      await expect(fixture(page).getByTestId('narrative-loading-section')).toHaveCount(0);
      await expect(fixture(page).getByText('人生开篇，正在落笔')).toBeVisible();
      await expect(fixture(page).getByText('正在写作', { exact: true })).toBeVisible();
      await expect(fixture(page).getByRole('button', { name: /重新连接|重试/ })).toHaveCount(0);
    }

    if (state === 'delayed') {
      await expect(fixture(page).getByTestId('narrative-loading-section')).toBeVisible();
      await expect(fixture(page).getByText('这一页仍在继续写作')).toBeVisible();
      await expect(fixture(page).getByRole('button', { name: /重新连接|重试/ })).toHaveCount(0);
    }

    if (state === 'reconnecting') {
      await expect(fixture(page).getByRole('button', { name: '重新连接' })).toBeVisible();
      await expect(fixture(page).getByRole('button', { name: '重试' })).toHaveCount(0);
    }

    if (state === 'failed') {
      await expect(fixture(page).getByRole('button', { name: '重试' })).toBeVisible();
      await expect(fixture(page).getByRole('button', { name: '重新连接' })).toHaveCount(0);
    }

    await page.screenshot({
      path: testInfo.outputPath(`narrative-loading-${viewportLabel(testInfo)}-${state}.png`),
      fullPage: false,
    });
  }

  await openState(page, 'polling');
  await expectSharedContract(page);
  await expect(fixture(page).getByRole('button', { name: '重新连接' })).toBeVisible();
  await expect(fixture(page).getByRole('button', { name: '重试' })).toHaveCount(0);
  expect(applicationRequests).toEqual([]);
});

test('switches from opening screen to partial prose without a reload or overflow', async ({
  page,
}) => {
  await openState(page, 'initial');
  const initialNavigationCount = await page.evaluate(
    () => performance.getEntriesByType('navigation').length,
  );
  const initialBounds = await fixture(page).boundingBox();
  expect(initialBounds).not.toBeNull();

  await fixture(page).getByRole('button', { name: '部分正文' }).click();

  await expect(fixture(page).getByTestId('narrative-loading-fixture-state')).toHaveText('partial');
  await expect(fixture(page).getByText('首段正文已经抵达。')).toBeVisible();
  await expect(fixture(page).getByTestId('narrative-loading-screen')).toHaveCount(0);
  await expect(fixture(page).getByTestId('narrative-loading-inline')).toBeVisible();
  expect(await page.evaluate(() => performance.getEntriesByType('navigation').length)).toBe(
    initialNavigationCount,
  );

  const partialBounds = await fixture(page).boundingBox();
  expect(partialBounds).not.toBeNull();
  expect(initialBounds!.x).toBeGreaterThanOrEqual(0);
  expect(initialBounds!.x + initialBounds!.width).toBeLessThanOrEqual(
    viewportFor(test.info()).width,
  );
  expect(partialBounds!.x).toBeGreaterThanOrEqual(0);
  expect(partialBounds!.x + partialBounds!.width).toBeLessThanOrEqual(
    viewportFor(test.info()).width,
  );
  await expectSharedContract(page);
});

test('keeps reconnect and retry actions local to the fixture', async ({ page }) => {
  for (const state of ['reconnecting', 'polling', 'failed'] as const) {
    await openState(page, state);
    const beforeUrl = page.url();
    const actionName = state === 'failed' ? '重试' : '重新连接';
    const apiRequests: string[] = [];
    const frameNavigations: string[] = [];
    let loadCount = 0;
    const observeRequest = (request: Request) => {
      const requestPath = new URL(request.url()).pathname;
      if (requestPath.startsWith('/api/')) apiRequests.push(requestPath);
    };
    const observeFrameNavigation = (frame: Frame) => {
      if (frame === page.mainFrame()) frameNavigations.push(frame.url());
    };
    const observeLoad = () => {
      loadCount += 1;
    };

    page.on('request', observeRequest);
    page.on('framenavigated', observeFrameNavigation);
    page.on('load', observeLoad);

    await expect(fixture(page).getByTestId('narrative-loading-action-count')).toHaveText('0');
    await fixture(page).getByRole('button', { name: actionName }).click();
    await expect(fixture(page).getByTestId('narrative-loading-action-count')).toHaveText('1');
    await expect(fixture(page).getByTestId('narrative-loading-fixture-state')).toHaveText(state);
    await page.waitForTimeout(100);
    expect(page.url()).toBe(beforeUrl);
    expect(apiRequests).toEqual([]);
    expect(frameNavigations).toEqual([]);
    expect(loadCount).toBe(0);
    await expectSharedContract(page);

    page.off('request', observeRequest);
    page.off('framenavigated', observeFrameNavigation);
    page.off('load', observeLoad);
  }
});

test('removes divider animation when reduced motion is preferred', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openState(page, 'initial');

  expect(
    await fixture(page)
      .locator('.narrative-loading-divider')
      .evaluate((element) => window.getComputedStyle(element).animationName),
  ).toBe('none');
  await expectSharedContract(page);
});

test('ignores unsupported or absent narrative loading parameters', async ({ page }) => {
  for (const url of ['/e2e-regression', '/e2e-regression?narrativeLoading=unknown']) {
    await page.goto(url);
    await expect(fixture(page)).toHaveCount(0);
    await expect(page.getByRole('button', { name: '模拟后端完成' })).toBeVisible();
  }
});
