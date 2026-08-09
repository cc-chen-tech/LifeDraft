import { expect, test, type Frame, type Page, type Request, type TestInfo } from "@playwright/test";

const FOUNDATION_URL = "/e2e-regression?visualSystem=foundation";
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT = { width: 390, height: 844 };

function fixture(page: Page) {
  return page.getByTestId("visual-foundation-fixture");
}

function viewportFor(testInfo: TestInfo) {
  return testInfo.project.name === "Mobile Safari" ? MOBILE_VIEWPORT : DESKTOP_VIEWPORT;
}

async function expectNoHorizontalOverflow(page: Page) {
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
}

test.beforeEach(async ({ page }, testInfo) => {
  await page.setViewportSize(viewportFor(testInfo));
});

test("server-renders only the allowlisted visual foundation fixture", async ({ request }) => {
  const foundationResponse = await request.get(FOUNDATION_URL);
  expect(foundationResponse.ok()).toBe(true);
  const foundationHtml = await foundationResponse.text();

  expect(foundationHtml).toContain('data-testid="visual-foundation-fixture"');
  expect(foundationHtml).not.toContain('data-testid="e2e-regression-legacy"');
  expect(foundationHtml).not.toContain('data-testid="narrative-loading-fixture"');

  const narrativePriorityResponse = await request.get(
    "/e2e-regression?narrativeLoading=initial&visualSystem=foundation",
  );
  expect(narrativePriorityResponse.ok()).toBe(true);
  const narrativePriorityHtml = await narrativePriorityResponse.text();
  expect(narrativePriorityHtml).toContain('data-testid="narrative-loading-fixture"');
  expect(narrativePriorityHtml).not.toContain('data-testid="visual-foundation-fixture"');

  for (const url of [
    "/e2e-regression",
    "/e2e-regression?visualSystem=unknown",
    "/e2e-regression?visualSystem=foundation&visualSystem=unknown",
  ]) {
    const legacyResponse = await request.get(url);
    expect(legacyResponse.ok()).toBe(true);
    const legacyHtml = await legacyResponse.text();

    expect(legacyHtml).toContain('data-testid="e2e-regression-legacy"');
    expect(legacyHtml).not.toContain('data-testid="visual-foundation-fixture"');
  }
});

test("renders the approved visual tokens, accessible states, and responsive evidence", async ({
  page,
}, testInfo) => {
  const apiRequests: string[] = [];
  const observeRequest = (request: Request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/")) apiRequests.push(path);
  };
  page.on("request", observeRequest);

  await page.goto(FOUNDATION_URL);
  await expect(fixture(page)).toBeVisible();
  await expect(fixture(page).getByTestId("visual-foundation-brand")).toBeVisible();
  await expect(fixture(page).getByText("请补充人物的称呼。", { exact: true })).toBeVisible();
  await expect(
    fixture(page).getByRole("textbox", { name: "补充这一页的方向" }),
  ).toBeVisible();

  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#0D0C0B");
  const fontLoaded = await page.evaluate(async () => {
    await document.fonts.load('600 32px "Spline Sans Variable"', "story101");
    return document.fonts.check('600 32px "Spline Sans Variable"', "story101");
  });
  expect(fontLoaded).toBe(true);

  const loadedFontResources = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .map((entry) => entry.name)
      .filter((name) => name.includes("spline-sans") && name.endsWith(".woff2")),
  );
  expect(loadedFontResources).toHaveLength(1);
  expect(loadedFontResources[0]).toContain("spline-sans-latin-wght-normal");
  expect(loadedFontResources[0]).not.toContain("latin-ext");

  const licenseResponse = await page.request.get("/licenses/SplineSans-OFL.txt");
  expect(licenseResponse.ok()).toBe(true);
  const licenseText = await licenseResponse.text();
  expect(licenseText).toContain("Copyright 2021 The Spline Sans Project Authors");
  expect(licenseText).toContain("SIL OPEN FONT LICENSE Version 1.1");

  const visualValues = await fixture(page).evaluate((element) => {
    const root = getComputedStyle(document.documentElement);
    const brand = element.querySelector('[data-testid="visual-foundation-brand"]');
    const touchButton = element.querySelector('[data-testid="visual-foundation-touch-control"]');
    const normalTextarea = element.querySelector('[data-testid="visual-foundation-normal-textarea"]');
    const invalidInput = element.querySelector('#foundation-character-name');
    const body = element.querySelector('[data-testid="visual-foundation-body"]');
    const helper = element.querySelector('[data-testid="visual-foundation-helper"]');

    return {
      canvas: root.getPropertyValue("--surface-canvas").trim(),
      reading: root.getPropertyValue("--surface-reading").trim(),
      primary: root.getPropertyValue("--text-primary").trim(),
      rule: root.getPropertyValue("--border-default").trim(),
      brandFamily: brand ? getComputedStyle(brand).fontFamily : "",
      bodySize: body ? getComputedStyle(body).fontSize : "",
      helperSize: helper ? getComputedStyle(helper).fontSize : "",
      touchButtonBorder: touchButton ? getComputedStyle(touchButton).borderColor : "",
      touchButtonRadius: touchButton ? getComputedStyle(touchButton).borderRadius : "",
      normalTextareaBorder: normalTextarea ? getComputedStyle(normalTextarea).borderColor : "",
      normalTextareaRadius: normalTextarea ? getComputedStyle(normalTextarea).borderRadius : "",
      invalidInputRadius: invalidInput ? getComputedStyle(invalidInput).borderRadius : "",
    };
  });

  expect(visualValues).toMatchObject({
    canvas: "#0d0c0b",
    reading: "#11100f",
    primary: "#f0ece6",
    rule: "#34302c",
    bodySize: "14px",
    helperSize: "12px",
    touchButtonBorder: "rgb(113, 103, 93)",
    touchButtonRadius: "6px",
    normalTextareaBorder: "rgb(113, 103, 93)",
    normalTextareaRadius: "6px",
    invalidInputRadius: "6px",
  });
  expect(visualValues.brandFamily).toMatch(/Spline Sans Variable/i);

  const touchTargetSizes = await fixture(page).locator("[data-touch-target]").evaluateAll((targets) =>
    targets.map((target) => {
      const style = getComputedStyle(target);
      return {
        tagName: target.tagName,
        height: Number.parseFloat(style.height),
        width: Number.parseFloat(style.width),
      };
    }),
  );
  expect(touchTargetSizes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ tagName: "BUTTON" }),
      expect.objectContaining({ tagName: "INPUT" }),
      expect.objectContaining({ tagName: "TEXTAREA" }),
    ]),
  );
  for (const target of touchTargetSizes) {
    expect(target.height).toBeGreaterThanOrEqual(44);
    expect(target.width).toBeGreaterThanOrEqual(44);
  }

  await expect(fixture(page).getByRole("status")).toHaveCount(3);
  await expect(fixture(page).getByRole("status").first()).toHaveAttribute("aria-live", "polite");
  await expect(fixture(page).getByRole("alert")).toHaveCount(1);
  await expect(fixture(page).getByRole("textbox", { name: "人物称呼" })).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(fixture(page).getByRole("textbox", { name: "人物称呼" })).toHaveAttribute(
    "required",
    "",
  );
  await expect(fixture(page).getByTestId("visual-foundation-disabled-control")).toBeDisabled();
  await expect(fixture(page).locator('[data-slot="surface"][data-variant="raised"]')).toHaveCount(0);

  const touchControl = fixture(page).getByTestId("visual-foundation-touch-control");
  await touchControl.hover();
  await touchControl.focus();
  await expect(touchControl).toBeFocused();
  expect(
    await touchControl.evaluate((element) => getComputedStyle(element).boxShadow),
  ).not.toBe("none");
  await expect(fixture(page).getByRole("button", { name: "标记这一页" }).locator("svg")).toHaveCount(1);
  await expectNoHorizontalOverflow(page);

  await page.screenshot({
    path: testInfo.outputPath(`visual-foundation-${viewportFor(testInfo).width}x${viewportFor(testInfo).height}.png`),
    fullPage: false,
  });

  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 844 });
    await expectNoHorizontalOverflow(page);
  }

  expect(apiRequests).toEqual([]);
  page.off("request", observeRequest);
});

test("keeps local visual fixture actions in place without API requests or navigation", async ({ page }) => {
  const apiRequests: string[] = [];
  const navigations: string[] = [];
  let loadCount = 0;
  const observeRequest = (request: Request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/")) apiRequests.push(path);
  };
  const observeNavigation = (frame: Frame) => {
    if (frame === page.mainFrame()) navigations.push(frame.url());
  };
  const observeLoad = () => {
    loadCount += 1;
  };

  await page.goto(FOUNDATION_URL);
  const beforeUrl = page.url();
  const navigationEntries = await page.evaluate(
    () => performance.getEntriesByType("navigation").length,
  );
  page.on("request", observeRequest);
  page.on("framenavigated", observeNavigation);
  page.on("load", observeLoad);

  await fixture(page).getByRole("button", { name: "保存这一页" }).click();
  await expect(fixture(page).getByTestId("visual-foundation-action-result")).toHaveText(
    "草稿已保存在当前夹具中。",
  );
  await page.waitForTimeout(100);

  expect(page.url()).toBe(beforeUrl);
  expect(await page.evaluate(() => performance.getEntriesByType("navigation").length)).toBe(
    navigationEntries,
  );
  expect(apiRequests).toEqual([]);
  expect(navigations).toEqual([]);
  expect(loadCount).toBe(0);

  page.off("request", observeRequest);
  page.off("framenavigated", observeNavigation);
  page.off("load", observeLoad);
});
