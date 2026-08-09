import {
  expect,
  test,
  type Locator,
  type Page,
  type TestInfo,
} from "@playwright/test";

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT = { width: 390, height: 844 };
const RESPONSIVE_WIDTHS = [320, 375, 390] as const;
const SOUND_GAME_ID = 73;
const AUTH_SESSION_HINT = "story2-auth-session";
const FRONTEND_ORIGIN = `http://localhost:${process.env.E2E_FRONTEND_PORT ?? "3000"}`;

const AUTH_USER = {
  user_id: 7,
  public_id: "E2E-READER-7",
  display_name: "墨页读者",
  private_id: "E2E-PRIVATE-7",
};

const LONG_SAVE_NAME = "这是一位名字很长需要在三百二十像素宽度下完整换行的角色";
const SAVED_GAMES = [
  {
    game_id: 41,
    player_name: LONG_SAVE_NAME,
    age: 28,
    week: 6,
    updated_at: "2026-08-09T10:00:00Z",
    created_at: "2026-08-01T02:00:00Z",
  },
  {
    game_id: 42,
    player_name: "江砚",
    age: 31,
    week: 0,
    updated_at: "2026-08-08T09:30:00Z",
    created_at: "2026-08-08T09:00:00Z",
  },
];

const LONG_LIFE_VISION = "在很长的人生愿景里保留好奇、耐心与重新出发的勇气";
const PRESETS = [
  {
    preset_id: 51,
    preset_name: "远行者",
    player_name: "林渡",
    life_vision: LONG_LIFE_VISION,
    created_at: "2026-08-09T10:00:00Z",
    character_settings: {
      era: {
        era: "现代",
        year: 2026,
        era_name: "现代",
        era_description: "当代城市生活",
        world_context: "一个可以重新选择人生方向的世界",
      },
      key_people: [],
      relationships_description: "尚未建立关系",
    },
  },
  {
    preset_id: 52,
    preset_name: "   ",
    player_name: "沈禾",
    life_vision: "安静地写完一本书",
    created_at: "2026-08-08T09:00:00Z",
    character_settings: {
      era: {
        era: "现代",
        year: 2026,
        era_name: "现代",
        era_description: "当代日常",
        world_context: "临海的小城",
      },
      key_people: [],
      relationships_description: "与家人保持联系",
    },
  },
];

const PLAYLIST = {
  game_id: SOUND_GAME_ID,
  current_song: {
    id: "e2e-song-73",
    name: "页间夜航",
    artists: ["story101 配乐"],
    album: "人生草稿本",
    duration: 180,
    url: "https://example.invalid/e2e-song-73.mp3",
    source: "netease",
  },
  queue: [],
  played_songs: [],
  is_playing: false,
  volume: 0.5,
  current_position_ms: 0,
};

type ApiRequestRecord = {
  method: string;
  origin: string;
  path: string;
  search: string;
};

type ApiScenario = {
  requests: ApiRequestRecord[];
  unexpected: string[];
};

type ExpectedApiRequest = {
  method: "GET" | "DELETE";
  path: string;
  count: number;
};

function viewportFor(testInfo: TestInfo) {
  return testInfo.project.name === "Mobile Safari"
    ? MOBILE_VIEWPORT
    : DESKTOP_VIEWPORT;
}

async function beginApiScenario(
  page: Page,
  options: { authenticated?: boolean; soundGameId?: number } = {},
): Promise<ApiScenario> {
  const scenario: ApiScenario = { requests: [], unexpected: [] };

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) {
      scenario.requests.push({
        method: request.method(),
        origin: url.origin,
        path: url.pathname,
        search: url.search,
      });
    }
  });

  await page.addInitScript(
    ({ authenticated, soundGameId, authSessionHint }) => {
      window.localStorage.clear();
      window.sessionStorage.clear();
      if (authenticated) {
        window.sessionStorage.setItem(authSessionHint, "1");
      }
      if (soundGameId !== undefined) {
        window.localStorage.setItem("gameId", String(soundGameId));
      }
    },
    {
      authenticated: options.authenticated ?? false,
      soundGameId: options.soundGameId,
      authSessionHint: AUTH_SESSION_HINT,
    },
  );

  // Install the fallback first. Playwright evaluates later matching routes first,
  // so every explicitly installed mock below wins and every other API is blocked.
  await page.route(/\/api\/.*/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    scenario.unexpected.push(`${request.method()} ${url.href}`);
    await route.fulfill({
      status: 418,
      contentType: "application/json",
      body: JSON.stringify({ message: `Unexpected E2E API request: ${url.href}` }),
    });
  });

  return scenario;
}

function isExactFrontendApi(requestUrl: string, path: string) {
  const url = new URL(requestUrl);
  return (
    url.origin === FRONTEND_ORIGIN &&
    url.pathname === path &&
    url.search === ""
  );
}

async function mockAuth(page: Page, authenticated: boolean) {
  await page.route(/\/api\/auth\/me(?:\?.*)?$/, async (route) => {
    if (
      route.request().method() !== "GET" ||
      !isExactFrontendApi(route.request().url(), "/api/auth/me")
    ) {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: authenticated ? 200 : 401,
      contentType: "application/json",
      body: JSON.stringify(
        authenticated ? AUTH_USER : { message: "Not authenticated" },
      ),
    });
  });
}

async function mockGames(page: Page, games: typeof SAVED_GAMES | []) {
  await page.route(/\/api\/games(?:\?.*)?$/, async (route) => {
    if (
      route.request().method() !== "GET" ||
      !isExactFrontendApi(route.request().url(), "/api/games")
    ) {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(games),
    });
  });
}

async function mockPresets(page: Page, presets: typeof PRESETS | []) {
  await page.route(/\/api\/presets(?:\?.*)?$/, async (route) => {
    if (
      route.request().method() !== "GET" ||
      !isExactFrontendApi(route.request().url(), "/api/presets")
    ) {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(presets),
    });
  });
}

async function mockSoundPlaylist(page: Page) {
  await page.route(
    new RegExp(`/api/music/playlist/${SOUND_GAME_ID}(?:\\?.*)?$`),
    async (route) => {
      if (
        route.request().method() !== "GET" ||
        !isExactFrontendApi(
          route.request().url(),
          `/api/music/playlist/${SOUND_GAME_ID}`,
        )
      ) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PLAYLIST),
      });
    },
  );
}

async function expectOnlyApiRequests(
  page: Page,
  scenario: ApiScenario,
  expected: ExpectedApiRequest[],
) {
  await page.waitForTimeout(100);

  expect(scenario.unexpected, "all browser APIs must be explicitly mocked").toEqual(
    [],
  );
  expect(
    scenario.requests.filter(
      ({ origin, search }) => origin !== FRONTEND_ORIGIN || search !== "",
    ),
    "API mocks only accept same-origin requests without query parameters",
  ).toEqual([]);

  const actualCounts = scenario.requests.reduce<Record<string, number>>(
    (counts, { method, path, search }) => {
      const signature = `${method} ${path}${search}`;
      counts[signature] = (counts[signature] ?? 0) + 1;
      return counts;
    },
    {},
  );
  const expectedCounts = expected.reduce<Record<string, number>>(
    (counts, { method, path, count }) => {
      counts[`${method} ${path}`] = count;
      return counts;
    },
    {},
  );
  expect(
    actualCounts,
    "every necessary API call must be present exactly as often as the scenario permits",
  ).toEqual(expectedCounts);
  expect(
    scenario.requests.filter(({ path }) =>
      /\/(?:generate|recommend|rewrite|choices|chat)(?:\/|$)/.test(path),
    ),
    "real generation and recommendation services must never be called",
  ).toEqual([]);
}

async function expectSingleReadingSurface(page: Page) {
  await expect(
    page.locator('[data-slot="surface"][data-variant="reading"]'),
  ).toHaveCount(1);
  await expect(page.locator('[data-slot="card"]')).toHaveCount(0);
}

async function expectNoHorizontalOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
    `document overflowed at ${await page.evaluate(() => window.innerWidth)}px`,
  ).toBe(true);
}

async function expectTouchTargetsAtLeast44(root: Locator) {
  const undersized = await root
    .locator('button, input, textarea, a[role="button"]')
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        const rect = element.getBoundingClientRect();
        let current: Element | null = element;
        let reachable = true;
        while (current) {
          const currentStyle = getComputedStyle(current);
          if (
            current.hasAttribute("inert") ||
            current.getAttribute("aria-hidden") === "true" ||
            currentStyle.display === "none" ||
            currentStyle.visibility === "hidden" ||
            currentStyle.pointerEvents === "none"
          ) {
            reachable = false;
            break;
          }
          current = current.parentElement;
        }
        const htmlElement = element as HTMLElement;
        const layoutWidth = htmlElement.offsetWidth;
        const layoutHeight = htmlElement.offsetHeight;
        const visible =
          reachable &&
          rect.width > 0 &&
          rect.height > 0;
        if (!visible || (layoutWidth >= 44 && layoutHeight >= 44)) return [];
        return [
          {
            label:
              element.getAttribute("aria-label") ||
              element.textContent?.trim() ||
              element.tagName,
            width: layoutWidth,
            height: layoutHeight,
          },
        ];
      }),
    );

  expect(undersized, "every visible interactive target must be at least 44px").toEqual(
    [],
  );
}

async function expectReadableTextSizes(page: Page) {
  const undersized = await page.locator("main").evaluate((main) =>
    Array.from(main.querySelectorAll("h1, h2, p, button, a[role='button']")).flatMap(
      (element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          rect.width === 0 ||
          rect.height === 0
        ) {
          return [];
        }
        const fontSize = Number.parseFloat(style.fontSize);
        return fontSize >= 12
          ? []
          : [
              {
                text: element.textContent?.trim().slice(0, 60),
                fontSize,
              },
            ];
      },
    ),
  );

  expect(undersized, "visible page copy must not fall below 12px").toEqual([]);
}

async function expectResponsiveSmoke(page: Page) {
  for (const width of RESPONSIVE_WIDTHS) {
    await page.setViewportSize({ width, height: MOBILE_VIEWPORT.height });
    await expectNoHorizontalOverflow(page);
    const readingSurface = page.locator(
      '[data-slot="surface"][data-variant="reading"]',
    );
    await expect(readingSurface).toHaveCount(1);
    await expect(readingSurface).toBeVisible();
    await expectHorizontalBounds(readingSurface, page);
    await expect(page.locator('[data-slot="card"]')).toHaveCount(0);
    await expectTouchTargetsAtLeast44(page.locator("body"));
    await expectReadableTextSizes(page);

    const soundPlayer = page.getByTestId("global-music-player");
    if ((await soundPlayer.count()) > 0) {
      await expectInsideViewport(soundPlayer, page);
    }
  }
}

async function expectHorizontalBounds(locator: Locator, page: Page) {
  const box = await locator.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();
  if (!box || !viewport) return;
  expect(box.x).toBeGreaterThanOrEqual(-0.5);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 0.5);
}

async function expectInsideViewport(locator: Locator, page: Page) {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();
  if (!box || !viewport) return;
  expect(box.x).toBeGreaterThanOrEqual(-0.5);
  expect(box.y).toBeGreaterThanOrEqual(-0.5);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 0.5);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 0.5);
}

async function expectUsesTextSubtleToken(locator: Locator) {
  const colors = await locator.evaluate((element) => {
    const root = document.documentElement;
    const authoredInlineValue = root.style.getPropertyValue("--text-subtle");
    const priority = root.style.getPropertyPriority("--text-subtle");
    const token = getComputedStyle(root).getPropertyValue("--text-subtle").trim();
    const normal = getComputedStyle(element).color;

    root.style.setProperty("--text-subtle", "rgb(1, 2, 3)", "important");
    const mutated = getComputedStyle(element).color;

    if (authoredInlineValue) {
      root.style.setProperty("--text-subtle", authoredInlineValue, priority);
    } else {
      root.style.removeProperty("--text-subtle");
    }

    return { token, normal, mutated };
  });

  expect(colors.token.toLowerCase()).toBe("#8f8881");
  expect(colors.normal).toBe("rgb(143, 136, 129)");
  expect(
    colors.mutated,
    "the secondary copy must consume --text-subtle rather than a lookalike token",
  ).toBe("rgb(1, 2, 3)");
}

async function expectBottomSoundReserve(page: Page) {
  const player = page.getByTestId("global-music-player");
  const spacer = page.locator('[data-app-shell-reserve-spacer="bottom"]');
  await expect(player).toBeVisible();
  await expect(player).toHaveAttribute("data-app-shell-reserve", "bottom");
  await expect(spacer).toHaveCount(1);

  const geometry = await page.evaluate(() => {
    const playerElement = document.querySelector<HTMLElement>(
      '[data-testid="global-music-player"]',
    );
    const spacerElement = document.querySelector<HTMLElement>(
      '[data-app-shell-reserve-spacer="bottom"]',
    );
    const contentElement = document.querySelector<HTMLElement>(
      '[data-slot="app-shell-content"]',
    );
    const fixedRegionsElement = document.querySelector<HTMLElement>(
      '[data-slot="app-shell-fixed-regions"]',
    );
    if (
      !playerElement ||
      !spacerElement ||
      !contentElement ||
      !fixedRegionsElement
    ) {
      return null;
    }
    const playerRect = playerElement.getBoundingClientRect();
    const spacerRect = spacerElement.getBoundingClientRect();
    const contentRect = contentElement.getBoundingClientRect();
    const fixedRegionsRect = fixedRegionsElement.getBoundingClientRect();
    const playerStyle = getComputedStyle(playerElement);
    const spacerStyle = getComputedStyle(spacerElement);
    return {
      playerPosition: playerStyle.position,
      playerBottomAnchor: playerStyle.bottom,
      playerHeight: playerRect.height,
      playerLeft: playerRect.left,
      playerTop: playerRect.top,
      playerRight: playerRect.right,
      playerBottom: playerRect.bottom,
      spacerPosition: spacerStyle.position,
      spacerTop: spacerRect.top,
      spacerBottom: spacerRect.bottom,
      spacerHeight: spacerRect.height,
      contentBottom: contentRect.bottom,
      fixedRegionsBottom: fixedRegionsRect.bottom,
      fixedRegionsHeight: fixedRegionsRect.height,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  });

  expect(geometry).not.toBeNull();
  expect(geometry?.playerPosition).toBe("fixed");
  expect(geometry?.playerBottomAnchor).not.toBe("auto");
  expect(["static", "relative"]).toContain(geometry?.spacerPosition);
  expect(geometry?.spacerTop ?? Number.NEGATIVE_INFINITY).toBeGreaterThanOrEqual(
    (geometry?.contentBottom ?? Number.POSITIVE_INFINITY) - 0.5,
  );
  expect(
    geometry?.fixedRegionsHeight ?? Number.NEGATIVE_INFINITY,
  ).toBeGreaterThanOrEqual(geometry?.spacerHeight ?? Number.POSITIVE_INFINITY);
  expect(
    geometry?.fixedRegionsBottom ?? Number.NEGATIVE_INFINITY,
  ).toBeGreaterThanOrEqual(geometry?.spacerBottom ?? Number.POSITIVE_INFINITY);
  expect(geometry?.spacerHeight ?? 0).toBeGreaterThanOrEqual(
    geometry?.playerHeight ?? Number.POSITIVE_INFINITY,
  );
  expect(geometry?.playerLeft ?? Number.NEGATIVE_INFINITY).toBeGreaterThanOrEqual(
    -0.5,
  );
  expect(geometry?.playerTop ?? Number.NEGATIVE_INFINITY).toBeGreaterThanOrEqual(
    -0.5,
  );
  expect(geometry?.playerRight ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
    (geometry?.viewportWidth ?? 0) + 0.5,
  );
  expect(geometry?.playerBottom ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
    (geometry?.viewportHeight ?? 0) + 0.5,
  );

  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.scrollY >=
          document.documentElement.scrollHeight - window.innerHeight - 1,
      ),
    )
    .toBe(true);

  const overlap = await page.evaluate(() => {
    const appShellContent = document.querySelector<HTMLElement>(
      '[data-slot="app-shell-content"]',
    );
    const playerElement = document.querySelector<HTMLElement>(
      '[data-testid="global-music-player"]',
    );
    if (!appShellContent || !playerElement) return null;
    const contentRect = appShellContent.getBoundingClientRect();
    const playerRect = playerElement.getBoundingClientRect();
    return {
      contentBottom: contentRect.bottom,
      playerTop: playerRect.top,
    };
  });

  expect(overlap).not.toBeNull();
  expect(
    overlap?.contentBottom ?? Number.POSITIVE_INFINITY,
    "the fixed sound bar must not cover the AppShell content at page bottom",
  ).toBeLessThanOrEqual((overlap?.playerTop ?? 0) + 0.5);
}

async function expectDialogInsideViewport(page: Page) {
  await expectInsideViewport(page.getByRole("dialog"), page);
}

async function captureEvidence(page: Page, testInfo: TestInfo, name: string) {
  const viewport = viewportFor(testInfo);
  await page.setViewportSize(viewport);
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  const screenshot = await page.screenshot({
    path: testInfo.outputPath(
      `story101-app-shell-${name}-${viewport.width}x${viewport.height}.png`,
    ),
    fullPage: false,
    animations: "disabled",
    caret: "hide",
    scale: "css",
  });
  expect({
    width: screenshot.readUInt32BE(16),
    height: screenshot.readUInt32BE(20),
  }).toEqual(viewport);
}

test.beforeEach(async ({ page }, testInfo) => {
  await page.setViewportSize(viewportFor(testInfo));
});

test("guest home keeps one quiet story101 portal and a labelled touch-sized auth sheet", async ({
  page,
}, testInfo) => {
  const scenario = await beginApiScenario(page, {
    soundGameId: SOUND_GAME_ID,
  });
  await mockAuth(page, false);
  await mockSoundPlaylist(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "story101" })).toBeVisible();
  await expect(page).toHaveTitle(/story101/);
  expect(await page.locator("body").innerText()).not.toMatch(/Story Life|AI驱动/);
  await expectSingleReadingSurface(page);
  await expect(page.locator('[data-slot="surface"][data-variant="raised"]')).toHaveCount(0);

  await captureEvidence(page, testInfo, "home");
  await expectBottomSoundReserve(page);
  await expectResponsiveSmoke(page);

  await page.setViewportSize(viewportFor(testInfo));
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: "注册", exact: true }).click();

  const authDialog = page.getByRole("dialog");
  const displayName = authDialog.getByRole("textbox", { name: "显示名称" });
  await expect(authDialog.getByRole("heading", { name: "创建账户" })).toBeVisible();
  await expect(page.locator('label[for="display-name-input"]')).toContainText("显示名称");
  await expect(displayName).toHaveAttribute(
    "aria-describedby",
    /display-name-input-description/,
  );
  await expect(page.locator("#display-name-input-description")).toHaveText(
    "将在首页这样称呼你",
  );
  await expectTouchTargetsAtLeast44(authDialog);
  await expectNoHorizontalOverflow(page);
  await captureEvidence(page, testInfo, "home-auth-sheet");

  await authDialog.getByRole("button", { name: "已有账户？登录" }).click();
  const privateId = authDialog.getByRole("textbox", { name: "私有密钥" });
  await expect(page.locator('label[for="private-id-input"]')).toContainText("私有密钥");
  await expect(privateId).toHaveAttribute(
    "aria-describedby",
    /private-id-input-description/,
  );
  await expect(page.locator("#private-id-input-description")).toHaveText(
    "使用注册时保存的唯一密钥",
  );
  await expectTouchTargetsAtLeast44(authDialog);
  await expectSingleReadingSurface(page);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/auth/me", count: 1 },
    {
      method: "GET",
      path: `/api/music/playlist/${SOUND_GAME_ID}`,
      count: 1,
    },
  ]);
});

test("saves renders a single reading list with subtle copy and protected sound reserve", async ({
  page,
}, testInfo) => {
  const scenario = await beginApiScenario(page, {
    authenticated: true,
    soundGameId: SOUND_GAME_ID,
  });
  await mockAuth(page, true);
  await mockGames(page, SAVED_GAMES);
  await mockSoundPlaylist(page);

  await page.goto("/saves");
  await expect(page.getByRole("heading", { level: 1, name: "存档" })).toBeVisible();
  await expect(page.getByRole("heading", { name: LONG_SAVE_NAME })).toBeVisible();
  await expect(page.getByRole("list", { name: "存档列表" })).toBeVisible();
  await expectSingleReadingSurface(page);
  expect(await page.locator("body").innerText()).not.toContain("Story Life");

  await expectUsesTextSubtleToken(page.getByText("不再保留这段人生").first());
  await captureEvidence(page, testInfo, "saves");
  await expectBottomSoundReserve(page);
  await expectResponsiveSmoke(page);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/auth/me", count: 1 },
    { method: "GET", path: "/api/games", count: 1 },
    {
      method: "GET",
      path: `/api/music/playlist/${SOUND_GAME_ID}`,
      count: 1,
    },
  ]);
});

test("saves distinguishes its empty state from a fetch failure and retries through the same path", async ({
  page,
}) => {
  const scenario = await beginApiScenario(page, { authenticated: true });
  await mockAuth(page, true);

  let gamesRequests = 0;
  await page.route(/\/api\/games(?:\?.*)?$/, async (route) => {
    if (
      route.request().method() !== "GET" ||
      !isExactFrontendApi(route.request().url(), "/api/games")
    ) {
      await route.fallback();
      return;
    }
    gamesRequests += 1;
    if (gamesRequests <= 3) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ message: "Temporary saves outage" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SAVED_GAMES),
    });
  });

  await page.goto("/saves");
  await expect(
    page.locator('[data-slot="feedback-notice"] [role="alert"]'),
  ).toContainText("未能载入存档", { timeout: 12_000 });
  await expect(page.getByText("还没有存档")).toHaveCount(0);
  await page.getByRole("button", { name: "重试载入存档" }).click();
  await expect(page.getByRole("heading", { name: LONG_SAVE_NAME })).toBeVisible();
  expect(gamesRequests).toBe(4);
  await expectSingleReadingSurface(page);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/auth/me", count: 1 },
    { method: "GET", path: "/api/games", count: 4 },
  ]);
});

test("saves shows the real empty state when the authenticated list is empty", async ({
  page,
}) => {
  const scenario = await beginApiScenario(page, { authenticated: true });
  await mockAuth(page, true);
  await mockGames(page, []);

  await page.goto("/saves");
  await expect(page.getByRole("heading", { name: "还没有存档" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始新游戏" })).toBeVisible();
  await expect(
    page.locator('[data-slot="feedback-notice"] [role="alert"]'),
  ).toHaveCount(0);
  await expectSingleReadingSurface(page);
  await expect(page.getByTestId("global-music-player")).toHaveCount(0);
  await expect(page.locator('[data-app-shell-reserve-spacer="bottom"]')).toHaveCount(0);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/auth/me", count: 1 },
    { method: "GET", path: "/api/games", count: 1 },
  ]);
});

test("save deletion traps focus, stays busy, reports failure, and permits one intentional retry", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: MOBILE_VIEWPORT.height });
  const scenario = await beginApiScenario(page, { authenticated: true });
  await mockAuth(page, true);
  await mockGames(page, SAVED_GAMES);

  let deleteRequests = 0;
  let releaseFirstDelete!: () => void;
  let notifyFirstDeleteStarted!: () => void;
  const firstDeleteGate = new Promise<void>((resolve) => {
    releaseFirstDelete = resolve;
  });
  const firstDeleteStarted = new Promise<void>((resolve) => {
    notifyFirstDeleteStarted = resolve;
  });

  await page.route(/\/api\/games\/41(?:\?.*)?$/, async (route) => {
    if (
      route.request().method() !== "DELETE" ||
      !isExactFrontendApi(route.request().url(), "/api/games/41")
    ) {
      await route.fallback();
      return;
    }
    deleteRequests += 1;
    if (deleteRequests === 1) {
      notifyFirstDeleteStarted();
      await firstDeleteGate;
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ message: "Controlled delete failure" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true }),
    });
  });

  await page.goto("/saves");
  await page
    .getByRole("button", {
      name: `删除存档“${LONG_SAVE_NAME}”（存档 41）`,
    })
    .click();

  const dialog = page.getByRole("dialog");
  const cancel = dialog.getByRole("button", { name: "取消" });
  const confirm = dialog.getByRole("button", { name: "删除", exact: true });
  await expect(dialog.getByRole("heading")).toHaveText(
    `删除存档“${LONG_SAVE_NAME}”？`,
  );
  await expect(dialog).toContainText("删除后无法恢复");
  await expect(cancel).toBeFocused();
  await expectDialogInsideViewport(page);
  await page.keyboard.press("Shift+Tab");
  await expect(confirm).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(cancel).toBeFocused();

  await confirm.evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });
  await firstDeleteStarted;
  await expect(dialog).toHaveAttribute("aria-busy", "true");
  await expect(cancel).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "正在删除" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  expect(deleteRequests).toBe(1);

  releaseFirstDelete();
  await expect(dialog.getByRole("alert")).toContainText(
    `未能删除存档“${LONG_SAVE_NAME}”，请重试。`,
  );
  await expect(dialog).toHaveAttribute("aria-busy", "false");
  await expect(dialog.getByRole("button", { name: "删除", exact: true })).toBeEnabled();

  for (const width of RESPONSIVE_WIDTHS) {
    await page.setViewportSize({ width, height: MOBILE_VIEWPORT.height });
    await expectNoHorizontalOverflow(page);
    await expectDialogInsideViewport(page);
    await expectTouchTargetsAtLeast44(dialog);
  }

  await dialog.getByRole("button", { name: "删除", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("status")).toContainText(
    `已删除存档“${LONG_SAVE_NAME}”。`,
  );
  await expect(page.getByRole("heading", { name: LONG_SAVE_NAME })).toHaveCount(0);
  expect(deleteRequests).toBe(2);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/auth/me", count: 1 },
    { method: "GET", path: "/api/games", count: 1 },
    { method: "DELETE", path: "/api/games/41", count: 2 },
  ]);
});

test("presets renders named and unnamed rows in one reading surface with subtle copy", async ({
  page,
}, testInfo) => {
  const scenario = await beginApiScenario(page, {
    soundGameId: SOUND_GAME_ID,
  });
  await mockPresets(page, PRESETS);
  await mockSoundPlaylist(page);

  await page.goto("/presets");
  await expect(page.getByRole("heading", { level: 1, name: "角色预设" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "远行者" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "未命名预设" })).toBeVisible();
  await expect(page.getByRole("list", { name: "角色预设列表" })).toBeVisible();
  await expectSingleReadingSurface(page);
  expect(await page.locator("body").innerText()).not.toContain("Story Life");

  await expectUsesTextSubtleToken(page.getByText(LONG_LIFE_VISION));
  await expectUsesTextSubtleToken(page.getByText("不再保留这份人物设定").first());
  await captureEvidence(page, testInfo, "presets");
  await expectBottomSoundReserve(page);
  await expectResponsiveSmoke(page);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/presets", count: 1 },
    {
      method: "GET",
      path: `/api/music/playlist/${SOUND_GAME_ID}`,
      count: 1,
    },
  ]);
});

test("presets distinguishes its empty state from a fetch failure and retries", async ({
  page,
}) => {
  const scenario = await beginApiScenario(page);
  let presetRequests = 0;

  await page.route(/\/api\/presets(?:\?.*)?$/, async (route) => {
    if (
      route.request().method() !== "GET" ||
      !isExactFrontendApi(route.request().url(), "/api/presets")
    ) {
      await route.fallback();
      return;
    }
    presetRequests += 1;
    if (presetRequests <= 3) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ message: "Temporary presets outage" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PRESETS),
    });
  });

  await page.goto("/presets");
  await expect(
    page.locator('[data-slot="feedback-notice"] [role="alert"]'),
  ).toContainText("未能载入角色预设", { timeout: 12_000 });
  await expect(page.getByText("还没有角色预设")).toHaveCount(0);
  await page.getByRole("button", { name: "重试载入角色预设" }).click();
  await expect(page.getByRole("heading", { name: "未命名预设" })).toBeVisible();
  expect(presetRequests).toBe(4);
  await expectSingleReadingSurface(page);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/presets", count: 4 },
  ]);
});

test("presets shows its real empty state when the list is empty", async ({ page }) => {
  const scenario = await beginApiScenario(page);
  await mockPresets(page, []);

  await page.goto("/presets");
  await expect(page.getByRole("heading", { name: "还没有角色预设" })).toBeVisible();
  await expect(page.getByRole("button", { name: "创建角色" })).toBeVisible();
  await expect(
    page.locator('[data-slot="feedback-notice"] [role="alert"]'),
  ).toHaveCount(0);
  await expectSingleReadingSurface(page);
  await expect(page.getByTestId("global-music-player")).toHaveCount(0);
  await expect(page.locator('[data-app-shell-reserve-spacer="bottom"]')).toHaveCount(0);

  await expectOnlyApiRequests(page, scenario, [
    { method: "GET", path: "/api/presets", count: 1 },
  ]);
});
