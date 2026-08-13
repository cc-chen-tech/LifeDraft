import { expect, type Locator, type Page } from '@playwright/test';

const DESKTOP_BREAKPOINT_PX = 768;

/**
 * Open the production play-tools sheet through the entry exposed by the
 * current viewport: the desktop bookmark action or the mobile action dock.
 */
export async function openPlayTools(page: Page): Promise<Locator> {
  const viewportWidth = page.viewportSize()?.width ?? DESKTOP_BREAKPOINT_PX;
  const triggerName = viewportWidth < DESKTOP_BREAKPOINT_PX ? '更多' : '打开工具';
  const trigger = page.getByRole('button', { name: triggerName, exact: true });

  await expect(trigger).toBeVisible({ timeout: 15_000 });
  await trigger.click();

  const dialog = page.getByRole('dialog', { name: '游戏工具', exact: true });
  await expect(dialog).toBeVisible({ timeout: 5_000 });
  return dialog;
}
