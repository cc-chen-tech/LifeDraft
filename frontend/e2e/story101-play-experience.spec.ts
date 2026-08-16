import {
  expect,
  test,
  type Frame,
  type Locator,
  type Page,
  type Request,
  type TestInfo,
} from "@playwright/test";

const PLAY_STATES = [
  "options",
  "choosing",
  "result",
  "summary",
  "history",
  "reconnecting",
  "polling",
  "failed",
] as const;

type PlayFixtureState = (typeof PLAY_STATES)[number];

const VISUAL_VIEWPORTS = [
  { label: "1440x900", width: 1440, height: 900 },
  { label: "390x844", width: 390, height: 844 },
] as const;
const DAILY_PROGRESS_VIEWPORTS = [
  { label: "1280x900", width: 1280, height: 900 },
  { label: "390x844", width: 390, height: 844 },
] as const;
const OVERFLOW_WIDTHS = [320, 375] as const;

const CURRENT_STORY =
  "雨停以后，林见微沿着旧城河走到档案馆。值夜人把一封没有署名的信推到灯下，她认出纸角那道熟悉的折痕。";
const CHOOSING_STORY =
  "林见微拆开信封，先读到一句被水迹晕开的提醒。她已经作出选择，新的故事仍在继续。";
const RESULT_STORY =
  "林见微没有立刻追问来信的人。她先核对档案编号，在闭馆钟声响起前找到了一条可以继续追查的记录。";
const SUMMARY_TEXT =
  "这一周，她学会把急于求证的冲动放慢一步，也保住了与旧友之间来之不易的信任。";
const HISTORY_STORY =
  "第三周的周中，林见微在渡口收下旧友交来的账册，并答应在天亮前不向任何人透露其中的名字。";
const RECOVERY_STORY =
  "档案馆的灯还亮着，已经抵达的正文不会因为连接变化而消失。";

const OPTION_TEXTS = [
  "先核对信封上的旧邮戳，再询问值夜人是谁送来了这封信。",
  "把信暂时收好，去河边寻找纸上提到的那盏蓝色路灯。",
  "联系多年未见的旧友，请她一起判断这条线索是否值得继续追查。",
] as const;

const FORBIDDEN_FAKE_METADATA =
  /Story Life|AI(?:正在|生成|驱动)|\b(?:CHAPTER|REVISION|LIFE FOLIO|CHARACTER)\b|PAGE\s+0?\d+/i;

const fixture = (page: Page) => page.getByTestId("play-experience-fixture");
const readingSurface = (page: Page) =>
  fixture(page).locator('[data-slot="surface"][data-variant="reading"]');
const mobileDock = (page: Page) =>
  fixture(page).locator('[data-slot="mobile-action-dock"]');

function fixtureUrl(state: PlayFixtureState) {
  return `/e2e-regression?playState=${state}`;
}

async function openState(page: Page, state: PlayFixtureState) {
  await page.goto(fixtureUrl(state));
  await expect(fixture(page)).toBeVisible();
  await expect(fixture(page)).toHaveAttribute("data-play-state", state);
}

function observeApiRequests(page: Page) {
  const requests: string[] = [];
  const listener = (request: Request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) {
      requests.push(`${request.method()} ${url.pathname}${url.search}`);
    }
  };
  page.on("request", listener);
  return {
    requests,
    stop: () => page.off("request", listener),
  };
}

async function expectNoHorizontalOverflow(page: Page) {
  const geometry = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    document: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(
    geometry.body,
    "body must not overflow horizontally",
  ).toBeLessThanOrEqual(geometry.viewport);
  expect(
    geometry.document,
    "documentElement must not overflow horizontally",
  ).toBeLessThanOrEqual(geometry.viewport);
}

async function expectSingleReadingSurface(page: Page) {
  await expect(fixture(page)).toHaveAttribute("data-slot", "page-transition");
  await expect(fixture(page)).toHaveClass(/\bplay-reading-axis\b/);
  await expect(readingSurface(page)).toHaveCount(1);
  await expect(fixture(page).locator('[data-slot="play-tools"]')).toHaveCount(1);
  await expect(mobileDock(page)).toHaveCount(1);
  await expect(fixture(page).locator('[data-slot="card"]')).toHaveCount(0);
  await expect(fixture(page).locator('[data-variant="raised"]')).toHaveCount(0);
}

async function expectNoCardGlowOrFakeMetadata(page: Page) {
  await expect(fixture(page)).not.toContainText(FORBIDDEN_FAKE_METADATA);

  const visualNoise = await readingSurface(page)
    .locator("*")
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        const className = element.getAttribute("class") ?? "";
        const style = getComputedStyle(element);
        const forbiddenClassTokens = className
          .split(/\s+/)
          .filter((token) => /glow|animate-pulse/i.test(token));
        const shadowLayers = (() => {
          if (style.boxShadow === "none") return [];
          const layers: string[] = [];
          let depth = 0;
          let start = 0;
          for (let index = 0; index < style.boxShadow.length; index += 1) {
            const character = style.boxShadow[index];
            if (character === "(") depth += 1;
            if (character === ")") depth -= 1;
            if (character === "," && depth === 0) {
              layers.push(style.boxShadow.slice(start, index).trim());
              start = index + 1;
            }
          }
          layers.push(style.boxShadow.slice(start).trim());
          return layers;
        })();
        const hasReadingShadow = shadowLayers.some((layer) => {
          if (/\btransparent\b/i.test(layer)) return false;
          const color = layer.match(/(?:rgba?|hsla?|color)\([^)]*\)/i)?.[0];
          if (!color) return true;
          const slashAlpha = color.match(/\/\s*([0-9.]+)%?\s*\)$/)?.[1];
          if (slashAlpha !== undefined) {
            return Number.parseFloat(slashAlpha) !== 0;
          }
          if (/^(?:rgba|hsla)\(/i.test(color)) {
            const commaAlpha = color.match(/,\s*([0-9.]+)%?\s*\)$/)?.[1];
            if (commaAlpha !== undefined) {
              return Number.parseFloat(commaAlpha) !== 0;
            }
          }
          return true;
        });
        const hasDropShadow = style.filter.includes("drop-shadow");
        if (
          forbiddenClassTokens.length === 0 &&
          !hasReadingShadow &&
          !hasDropShadow
        ) {
          return [];
        }
        return [
          {
            tag: element.tagName,
            className,
            forbiddenClassTokens,
            boxShadow: style.boxShadow,
            filter: style.filter,
          },
        ];
      }),
    );

  expect(
    visualNoise,
    "the reading surface must not contain card glow, pulse, or shadow effects",
  ).toEqual([]);
}

async function expectReadableTextSizes(page: Page) {
  const undersized = await fixture(page)
    .locator(
      "h1, h2, h3, p, li, dt, dd, label, button, a[href], input, textarea",
    )
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

        const interactive = element.matches(
          'button, a[href], input, textarea, [role="button"]',
        );
        const minimum = interactive ? 14 : 12;
        const fontSize = Number.parseFloat(style.fontSize);
        return fontSize >= minimum
          ? []
          : [
              {
                label:
                  element.getAttribute("aria-label") ||
                  element.textContent?.trim().slice(0, 60) ||
                  element.tagName,
                fontSize,
                minimum,
              },
            ];
      }),
    );
  expect(undersized, "visible copy must remain readable").toEqual([]);

  const narrativeMetrics = await fixture(page)
    .locator('[data-slot="play-story"] .prose-story p')
    .evaluateAll((paragraphs) =>
      paragraphs.flatMap((paragraph) => {
        const rect = paragraph.getBoundingClientRect();
        const style = getComputedStyle(paragraph);
        if (rect.width === 0 || rect.height === 0) return [];
        const fontSize = Number.parseFloat(style.fontSize);
        const lineHeight = Number.parseFloat(style.lineHeight);
        return fontSize >= 16 && lineHeight / fontSize >= 1.6
          ? []
          : [
              {
                text: paragraph.textContent?.trim().slice(0, 60),
                fontSize,
                lineHeight,
              },
            ];
      }),
    );
  expect(
    narrativeMetrics,
    "narrative prose must be at least 16px with a 1.6 line-height ratio",
  ).toEqual([]);
}

async function expectTouchTargetsAtLeast44(root: Locator) {
  const undersized = await root
    .locator(
      'button, input, textarea, select, summary, a[href], [role="button"]',
    )
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        const rect = element.getBoundingClientRect();
        let current: Element | null = element;
        let reachable = true;
        while (current) {
          const style = getComputedStyle(current);
          if (
            current.hasAttribute("inert") ||
            current.getAttribute("aria-hidden") === "true" ||
            style.display === "none" ||
            style.visibility === "hidden" ||
            style.pointerEvents === "none"
          ) {
            reachable = false;
            break;
          }
          current = current.parentElement;
        }
        if (!reachable || rect.width === 0 || rect.height === 0) return [];

        const htmlElement = element as HTMLElement;
        const width = htmlElement.offsetWidth;
        const height = htmlElement.offsetHeight;
        return width >= 44 && height >= 44
          ? []
          : [
              {
                label:
                  element.getAttribute("aria-label") ||
                  element.textContent?.trim().slice(0, 60) ||
                  element.tagName,
                width,
                height,
              },
            ];
      }),
    );
  expect(
    undersized,
    "every visible interactive target must be at least 44px by 44px",
  ).toEqual([]);
}

async function expectFixedLayerClearance(
  page: Page,
  anchor: Locator,
  requireFixedLayer = false,
) {
  await anchor.scrollIntoViewIfNeeded();

  const geometry = await page.evaluate(() => {
    const isVisible = (element: Element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        !element.closest('[inert], [aria-hidden="true"]')
      );
    };
    const fixedLayers = Array.from(document.body.querySelectorAll("*"))
      .filter((element) => {
        if (!isVisible(element)) return false;
        const position = getComputedStyle(element).position;
        if (position !== "fixed" && position !== "sticky") return false;
        let parent = element.parentElement;
        while (parent) {
          const parentPosition = getComputedStyle(parent).position;
          if (parentPosition === "fixed" || parentPosition === "sticky") {
            return false;
          }
          parent = parent.parentElement;
        }
        return true;
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          label:
            element.getAttribute("data-slot") ||
            element.getAttribute("data-testid") ||
            element.getAttribute("aria-label") ||
            element.tagName,
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
        };
      });

    return {
      fixedLayers,
      viewport: { width: window.innerWidth, height: window.innerHeight },
    };
  });

  if (requireFixedLayer) {
    expect(
      geometry.fixedLayers.length,
      "mobile acceptance must exercise at least one visible fixed layer",
    ).toBeGreaterThan(0);
  }

  for (const layer of geometry.fixedLayers) {
    expect(
      layer.left,
      `${layer.label} must stay inside the left edge`,
    ).toBeGreaterThanOrEqual(-0.5);
    expect(
      layer.top,
      `${layer.label} must stay inside the top edge`,
    ).toBeGreaterThanOrEqual(-0.5);
    expect(
      layer.right,
      `${layer.label} must stay inside the right edge`,
    ).toBeLessThanOrEqual(geometry.viewport.width + 0.5);
    expect(
      layer.bottom,
      `${layer.label} must stay inside the bottom edge`,
    ).toBeLessThanOrEqual(geometry.viewport.height + 0.5);
  }

  for (
    let leftIndex = 0;
    leftIndex < geometry.fixedLayers.length;
    leftIndex += 1
  ) {
    for (
      let rightIndex = leftIndex + 1;
      rightIndex < geometry.fixedLayers.length;
      rightIndex += 1
    ) {
      const left = geometry.fixedLayers[leftIndex];
      const right = geometry.fixedLayers[rightIndex];
      const overlapWidth =
        Math.min(left.right, right.right) - Math.max(left.left, right.left);
      const overlapHeight =
        Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top);
      expect(
        overlapWidth > 0.5 && overlapHeight > 0.5
          ? `${left.label} overlaps ${right.label}`
          : null,
      ).toBeNull();
    }
  }

  const anchorBox = await anchor.boundingBox();
  expect(anchorBox).not.toBeNull();
  if (!anchorBox) return;

  for (const layer of geometry.fixedLayers) {
    const overlapWidth =
      Math.min(anchorBox.x + anchorBox.width, layer.right) -
      Math.max(anchorBox.x, layer.left);
    const overlapHeight =
      Math.min(anchorBox.y + anchorBox.height, layer.bottom) -
      Math.max(anchorBox.y, layer.top);
    expect(
      overlapWidth > 0.5 && overlapHeight > 0.5
        ? `acceptance anchor overlaps ${layer.label}`
        : null,
    ).toBeNull();
  }

  const hitTarget = await anchor.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(
      rect.left + rect.width / 2,
      rect.top + rect.height / 2,
    );
    return hit === element || Boolean(hit && element.contains(hit));
  });
  expect(hitTarget, "the state action or status must not be covered").toBe(
    true,
  );
}

async function expectSharedVisualContract(page: Page, state: PlayFixtureState) {
  await expect(fixture(page)).toHaveAttribute("data-play-state", state);
  await expectSingleReadingSurface(page);
  await expectNoCardGlowOrFakeMetadata(page);
  await expectReadableTextSizes(page);
  await expectTouchTargetsAtLeast44(fixture(page));
  await expectNoHorizontalOverflow(page);
}

function acceptanceAnchor(page: Page, state: PlayFixtureState): Locator {
  const root = fixture(page);
  switch (state) {
    case "options":
      return root.getByRole("button", { name: `选择 3：${OPTION_TEXTS[2]}` });
    case "choosing":
      return root.getByTestId("narrative-loading-inline");
    case "result":
      return root.getByRole("button", { name: "进入周中" });
    case "summary":
      return root.getByRole("button", { name: "继续人生旅途" });
    case "history":
      return root.getByRole("button", { name: "返回当前" });
    case "reconnecting":
    case "polling":
      return root.getByRole("button", { name: "重新连接" });
    case "failed":
      return root.getByRole("button", { name: "重试" });
  }
}

async function expectStateSemantics(page: Page, state: PlayFixtureState) {
  const root = fixture(page);
  const story = root.locator('[data-slot="play-story"]');
  await expect(story).toBeVisible();

  switch (state) {
    case "options": {
      await expect(story).toContainText(CURRENT_STORY);
      const choices = root.getByTestId("play-options");
      await expect(choices).toBeVisible();
      await expect(choices.locator('[data-slot="choice-branch-row"]')).toHaveCount(3);
      await expect(
        choices.getByRole("textbox", { name: "写下自己的选择" }),
      ).toBeVisible();
      for (const [index, option] of OPTION_TEXTS.entries()) {
        await expect(
          choices.getByRole("button", {
            name: `选择 ${index + 1}：${option}`,
          }),
        ).toBeVisible();
      }
      await expect(
        choices.getByRole("button", { name: "提交自定义选择" }),
      ).toBeVisible();
      await expect(root.getByTestId("narrative-loading-inline")).toHaveCount(0);
      break;
    }
    case "choosing":
      await expect(story).toContainText(CHOOSING_STORY);
      await expect(root.getByTestId("play-options")).toHaveCount(0);
      await expect(root.getByTestId("narrative-loading-inline")).toContainText(
        "正在继续推演",
      );
      await expect(root.getByTestId("chat-bar-launcher")).toHaveCount(0);
      break;
    case "result":
      await expect(story).toContainText(RESULT_STORY);
      await expect(
        root.getByRole("heading", {
          name: "刚才的选择，留下的变化",
        }),
      ).toBeVisible();
      await expect(root.locator('[data-slot="feedback-notice"]')).toHaveCount(
        0,
      );
      await expect(
        root.getByRole("button", { name: "进入周中" }),
      ).toBeVisible();
      await expect(root.getByTestId("play-options")).toHaveCount(0);
      break;
    case "summary":
      await expect(story).toContainText(RESULT_STORY);
      await expect(root.getByRole("heading", { name: "周总结" })).toBeVisible();
      await expect(root.getByText(SUMMARY_TEXT, { exact: true })).toBeVisible();
      await expect(
        root.getByRole("button", { name: "继续人生旅途" }),
      ).toBeVisible();
      await expect(root.getByTestId("play-options")).toHaveCount(0);
      break;
    case "history":
      await expect(story).toContainText(HISTORY_STORY);
      await expect(
        root.getByText("历史回顾 · 只读", { exact: true }),
      ).toBeVisible();
      await expect(
        root.getByText("正在查看历史轮次（只读模式）", { exact: true }),
      ).toHaveCount(0);
      await expect(
        root.getByRole("button", { name: "返回当前" }),
      ).toBeVisible();
      await expect(root.getByTestId("play-options")).toHaveCount(0);
      await expect(root.getByTestId("chat-bar-launcher")).toHaveCount(0);
      await expect(root).not.toContainText(CURRENT_STORY);
      break;
    case "reconnecting":
    case "polling":
      await expect(story).toContainText(RECOVERY_STORY);
      await expect(root.getByTestId("narrative-loading-inline")).toBeVisible();
      await expect(
        root.getByRole("button", { name: "重新连接" }),
      ).toBeVisible();
      await expect(root.getByRole("button", { name: "重试" })).toHaveCount(0);
      await expect(root.getByTestId("play-options")).toHaveCount(0);
      await expect(root.getByTestId("chat-bar-launcher")).toHaveCount(0);
      break;
    case "failed":
      await expect(story).toContainText(RECOVERY_STORY);
      await expect(root.getByTestId("narrative-loading-inline")).toBeVisible();
      await expect(root.getByRole("button", { name: "重试" })).toBeVisible();
      await expect(root.getByRole("button", { name: "重新连接" })).toHaveCount(
        0,
      );
      await expect(root.getByTestId("play-options")).toHaveCount(0);
      await expect(root.getByTestId("chat-bar-launcher")).toHaveCount(0);
      break;
  }
}

async function captureScreenshot(
  page: Page,
  testInfo: TestInfo,
  state: PlayFixtureState,
  viewportLabel: string,
) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.addStyleTag({
    content:
      "nextjs-portal, next-route-announcer { display: none !important; }",
  });
  await page.screenshot({
    path: testInfo.outputPath(`story101-play-${state}-${viewportLabel}.png`),
    fullPage: true,
    animations: "disabled",
    scale: "css",
  });
}

test.describe("story101 play experience deterministic acceptance", () => {
  for (const viewport of DAILY_PROGRESS_VIEWPORTS) {
    test(`daily progress stays singular at ${viewport.label}`, async ({ page }, testInfo) => {
      await page.setViewportSize(viewport);
      await page.goto("/e2e-regression?playState=options&timeline=daily");
      const root = fixture(page);

      await expect(root).toBeVisible();
      await expect(
        root.getByText("公元 640 年 8 月 17 日 · 第 5 天 · 29 岁", { exact: true }),
      ).toHaveCount(1);
      await expect(root.getByText(/第3周|周中|第2轮\/3/)).toHaveCount(0);
      await expect(root.getByText("story101 · 人生草稿本", { exact: true })).toHaveCount(0);
      await expect(root.getByText("当前人生", { exact: true })).toHaveCount(0);
      await expectNoHorizontalOverflow(page);
      await captureScreenshot(page, testInfo, "options", `daily-${viewport.label}`);

      await page.goto("/e2e-regression?playState=history&timeline=daily");
      await expect(root.getByText("历史回顾 · 只读", { exact: true })).toHaveCount(1);
      await expect(root.getByTestId("status-bar")).toHaveCount(0);
      await expect(root.getByRole("button", { name: "返回当前" })).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await captureScreenshot(page, testInfo, "history", `daily-${viewport.label}`);
    });
  }

  test("server allowlists every dedicated play fixture without rendering legacy content", async ({
    request,
  }) => {
    for (const state of PLAY_STATES) {
      const response = await request.get(fixtureUrl(state));
      expect(response.ok()).toBe(true);
      const html = await response.text();
      expect(html).toContain('data-testid="play-experience-fixture"');
      expect(html).toContain(`data-play-state="${state}"`);
      expect(html).not.toContain('data-testid="e2e-regression-legacy"');
      expect(html).not.toContain('data-testid="narrative-loading-fixture"');
      expect(html).not.toContain('data-testid="visual-foundation-fixture"');
    }
  });

  test("unsupported or repeated play fixture parameters remain on the legacy page", async ({
    request,
  }) => {
    for (const url of [
      "/e2e-regression",
      "/e2e-regression?playState=unknown",
      "/e2e-regression?playState=options&playState=failed",
    ]) {
      const response = await request.get(url);
      expect(response.ok()).toBe(true);
      const html = await response.text();
      expect(html).toContain('data-testid="e2e-regression-legacy"');
      expect(html).not.toContain('data-testid="play-experience-fixture"');
    }
  });

  test("narrative loading fixture retains server priority over play fixtures", async ({
    request,
  }) => {
    const response = await request.get(
      "/e2e-regression?narrativeLoading=partial&playState=options",
    );
    expect(response.ok()).toBe(true);
    const html = await response.text();
    expect(html).toContain('data-testid="narrative-loading-fixture"');
    expect(html).not.toContain('data-testid="play-experience-fixture"');
    expect(html).not.toContain('data-testid="e2e-regression-legacy"');
  });

  for (const state of PLAY_STATES) {
    test(`${state} exposes the real visible state contract with no application requests`, async ({
      page,
    }) => {
      const api = observeApiRequests(page);
      await openState(page, state);
      await expectStateSemantics(page, state);
      await expectSharedVisualContract(page, state);
      expect(api.requests, `${state} fixture must not call /api/*`).toEqual([]);
      api.stop();
    });
  }

  test("fixture actions stay local without API calls, navigation, or reloads", async ({
    page,
  }) => {
    const actions: Array<{
      state: Exclude<PlayFixtureState, "choosing">;
      name: string;
      expected: string;
    }> = [
      {
        state: "options",
        name: `选择 1：${OPTION_TEXTS[0]}`,
        expected: "choice:0",
      },
      { state: "result", name: "进入周中", expected: "continue-result" },
      { state: "summary", name: "继续人生旅途", expected: "continue-summary" },
      { state: "history", name: "返回当前", expected: "return-current" },
      {
        state: "reconnecting",
        name: "重新连接",
        expected: "recover:reconnecting",
      },
      { state: "polling", name: "重新连接", expected: "recover:polling" },
      { state: "failed", name: "重试", expected: "retry" },
    ];

    for (const action of actions) {
      await openState(page, action.state);
      const api = observeApiRequests(page);
      const frameNavigations: string[] = [];
      let loadCount = 0;
      const observeFrameNavigation = (frame: Frame) => {
        if (frame === page.mainFrame()) frameNavigations.push(frame.url());
      };
      const observeLoad = () => {
        loadCount += 1;
      };
      page.on("framenavigated", observeFrameNavigation);
      page.on("load", observeLoad);

      await expect(
        fixture(page).getByTestId("play-fixture-action-count"),
      ).toHaveText("0");
      await fixture(page).getByRole("button", { name: action.name }).click();
      await expect(
        fixture(page).getByTestId("play-fixture-action-count"),
      ).toHaveText("1");
      await expect(
        fixture(page).getByTestId("play-fixture-last-action"),
      ).toHaveText(action.expected);
      await page.waitForTimeout(100);

      expect(api.requests).toEqual([]);
      expect(frameNavigations).toEqual([]);
      expect(loadCount).toBe(0);
      await expect(fixture(page)).toHaveAttribute(
        "data-play-state",
        action.state,
      );

      api.stop();
      page.off("framenavigated", observeFrameNavigation);
      page.off("load", observeLoad);
    }
  });

  test("mobile production dock stays fixed and records only local actions", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openState(page, "options");
    await expect(fixture(page)).toHaveAttribute("data-slot", "page-transition");
    await expect(fixture(page)).toHaveClass(/\bplay-reading-axis\b/);
    await expect(mobileDock(page)).toBeVisible();
    await expect(mobileDock(page)).toHaveCSS("position", "fixed");

    const api = observeApiRequests(page);
    const frameNavigations: string[] = [];
    let loadCount = 0;
    const observeFrameNavigation = (frame: Frame) => {
      if (frame === page.mainFrame()) frameNavigations.push(frame.url());
    };
    const observeLoad = () => {
      loadCount += 1;
    };
    page.on("framenavigated", observeFrameNavigation);
    page.on("load", observeLoad);

    await mobileDock(page).getByRole("button", { name: "保存" }).click();
    await expect(
      fixture(page).getByTestId("play-fixture-action-count"),
    ).toHaveText("1");
    await expect(
      fixture(page).getByTestId("play-fixture-last-action"),
    ).toHaveText("dock:save");
    await page.waitForTimeout(100);

    expect(api.requests).toEqual([]);
    expect(frameNavigations).toEqual([]);
    expect(loadCount).toBe(0);
    api.stop();
    page.off("framenavigated", observeFrameNavigation);
    page.off("load", observeLoad);
  });

  test("production tools own the desktop trigger, mobile dock, and shared sheet", async ({
    page,
  }) => {
    const api = observeApiRequests(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await openState(page, "options");
    await fixture(page).getByRole("button", { name: "打开工具" }).click();
    await expect(page.getByRole("dialog", { name: "游戏工具" })).toBeVisible();
    await page.getByRole("button", { name: "关闭工具" }).click();

    await page.setViewportSize({ width: 390, height: 844 });
    await openState(page, "options");
    await mobileDock(page).getByRole("button", { name: "更多" }).click();
    const tools = page.getByRole("dialog", { name: "游戏工具" });
    await expect(tools).toBeVisible();
    await expectTouchTargetsAtLeast44(tools);
    await expectNoHorizontalOverflow(page);
    await page.getByRole("button", { name: "关闭工具" }).click();
    await expect(mobileDock(page).getByRole("button", { name: "更多" })).toBeFocused();
    expect(api.requests, "opening the production tools must stay offline").toEqual([]);
    api.stop();
  });

  test("all play states meet desktop and mobile visual and fixed-layer geometry", async ({
    page,
  }, testInfo) => {
    const api = observeApiRequests(page);
    for (const viewport of VISUAL_VIEWPORTS) {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      for (const state of PLAY_STATES) {
        await openState(page, state);
        await expectStateSemantics(page, state);
        await expectSharedVisualContract(page, state);
        if (viewport.width < 768) {
          await expect(mobileDock(page)).toBeVisible();
          await expect(mobileDock(page)).toHaveCSS("position", "fixed");
        } else {
          await expect(mobileDock(page)).toBeHidden();
        }
        await expectFixedLayerClearance(
          page,
          acceptanceAnchor(page, state),
          viewport.width < 768,
        );
        await captureScreenshot(page, testInfo, state, viewport.label);
      }
    }
    expect(api.requests, "visual fixtures must remain offline").toEqual([]);
    api.stop();
  });

  test("all play states remain inside 320px and 375px viewports", async ({
    page,
  }) => {
    const api = observeApiRequests(page);
    for (const width of OVERFLOW_WIDTHS) {
      await page.setViewportSize({ width, height: 844 });
      for (const state of PLAY_STATES) {
        await openState(page, state);
        await expect(mobileDock(page)).toBeVisible();
        await expect(mobileDock(page)).toHaveCSS("position", "fixed");
        await expectNoHorizontalOverflow(page);
        await expectSingleReadingSurface(page);
        await expectTouchTargetsAtLeast44(fixture(page));
        await expectFixedLayerClearance(
          page,
          acceptanceAnchor(page, state),
          true,
        );
      }
    }
    expect(api.requests, "overflow fixtures must remain offline").toEqual([]);
    api.stop();
  });
});
