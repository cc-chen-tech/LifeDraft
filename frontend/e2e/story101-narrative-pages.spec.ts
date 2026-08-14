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
const FRONTEND_ORIGIN = `http://localhost:${process.env.E2E_FRONTEND_PORT ?? "3000"}`;
const CREATE_GAME_ID = 71001;
const ENDING_GAME_ID = 72001;
const SOUND_GAME_ID = 73001;

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

type StorageSeed = {
  local?: Record<string, string>;
  session?: Record<string, string>;
};

const ENDING_RESPONSE = {
  ending_type: "balanced",
  ending_name: "把真实的日子写到最后",
  summary:
    "许知夏没有把人生过成标准答案。她保留了好奇，也学会在每一次选择之后承担真实的结果。",
  achievements: {
    list: [
      {
        id: "honest_life",
        name: "如实生活",
        description: "在变化中没有丢掉自己的判断",
        rarity: "rare",
        unlocked_at_week: 12,
      },
    ],
  },
  life_review: {
    personality_labels: ["沉着的记录者", "关系守护者"],
    key_turning_points: [
      {
        week: 4,
        description: "在一次艰难取舍中决定忠于已经发生的生活。",
        impact_score: 0.82,
      },
    ],
    resource_curves: {},
    achievement_badge_wall: [
      {
        id: "honest_life",
        name: "如实生活",
        description: "在变化中没有丢掉自己的判断",
        rarity: "rare",
        unlocked_at_week: 12,
      },
    ],
    relationship_network: { nodes: [], edges: [] },
    life_motto: "把真实的日子，过成自己的答案。",
    play_duration_minutes: 42,
    total_decisions: 12,
    favorite_choice_type: "平衡",
  },
  final_stats: {
    energy: 86,
    mood: 91,
    knowledge: 76,
    relationships: {
      "这是一位名字很长需要在三百二十像素宽度下完整换行的故友": 82,
    },
  },
};

const SOUND_PLAYLIST = {
  game_id: SOUND_GAME_ID,
  current_song: {
    id: "narrative-pages-song",
    name: "页间夜航",
    artists: ["story101 配乐"],
    album: "人生草稿本",
    duration: 180,
    url: "https://example.invalid/narrative-pages-song.mp3",
    source: "netease",
  },
  queue: [],
  played_songs: [],
  is_playing: false,
  volume: 0.5,
  current_position_ms: 0,
};

function viewportFor(testInfo: TestInfo) {
  return testInfo.project.name === "Mobile Safari"
    ? MOBILE_VIEWPORT
    : DESKTOP_VIEWPORT;
}

function exactFrontendApi(requestUrl: string, path: string) {
  const url = new URL(requestUrl);
  return (
    url.origin === FRONTEND_ORIGIN &&
    url.pathname === path &&
    url.search === ""
  );
}

async function beginApiScenario(
  page: Page,
  storageSeed: StorageSeed = {},
): Promise<ApiScenario> {
  const scenario: ApiScenario = { requests: [], unexpected: [] };

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return;
    scenario.requests.push({
      method: request.method(),
      origin: url.origin,
      path: url.pathname,
      search: url.search,
    });
  });

  await page.addInitScript(({ local, session }) => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    for (const [key, value] of Object.entries(local ?? {})) {
      window.localStorage.setItem(key, value);
    }
    for (const [key, value] of Object.entries(session ?? {})) {
      window.sessionStorage.setItem(key, value);
    }
  }, storageSeed);

  // Registered first so later exact mocks win; every unowned API is blocked.
  await page.route(/\/api\/.*/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    scenario.unexpected.push(`${request.method()} ${url.href}`);
    await route.fulfill({
      status: 418,
      contentType: "application/json",
      body: JSON.stringify({ message: `Unexpected E2E API: ${url.href}` }),
    });
  });

  return scenario;
}

async function fulfillExactJson(
  page: Page,
  path: string,
  method: string,
  resolveBody: (body: Record<string, unknown>) => unknown,
) {
  await page.route(new RegExp(`${path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`), async (route) => {
    const request = route.request();
    if (
      request.method() !== method ||
      !exactFrontendApi(request.url(), path)
    ) {
      await route.fallback();
      return;
    }

    const rawBody = request.postData();
    const body = rawBody ? (JSON.parse(rawBody) as Record<string, unknown>) : {};
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(resolveBody(body)),
    });
  });
}

async function expectOnlyApiRequests(
  page: Page,
  scenario: ApiScenario,
  expected: Record<string, number>,
) {
  await page.waitForTimeout(100);
  expect(scenario.unexpected).toEqual([]);
  expect(
    scenario.requests.filter(
      ({ method, origin, path, search }) =>
        origin !== FRONTEND_ORIGIN ||
        (search !== "" && expected[`${method} ${path}${search}`] === undefined),
    ),
  ).toEqual([]);

  const actual = scenario.requests.reduce<Record<string, number>>(
    (counts, { method, path, search }) => {
      const signature = `${method} ${path}${search}`;
      counts[signature] = (counts[signature] ?? 0) + 1;
      return counts;
    },
    {},
  );
  expect(actual).toEqual(expected);
}

async function expectSingleReadingSurface(page: Page) {
  await expect(
    page.locator('[data-slot="surface"][data-variant="reading"]'),
  ).toHaveCount(1);
  await expect(page.locator('[data-slot="card"]')).toHaveCount(0);
  await expect(page.locator('[data-variant="raised"]')).toHaveCount(0);
}

async function expectNarrativeVisualContract(page: Page) {
  const content = page.locator('[data-slot="app-shell-content"]');
  await expect(content).not.toContainText(
    /Story Life|AI(?:正在|生成|驱动)|\b(?:CHAPTER|REVISION|LIFE FOLIO|CHARACTER)\b|PAGE\s+0?\d+/i,
  );

  const visualNoise = await content.locator("*").evaluateAll((elements) =>
    elements.flatMap((element) => {
      const className = element.getAttribute("class") ?? "";
      const forbidden = [
        "glow",
        "shadow-lg",
        "shadow-xl",
        "animate-pulse",
      ].filter((token) => className.includes(token));
      return forbidden.length > 0
        ? [{ tag: element.tagName, className, forbidden }]
        : [];
    }),
  );
  expect(visualNoise).toEqual([]);

  const undersizedText = await content
    .locator("p, span, label, button, a[href], input, textarea, li, dt, dd")
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const visible =
          rect.width > 0 &&
          rect.height > 0 &&
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          !element.closest('[inert], [aria-hidden="true"]');
        if (!visible) return [];

        const isInteractive = element.matches(
          "button, a[href], input, textarea",
        );
        const hasReadableContent =
          isInteractive ||
          Boolean(element.textContent?.trim()) ||
          Boolean(element.getAttribute("aria-label"));
        if (!hasReadableContent) return [];

        const fontSize = Number.parseFloat(style.fontSize);
        const minimum = isInteractive ? 14 : 12;
        if (fontSize >= minimum) return [];
        return [
          {
            label:
              element.getAttribute("aria-label") ||
              element.textContent?.trim().slice(0, 50) ||
              element.tagName,
            fontSize,
            minimum,
          },
        ];
      }),
    );
  expect(undersizedText).toEqual([]);
}

async function expectNoHorizontalOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}

async function expectTouchTargetsAtLeast44(root: Locator) {
  const undersized = await root
    .locator('button, input, textarea, a[href]')
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const visible =
          rect.width > 0 &&
          rect.height > 0 &&
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          !element.closest('[inert], [aria-hidden="true"]');
        if (!visible || (rect.width >= 44 && rect.height >= 44)) return [];
        return [
          {
            label:
              element.getAttribute("aria-label") ||
              element.textContent?.trim().slice(0, 50) ||
              element.tagName,
            width: rect.width,
            height: rect.height,
          },
        ];
      }),
    );
  expect(undersized).toEqual([]);
}

async function expectLiveRegionCount(page: Page, count: number) {
  await expect
    .poll(() =>
      page
        .locator(
          '[data-slot="app-shell"] [aria-live], [data-slot="app-shell"] [role="status"], [data-slot="app-shell"] [role="alert"]',
        )
        .count(),
    )
    .toBe(count);
}

async function expectResponsivePage(page: Page) {
  for (const width of RESPONSIVE_WIDTHS) {
    await page.setViewportSize({ width, height: MOBILE_VIEWPORT.height });
    await expectNoHorizontalOverflow(page);
    await expectSingleReadingSurface(page);
    await expectTouchTargetsAtLeast44(page.locator('[data-slot="app-shell"]'));
  }
}

async function screenshot(
  page: Page,
  testInfo: TestInfo,
  name: string,
) {
  const project = testInfo.project.name.replace(/\s+/g, "-").toLowerCase();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.addStyleTag({
    content: "nextjs-portal, next-route-announcer { display: none !important; }",
  });
  await page.screenshot({
    path: testInfo.outputPath(`${name}-${project}.png`),
    fullPage: true,
    animations: "disabled",
    scale: "css",
  });
}

async function installCreateFixture(page: Page) {
  const settingResponses: Record<string, Record<string, unknown>> = {
    gender: {
      gender: "女性",
      gender_description: "她习惯先观察，再作出自己的判断",
    },
    world: {
      world_description: "2026 年的上海，工作与个人创作同时向前推进。",
      technology_level: "当代",
      social_system: "现代城市社会",
      economy: "稳定而充满变化",
    },
    family: {
      family_description: "她成长在一个尊重选择、也珍惜相互照顾的家庭。",
      family_members: [
        { name: "许父", role: "父亲", personality: "温和而克制" },
      ],
      family_economy: "稳定",
    },
    traits: {
      traits_description: "她愿意为重要的事情保持耐心。",
      core_personality: "冷静而有好奇心",
      values: "诚实、自由",
      strengths: "观察与表达",
      weaknesses: "偶尔犹豫",
      life_attitude: "先理解，再行动",
    },
  };

  await fulfillExactJson(page, "/api/character/story-origin", "POST", () => ({
    revision: 1,
    start_date: "2026-08-13",
    starting_age: 26,
    era_description: "2020年代中期的现代都市",
    life_stage_description: "刚刚进入职业与生活都需要重新判断的阶段",
    world_context: "一个允许重新选择人生方向的世界",
  }));
  await fulfillExactJson(page, "/api/character/setting", "POST", (body) => {
    const type = String(body.setting_type ?? "");
    return settingResponses[type] ?? {};
  });
  await fulfillExactJson(page, "/api/character/relationship", "POST", (body) => {
    const index = Number(body.person_index ?? 0);
    return {
      name: ["苏敏", "周既明", "林渡"][index] ?? `人物${index + 1}`,
      role: ["朋友", "同事", "家人"][index] ?? "朋友",
      relationship: "愿意在重要选择前认真听她说完。",
    };
  });
  await fulfillExactJson(
    page,
    "/api/character/relationships-summary",
    "POST",
    () => ({ relationships_description: "她和身边的人保持真实而有边界的关系。" }),
  );
  await fulfillExactJson(page, "/api/games", "POST", () => ({
    game_id: CREATE_GAME_ID,
  }));
  const portraitImage = {
    image_id: 81001,
    image_url:
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='480'%3E%3Crect width='100%25' height='100%25' fill='%23171513'/%3E%3C/svg%3E",
    image_type: "character",
    entity_key: "player_main",
    entity_name: "许知夏",
  };
  await fulfillExactJson(
    page,
    "/api/images/character/generate-async",
    "POST",
    () => ({
      job_id: 81002,
      game_id: CREATE_GAME_ID,
      status: "queued",
      image_id: null,
      attempt_count: 0,
    }),
  );
  await page.route(
    new RegExp(`/api/images/character/jobs/latest\\?game_id=${CREATE_GAME_ID}$`),
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (
        request.method() !== "GET" ||
        url.origin !== FRONTEND_ORIGIN ||
        url.pathname !== "/api/images/character/jobs/latest" ||
        url.search !== `?game_id=${CREATE_GAME_ID}`
      ) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: 81002,
          game_id: CREATE_GAME_ID,
          status: "succeeded",
          image_id: portraitImage.image_id,
          attempt_count: 1,
        }),
      });
    },
  );
  await page.route(
    new RegExp(`/api/images/game/${CREATE_GAME_ID}\\?image_type=character$`),
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (
        request.method() !== "GET" ||
        url.origin !== FRONTEND_ORIGIN ||
        url.pathname !== `/api/images/game/${CREATE_GAME_ID}` ||
        url.search !== "?image_type=character"
      ) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ images: [portraitImage], total: 1 }),
      });
    },
  );
  await fulfillExactJson(page, "/api/presets", "POST", () => ({
    preset_id: 74001,
  }));
}

async function installSoundFixture(page: Page, gameId = SOUND_GAME_ID) {
  await fulfillExactJson(
    page,
    `/api/music/playlist/${gameId}`,
    "GET",
    () => ({ ...SOUND_PLAYLIST, game_id: gameId }),
  );
}

async function expectSoundDockClearance(page: Page) {
  const player = page.getByTestId("global-music-player");
  const spacer = page.locator('[data-app-shell-reserve-spacer="bottom"]');
  await expect(player).toBeVisible();
  await expect(player).toHaveAttribute("data-app-shell-reserve", "bottom");
  await expect(spacer).toHaveCount(1);
  await expect(page.getByTestId("collapsed-sound-status")).toHaveCSS(
    "font-size",
    "12px",
  );

  await page.evaluate(() =>
    window.scrollTo(0, document.documentElement.scrollHeight),
  );
  const geometry = await page.evaluate(() => {
    const content = document.querySelector<HTMLElement>(
      '[data-slot="app-shell-content"]',
    );
    const playerElement = document.querySelector<HTMLElement>(
      '[data-testid="global-music-player"]',
    );
    const spacerElement = document.querySelector<HTMLElement>(
      '[data-app-shell-reserve-spacer="bottom"]',
    );
    if (!content || !playerElement || !spacerElement) return null;
    return {
      contentBottom: content.getBoundingClientRect().bottom,
      playerTop: playerElement.getBoundingClientRect().top,
      playerBottom: playerElement.getBoundingClientRect().bottom,
      viewportHeight: window.innerHeight,
      spacerPosition: getComputedStyle(spacerElement).position,
    };
  });
  expect(geometry).not.toBeNull();
  if (geometry) {
    expect(geometry.spacerPosition).toBe("static");
    expect(geometry.contentBottom).toBeLessThanOrEqual(geometry.playerTop + 0.5);
    expect(geometry.playerBottom).toBeLessThanOrEqual(
      geometry.viewportHeight + 0.5,
    );
  }
}

async function waitForGeneratedStep(page: Page, label: string) {
  await expect(
    page.locator('[data-slot="page-edge-bookmark"]'),
  ).toContainText(label);
  await expect(page.getByText("刚刚生成")).toBeVisible();
}

test("the create reading axis reserves the persistent sound dock", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(viewportFor(testInfo));
  const scenario = await beginApiScenario(page, {
    local: { gameId: String(SOUND_GAME_ID) },
  });
  await installSoundFixture(page);

  await page.goto("/create");
  await expectSoundDockClearance(page);

  await expectOnlyApiRequests(page, scenario, {
    [`GET /api/music/playlist/${SOUND_GAME_ID}`]: 1,
  });
});

test("create uses the real four-step reading flow through completion", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(viewportFor(testInfo));
  await page.emulateMedia({ reducedMotion: "reduce" });
  const scenario = await beginApiScenario(page, {
    local: { gameId: String(SOUND_GAME_ID) },
  });
  await installCreateFixture(page);
  await installSoundFixture(page);

  await page.goto("/create");

  await expect(page.getByRole("heading", { name: "故事起点" })).toBeVisible();
  await expect(page.getByText("story101", { exact: true })).toBeVisible();
  await expectSingleReadingSurface(page);
  await expect(page.locator('[data-slot="page-transition"]')).toHaveCSS(
    "animation-name",
    "none",
  );
  await expectLiveRegionCount(page, 0);
  await expectTouchTargetsAtLeast44(page.locator('[data-slot="app-shell"]'));
  await expectNarrativeVisualContract(page);
  await screenshot(page, testInfo, "create-initial");

  // Fill optional vision first: entering the required name last starts one origin request.
  await page.getByRole("textbox", { name: "人生愿景（可选）" }).fill(
    "在城市里保留创作、关系与重新选择的自由。",
  );
  await page.getByRole("textbox", { name: "角色姓名" }).fill("许知夏");

  await waitForGeneratedStep(page, "故事起点");
  await screenshot(page, testInfo, "create-generated");
  await page.getByRole("button", { name: "下一步" }).click();

  for (const label of ["性别", "世界观"]) {
    await waitForGeneratedStep(page, label);
    await page.getByRole("button", { name: "下一步" }).click();
  }

  await expect(page.getByRole("heading", { name: "人物形象" })).toBeVisible();
  await page.getByRole("button", { name: /继续生成角色/ }).click();
  await expect(
    page.getByRole("heading", { name: "角色设定完成" }),
  ).toBeVisible({ timeout: 15_000 });
  await expectSingleReadingSurface(page);
  await expect(page.getByRole("button", { name: "开始游戏" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "保存为预设" })).toBeVisible();
  await expectTouchTargetsAtLeast44(page.locator('[data-slot="app-shell"]'));
  await expectNarrativeVisualContract(page);
  await screenshot(page, testInfo, "create-complete");

  await page.getByRole("button", { name: "保存为预设" }).click();
  const presetDialog = page.getByRole("dialog", { name: "保存角色预设" });
  await expect(presetDialog).toBeVisible();
  await expect(page.getByRole("textbox", { name: "预设名称" })).toBeFocused();
  await expectTouchTargetsAtLeast44(presetDialog);
  await expect
    .poll(() =>
      presetDialog.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return (
          rect.left >= 0 &&
          rect.top >= 0 &&
          rect.right <= window.innerWidth &&
          rect.bottom <= window.innerHeight
        );
      }),
    )
    .toBe(true);
  const dialogBounds = await presetDialog.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      left: rect.left,
      right: rect.right,
      top: rect.top,
      bottom: rect.bottom,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      position: getComputedStyle(element).position,
    };
  });
  expect(dialogBounds.position).toBe("fixed");
  expect(dialogBounds.left).toBeGreaterThanOrEqual(0);
  expect(dialogBounds.top).toBeGreaterThanOrEqual(0);
  expect(dialogBounds.right).toBeLessThanOrEqual(dialogBounds.viewportWidth);
  expect(dialogBounds.bottom).toBeLessThanOrEqual(dialogBounds.viewportHeight);

  await page
    .getByRole("textbox", { name: "预设名称" })
    .fill("许知夏的城市人生");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.locator('[data-slot="page-transition"]')).toHaveCSS(
    "animation-name",
    "story101-page-enter",
  );
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: "确认保存" }).click();
  await expect(presetDialog).toBeHidden();
  const savedStatus = page.getByRole("status").filter({
    hasText: "预设保存成功",
  });
  await expect(savedStatus).toBeVisible();
  const toastNotice = page
    .locator('[data-slot="feedback-notice"]')
    .filter({ hasText: "预设保存成功" });
  await expect(toastNotice).toHaveCSS("position", "fixed");
  expect(
    await toastNotice.evaluate(
      (element) => element.closest('[data-slot="page-transition"]') === null,
    ),
  ).toBe(true);
  const toastGeometry = await toastNotice.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const player = document.querySelector<HTMLElement>(
      '[data-testid="global-music-player"]',
    );
    return {
      top: rect.top,
      bottom: rect.bottom,
      viewportHeight: window.innerHeight,
      playerTop: player?.getBoundingClientRect().top ?? null,
      bottomProperty: getComputedStyle(element).bottom,
    };
  });
  expect(toastGeometry.top).toBeGreaterThanOrEqual(0);
  expect(toastGeometry.bottom).toBeLessThanOrEqual(
    toastGeometry.viewportHeight + 0.5,
  );
  expect(Number.parseFloat(toastGeometry.bottomProperty)).toBeGreaterThan(0);
  expect(toastGeometry.playerTop).not.toBeNull();
  if (toastGeometry.playerTop !== null) {
    expect(toastGeometry.bottom).toBeLessThanOrEqual(
      toastGeometry.playerTop + 0.5,
    );
  }
  await expectLiveRegionCount(page, 1);

  await expectResponsivePage(page);

  await expectOnlyApiRequests(page, scenario, {
    "POST /api/character/story-origin": 1,
    "POST /api/character/setting": 4,
    "POST /api/character/relationship": 3,
    "POST /api/character/relationships-summary": 1,
    "POST /api/games": 1,
    "POST /api/images/character/generate-async": 1,
    [`GET /api/images/character/jobs/latest?game_id=${CREATE_GAME_ID}`]: 1,
    [`GET /api/images/game/${CREATE_GAME_ID}?image_type=character`]: 1,
    "POST /api/presets": 1,
    [`GET /api/music/playlist/${SOUND_GAME_ID}`]: 1,
  });
});

async function installOpeningStreamFixture(page: Page) {
  await page.addInitScript(() => {
    type StreamFixture = {
      requestCount: number;
      controllers: ReadableStreamDefaultController<Uint8Array>[];
      enqueue: (index: number, event: string, data: unknown) => void;
    };

    const fixture: StreamFixture = {
      requestCount: 0,
      controllers: [],
      enqueue(index, event, data) {
        const controller = fixture.controllers[index];
        if (!controller) throw new Error(`Opening stream ${index} is not ready`);
        const frame = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
        controller.enqueue(new TextEncoder().encode(frame));
      },
    };

    const target = window as Window & {
      __TEST_DATA__?: unknown;
      __OPENING_STREAM_FIXTURE__?: StreamFixture;
    };
    target.__TEST_DATA__ = {
      playerName: "许知夏",
      lifeVision: "在城市里保留创作与重新选择的自由。",
      characterSettings: { era: { era_name: "现代", year: 2026 } },
    };
    target.__OPENING_STREAM_FIXTURE__ = fixture;

    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const url = new URL(rawUrl, window.location.origin);
      const method = init?.method ?? (input instanceof Request ? input.method : "GET");
      if (
        url.origin === window.location.origin &&
        url.pathname === "/api/character/opening-story" &&
        url.search === "" &&
        method === "POST"
      ) {
        fixture.requestCount += 1;
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            fixture.controllers.push(controller);
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }
      return originalFetch(input, init);
    };
  });
}

async function openingRequestCount(page: Page) {
  return page.evaluate(() => {
    const target = window as Window & {
      __OPENING_STREAM_FIXTURE__?: { requestCount: number };
    };
    return target.__OPENING_STREAM_FIXTURE__?.requestCount ?? 0;
  });
}

async function enqueueOpeningFrame(
  page: Page,
  index: number,
  event: string,
  data: unknown,
) {
  await page.evaluate(
    ({ streamIndex, streamEvent, streamData }) => {
      const target = window as Window & {
        __OPENING_STREAM_FIXTURE__?: {
          enqueue: (index: number, event: string, data: unknown) => void;
        };
      };
      target.__OPENING_STREAM_FIXTURE__?.enqueue(
        streamIndex,
        streamEvent,
        streamData,
      );
    },
    { streamIndex: index, streamEvent: event, streamData: data },
  );
}

test("opening stays on one calm reading axis across retry and completion", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(viewportFor(testInfo));
  await page.emulateMedia({ reducedMotion: "reduce" });
  const scenario = await beginApiScenario(page, {
    local: { gameId: String(SOUND_GAME_ID) },
  });
  await installOpeningStreamFixture(page);
  await installSoundFixture(page);

  await page.goto("/story/opening");
  await expect.poll(() => openingRequestCount(page)).toBe(1);
  await expect(page.getByTestId("narrative-loading-screen")).toBeVisible();
  await expect(page.locator('[data-slot="surface"]')).toHaveCount(0);
  await expectLiveRegionCount(page, 1);

  await enqueueOpeningFrame(page, 0, "story", "旧稿开场。风从窗边经过。");
  await expect(page.getByText("旧稿开场。风从窗边经过。")).toBeVisible();
  await expect(page.getByTestId("narrative-loading-screen")).toHaveCount(0);
  await expect(page.getByTestId("narrative-loading-inline")).toBeVisible();
  await expect(page.locator(".typewriter-cursor")).toHaveCount(0);
  await expectSingleReadingSurface(page);
  await expectLiveRegionCount(page, 1);
  await expectNarrativeVisualContract(page);
  await screenshot(page, testInfo, "opening-partial");

  let mainFrameNavigations = 0;
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) mainFrameNavigations += 1;
  });
  await enqueueOpeningFrame(page, 0, "error", { message: "连接暂时中断" });
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  await expect(page.getByText("旧稿开场。风从窗边经过。")).toBeVisible();
  await expect(page.getByTestId("narrative-loading-screen")).toHaveCount(0);
  await expectLiveRegionCount(page, 1);
  await screenshot(page, testInfo, "opening-failed");

  await page.getByRole("button", { name: "重试" }).click();
  await expect.poll(() => openingRequestCount(page)).toBe(2);
  await expect(page.getByText("旧稿开场。风从窗边经过。")).toBeVisible();
  await enqueueOpeningFrame(page, 1, "story", "新稿开场。");
  await expect(page.getByText("新稿开场。")).toBeVisible();
  await expect(page.getByText("旧稿开场。风从窗边经过。")).toHaveCount(0);

  const finalStory = "新稿开场。她推开门，故事从这一天真正开始。";
  await enqueueOpeningFrame(page, 1, "complete", { full_story: finalStory });
  await expect(page.getByTestId("narrative-loading-inline")).toHaveCount(0);
  const start = page.getByRole("button", { name: "开始我的人生" });
  await expect(start).toBeEnabled({ timeout: 10_000 });
  await expect(page.getByText(finalStory)).toBeVisible();
  await expectLiveRegionCount(page, 0);
  await expectSingleReadingSurface(page);
  await expectTouchTargetsAtLeast44(page.locator('[data-slot="app-shell"]'));
  await expect(page.locator('[data-slot="page-transition"]')).toHaveCSS(
    "animation-name",
    "none",
  );
  expect(mainFrameNavigations).toBe(0);
  await screenshot(page, testInfo, "opening-complete");
  await expectSoundDockClearance(page);
  await expectResponsivePage(page);
  await expectOnlyApiRequests(page, scenario, {
    [`GET /api/music/playlist/${SOUND_GAME_ID}`]: 1,
  });
});

async function installEndingFixture(page: Page) {
  let attempts = 0;
  const path = `/api/games/${ENDING_GAME_ID}/ending`;
  await page.route(new RegExp(`${path}$`), async (route) => {
    const request = route.request();
    if (
      request.method() !== "GET" ||
      !exactFrontendApi(request.url(), path)
    ) {
      await route.fallback();
      return;
    }

    attempts += 1;
    await route.fulfill({
      status: attempts === 1 ? 400 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        attempts === 1
          ? { message: "结局尚未准备好" }
          : ENDING_RESPONSE,
      ),
    });
  });
}

test("ending failure retries into only the sections present in real data", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(viewportFor(testInfo));
  await page.emulateMedia({ reducedMotion: "reduce" });
  const scenario = await beginApiScenario(page, {
    local: {
      gameId: String(ENDING_GAME_ID),
      "game-store": JSON.stringify({
        state: {
          gameId: ENDING_GAME_ID,
          playerState: { player_name: "许知夏" },
        },
        version: 1,
      }),
    },
  });
  await installEndingFixture(page);
  await installSoundFixture(page, ENDING_GAME_ID);

  await page.goto("/ending");
  await expect(page.getByTestId("narrative-loading-screen")).toBeVisible();
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  await expect(page.locator('[data-slot="surface"]')).toHaveCount(0);
  await expectLiveRegionCount(page, 1);
  await screenshot(page, testInfo, "ending-failed");

  await page.getByRole("button", { name: "重试" }).click();
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: ENDING_RESPONSE.ending_name,
    }),
  ).toBeVisible();
  await expectSingleReadingSurface(page);
  await expectNarrativeVisualContract(page);
  const index = page.getByRole("navigation", { name: "本页内容" });
  await expect(index.getByRole("link")).toHaveCount(4);
  await expect(index.getByRole("link", { name: "终章正文" })).toBeVisible();
  await expect(index.getByRole("link", { name: "人际关系" })).toBeVisible();
  await expect(index.getByRole("link", { name: "人生成就" })).toBeVisible();
  await expect(index.getByRole("link", { name: "人生回顾" })).toBeVisible();
  await screenshot(page, testInfo, "ending-ready");

  const review = page.getByRole("button", { name: "查看人生回顾" });
  await expect(review).toHaveAttribute("aria-expanded", "false");
  await review.click();
  await expect(
    page.getByRole("button", { name: "隐藏人生回顾" }),
  ).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByTestId("life-review-card")).toBeVisible();
  await expect(page.locator('[data-slot="card"]')).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
  await expectTouchTargetsAtLeast44(page.locator('[data-slot="app-shell"]'));
  await expect(page.locator('[data-slot="page-transition"]')).toHaveCSS(
    "animation-name",
    "none",
  );
  await expectSoundDockClearance(page);
  await expectResponsivePage(page);

  await expectOnlyApiRequests(page, scenario, {
    [`GET /api/games/${ENDING_GAME_ID}/ending`]: 2,
    [`GET /api/music/playlist/${ENDING_GAME_ID}`]: 1,
  });
});
