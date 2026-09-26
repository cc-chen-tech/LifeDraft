import { expect, test } from "@playwright/test";

for (const viewport of [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test(`underlined creation fields keep text inset on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/create");

    const name = page.getByPlaceholder("输入你的角色名");
    const vision = page.getByPlaceholder("描述你希望的人生方向...");

    for (const field of [name, vision]) {
      await expect(field).toBeVisible();
      const padding = await field.evaluate((element) => {
        const style = getComputedStyle(element);
        return { left: style.paddingLeft, right: style.paddingRight };
      });
      expect(padding).toEqual({ left: "12px", right: "12px" });
    }

    await name.fill("林见微");
    await expect(name).toHaveValue("林见微");
    await expect(name).toBeFocused();
    await name.fill("林".repeat(51));
    await expect(name).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByText("角色姓名不能超过 50 字")).toBeVisible();

    await vision.fill("想写一本书");
    await expect(vision).toHaveValue("想写一本书");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
