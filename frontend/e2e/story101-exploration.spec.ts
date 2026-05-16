import { test, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// ============================================================
// Story101.live Deep Exploration Script v2
// ============================================================
// Properly handles: registration, 5-step character creation,
// opening story, gameplay through 4+ weeks, all side features.
// ============================================================

const SITE_URL = 'https://story101.live';
const REPORT_DIR = path.resolve(__dirname, 'exploration-report');

// ---- Issue tracker ----
interface Issue {
  id: number;
  severity: 'critical' | 'major' | 'minor' | 'cosmetic';
  category: 'bug' | 'ux' | 'performance' | 'visual' | 'copy' | 'a11y';
  page: string;
  element: string;
  description: string;
  expected: string;
  actual: string;
  screenshot?: string;
  timestamp: string;
}

const allIssues: Issue[] = [];
let issueId = 0;

function addIssue(page: Page, severity: Issue['severity'], category: Issue['category'], element: string, description: string, expected: string, actual: string) {
  issueId++;
  const issue: Issue = { id: issueId, severity, category, page: page.url(), element, description, expected, actual, timestamp: new Date().toISOString() };
  allIssues.push(issue);
  console.log(`[ISSUE #${issueId}][${severity.toUpperCase()}][${category}] ${element}: ${description}`);
  console.log(`  Expected: ${expected}`);
  console.log(`  Actual: ${actual}`);
}

async function shot(page: Page, name: string) {
  const dir = path.join(REPORT_DIR, 'screenshots');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${Date.now()}_${name.replace(/[^a-zA-Z0-9_-]/g, '_')}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => {});
  return file;
}

// ---- Helpers ----
async function waitForEnabled(page: Page, locator: any, timeoutMs = 120_000, label = 'button') {
  console.log(`  Waiting for enabled: ${label} (timeout: ${timeoutMs / 1000}s)`);
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      if (await locator.isEnabled({ timeout: 1000 }).catch(() => false)) {
        console.log(`  ${label} is now enabled (waited ${((Date.now() - start) / 1000).toFixed(1)}s)`);
        return true;
      }
    } catch { /* retry */ }
    await page.waitForTimeout(2000);
  }
  addIssue(page, 'major', 'ux', label, `${label} should become enabled`, `${label} stayed disabled for ${timeoutMs / 1000}s`, `Timeout`);
  return false;
}

async function clickEnabled(page: Page, locator: any, label: string, waitAfter = 3000) {
  console.log(`  Clicking: ${label}`);
  try {
    await locator.scrollIntoViewIfNeeded().catch(() => {});
    if (!(await locator.isEnabled().catch(() => false))) {
      addIssue(page, 'major', 'bug', label, `"${label}" should be clickable`, `"${label}" is disabled`, `Disabled`);
      return false;
    }
    await locator.click();
    await page.waitForTimeout(waitAfter);
    return true;
  } catch (e: any) {
    addIssue(page, 'major', 'bug', label, `Click "${label}" should work`, `Failed: ${e.message}`, `Click failed`);
    return false;
  }
}

async function scanAllButtons(page: Page, label: string) {
  console.log(`\n=== BUTTON SCAN: ${label} ===`);
  const buttons = await page.locator('button:visible, [role="button"]:visible').all();
  console.log(`  Total visible buttons: ${buttons.length}`);
  for (const btn of buttons) {
    try {
      const text = (await btn.textContent())?.trim().slice(0, 100) || '[empty]';
      const disabled = !(await btn.isEnabled().catch(() => false));
      console.log(`  ${disabled ? '[DISABLED]' : '[ENABLED]'} "${text}"`);
    } catch { /* skip */ }
  }
}

async function fillInput(page: Page, placeholder: string, value: string) {
  const input = page.getByPlaceholder(placeholder).first();
  if (await input.isVisible({ timeout: 1000 }).catch(() => false)) {
    await input.fill(value);
    console.log(`  Filled "${placeholder}" with "${value}"`);
    return true;
  }
  return false;
}

function generateReport(issues: Issue[], finalUrl: string, finalTitle: string): string {
  const critical = issues.filter(i => i.severity === 'critical');
  const major = issues.filter(i => i.severity === 'major');
  const minor = issues.filter(i => i.severity === 'minor');
  const cosmetic = issues.filter(i => i.severity === 'cosmetic');

  const lines: string[] = [];
  lines.push(`# Story101.live Deep Exploration Report`);
  lines.push('');
  lines.push(`**Date:** ${new Date().toISOString()}`);
  lines.push(`**Final URL:** ${finalUrl}`);
  lines.push(`**Final Page Title:** ${finalTitle}`);
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push('| Severity | Count |');
  lines.push('|----------|-------|');
  lines.push(`| Critical | ${critical.length} |`);
  lines.push(`| Major    | ${major.length} |`);
  lines.push(`| Minor    | ${minor.length} |`);
  lines.push(`| Cosmetic | ${cosmetic.length} |`);
  lines.push(`| **Total** | **${issues.length}** |`);
  lines.push('');

  const byCategory: Record<string, Issue[]> = {};
  for (const i of issues) {
    (byCategory[i.category] ||= []).push(i);
  }

  for (const sev of ['critical', 'major', 'minor', 'cosmetic']) {
    const items = issues.filter(i => i.severity === sev);
    lines.push(`---`);
    lines.push(`## ${sev.charAt(0).toUpperCase() + sev.slice(1)} Issues (${items.length})`);
    lines.push('');
    if (items.length === 0) {
      lines.push('None found.\n');
    }
    for (const i of items) {
      lines.push(`### #${i.id} [${i.severity.toUpperCase()}] ${i.category} — ${i.element}`);
      lines.push('');
      lines.push(`- **Page:** ${i.page}`);
      lines.push(`- **Description:** ${i.description}`);
      lines.push(`- **Expected:** ${i.expected}`);
      lines.push(`- **Actual:** ${i.actual}`);
      lines.push(`- **Time:** ${i.timestamp}`);
      lines.push('');
    }
  }

  lines.push('---');
  lines.push('## All Issues by Category');
  for (const [cat, items] of Object.entries(byCategory)) {
    lines.push(`\n### ${cat.toUpperCase()} (${items.length})\n`);
    for (const i of items) {
      lines.push(`- #${i.id} [${i.severity}] **${i.element}**: ${i.description}`);
    }
  }
  lines.push('');
  lines.push('*Generated by Playwright automated exploration script*');
  return lines.join('\n');
}

// ============================================================
// MAIN TEST
// ============================================================
test.describe('Story101.live Deep Exploration', () => {
  test.setTimeout(1_800_000); // 30 minutes total

  test('Full deep exploration', async ({ page }) => {
    fs.mkdirSync(REPORT_DIR, { recursive: true });
    fs.mkdirSync(path.join(REPORT_DIR, 'screenshots'), { recursive: true });

    console.log('============================================================');
    console.log('  Story101.live Deep Exploration v2');
    console.log('  Started at:', new Date().toISOString());
    console.log('============================================================');

    // ============================================================
    // PHASE 1: LANDING PAGE
    // ============================================================
    console.log('\n========== PHASE 1: LANDING PAGE ==========');
    await page.goto(SITE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    await shot(page, '01_landing');
    console.log(`  Title: "${await page.title()}"`);
    await scanAllButtons(page, 'landing');

    // ============================================================
    // PHASE 2: REGISTRATION
    // ============================================================
    console.log('\n========== PHASE 2: REGISTRATION ==========');

    // Click "注册" on landing page
    const registerBtn = page.getByRole('button', { name: /注册/ });
    if (await registerBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await clickEnabled(page, registerBtn, '注册 button');
    } else {
      // Fallback: click 新游戏 which may trigger registration sheet
      const newGameBtn = page.getByRole('button', { name: /新游戏/ });
      await clickEnabled(page, newGameBtn, '新游戏 button');
    }
    await page.waitForTimeout(1500);
    await shot(page, '02_registration_sheet');
    await scanAllButtons(page, 'registration sheet');

    // Fill registration form
    await fillInput(page, '你的名字', '深度测试员');
    await fillInput(page, '输入你的名字', '深度测试员');

    // Click "创建账户"
    const createAccountBtn = page.getByRole('button', { name: /创建账户/ });
    if (await createAccountBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      if (await createAccountBtn.isEnabled().catch(() => false)) {
        await clickEnabled(page, createAccountBtn, '创建账户');
      } else {
        console.log('  创建账户 is disabled - waiting for name input');
        // Try again after filling more inputs
        await fillInput(page, '你的名字', '深度测试员');
        await page.waitForTimeout(1000);
        await clickEnabled(page, createAccountBtn, '创建账户 (retry)');
      }
    }
    await page.waitForTimeout(2000);
    await shot(page, '02b_after_register');
    await scanAllButtons(page, 'after registration');

    // Capture private key if shown
    try {
      const privateKeyEl = page.locator('text=/[A-Za-z0-9_-]{20,}/').first();
      const privateKey = await privateKeyEl.textContent();
      if (privateKey && privateKey.length > 20) {
        console.log(`  PRIVATE KEY: ${privateKey.trim()}`);
      }
    } catch { /* no key visible */ }

    // Click "我已保存密钥，开始体验"
    const startExperienceBtn = page.getByRole('button', { name: /保存密钥|开始体验/ });
    if (await startExperienceBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await clickEnabled(page, startExperienceBtn, '开始体验');
      await page.waitForTimeout(2000);
    }

    await shot(page, '02c_post_register');
    console.log(`  Current URL: ${page.url()}`);

    // ============================================================
    // PHASE 3: CHARACTER CREATION (5 STEPS)
    // ============================================================
    console.log('\n========== PHASE 3: CHARACTER CREATION ==========');

    // If we're still on home page, click "新游戏" to start character creation
    const onHomePage = page.url().includes('create') === false;
    if (onHomePage) {
      const newGameBtn2 = page.getByRole('button', { name: /新游戏/ });
      if (await newGameBtn2.isVisible({ timeout: 2000 }).catch(() => false)) {
        await clickEnabled(page, newGameBtn2, '新游戏 (start creation)');
        await page.waitForTimeout(3000);
      }
    }

    console.log(`  Character creation URL: ${page.url()}`);
    await shot(page, '03_char_create_start');
    await scanAllButtons(page, 'character creation start');

    // Step 0 (1/5): Fill character name
    // The page shows "角色姓名" heading and "输入你的角色名" textbox
    await fillInput(page, '输入你的角色名', '云逸');
    await page.waitForTimeout(1000);
    await shot(page, '03_step0_name_filled');

    // Wait for "下一步" to become enabled (AI needs to auto-generate era content)
    const nextBtn = page.getByRole('button', { name: /下一步/ });
    let nextEnabled = await waitForEnabled(page, nextBtn, 120_000, '下一步 (step 0)');
    if (!nextEnabled) {
      // Try filling name again in a different input
      await fillInput(page, '你的角色名', '云逸');
      await fillInput(page, '角色名', '云逸');
      nextEnabled = await waitForEnabled(page, nextBtn, 30_000, '下一步 (step 0 retry)');
    }

    if (nextEnabled) {
      await clickEnabled(page, nextBtn, '下一步 (step 0→1)');
      await page.waitForTimeout(3000);
    }
    await shot(page, '03_step1_age');
    await scanAllButtons(page, 'step 1 (age)');

    // Step 1 (2/5): Age - wait for auto-generation, then click next
    nextEnabled = await waitForEnabled(page, nextBtn, 120_000, '下一步 (step 1)');
    if (nextEnabled) {
      await clickEnabled(page, nextBtn, '下一步 (step 1→2)');
      await page.waitForTimeout(3000);
    }
    await shot(page, '03_step2_gender');
    await scanAllButtons(page, 'step 2 (gender)');

    // Step 2 (3/5): Gender - wait, then next
    nextEnabled = await waitForEnabled(page, nextBtn, 120_000, '下一步 (step 2)');
    if (nextEnabled) {
      await clickEnabled(page, nextBtn, '下一步 (step 2→3)');
      await page.waitForTimeout(3000);
    }
    await shot(page, '03_step3_world');
    await scanAllButtons(page, 'step 3 (world)');

    // Step 3 (4/5): World - wait, then next
    nextEnabled = await waitForEnabled(page, nextBtn, 120_000, '下一步 (step 3)');
    if (nextEnabled) {
      await clickEnabled(page, nextBtn, '下一步 (step 3→4)');
      await page.waitForTimeout(5000); // Extra wait - world step creates game too
    }
    await shot(page, '03_step4_portrait');
    await scanAllButtons(page, 'step 4 (portrait)');

    // Step 4 (5/5): Portrait - wait for image generation, then next
    nextEnabled = await waitForEnabled(page, nextBtn, 180_000, '下一步 (step 4 portrait)');
    if (nextEnabled) {
      await clickEnabled(page, nextBtn, '下一步 (portrait→autoGen)');
      await page.waitForTimeout(5000);
    }
    await shot(page, '03_autogen');
    await scanAllButtons(page, 'auto generation screen');

    // Wait for auto-generation to complete (family, relationships, traits, wealth)
    console.log('  Waiting for auto-gen (background settings generation)...');
    await page.waitForTimeout(15000); // Can take a while

    // Check if completion screen appeared
    const startGameBtn = page.getByRole('button', { name: /开始游戏/ });
    const startGameVisible = await startGameBtn.isVisible({ timeout: 60_000 }).catch(() => false);
    if (!startGameVisible) {
      // Might still be on auto-gen screen, wait more
      await page.waitForTimeout(30000);
    }

    await shot(page, '03_completion');

    // Click "开始游戏"
    if (await startGameBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await clickEnabled(page, startGameBtn, '开始游戏');
      await page.waitForTimeout(5000);
    }
    console.log(`  After start game URL: ${page.url()}`);
    await shot(page, '03_started_game');

    // ============================================================
    // PHASE 4: OPENING STORY
    // ============================================================
    console.log('\n========== PHASE 4: OPENING STORY ==========');

    // Wait for opening story to load
    await page.waitForTimeout(10000);
    await shot(page, '04_opening_story');
    await scanAllButtons(page, 'opening story');

    // Click "开始游戏" or "进入游戏" or "开始人生" on opening page
    const enterGameBtn = page.getByRole('button', { name: /开始游戏|进入游戏|开始人生|进入人生|开始/i });
    if (await enterGameBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await clickEnabled(page, enterGameBtn, '进入游戏 (from opening)');
      await page.waitForTimeout(5000);
    }

    console.log(`  Gameplay URL: ${page.url()}`);
    await shot(page, '04_entered_game');

    // ============================================================
    // PHASE 5: GAMEPLAY — PLAY THROUGH WEEKS 1-4
    // ============================================================
    console.log('\n========== PHASE 5: GAMEPLAY (WEEKS 1-4) ==========');

    for (let week = 1; week <= 4; week++) {
      console.log(`\n  === WEEK ${week} ===`);

      // Wait for AI to generate content
      console.log('  Waiting for AI content generation...');
      await page.waitForTimeout(8000);

      // Scan all buttons on the gameplay page
      await scanAllButtons(page, `week ${week} start`);

      // Look for choice/option buttons (the 3-4 story choices)
      // On the play page, choices are shown as clickable cards/buttons
      const choiceBtns = page.locator('button').filter({ hasText: /.{4,}/ });

      let choiceMade = false;
      for (let c = 0; c < 5; c++) {
        const btn = choiceBtns.nth(c);
        if (await btn.isVisible({ timeout: 1000 }).catch(() => false) && await btn.isEnabled().catch(() => false)) {
          const text = (await btn.textContent())?.trim().slice(0, 120) || '';
          // Skip navigation/utility buttons - only click story choices
          const isUtility = /返回|下一步|继续|设置|音乐|收藏|存档|分享|角色|登录|注册|新建|加载/.test(text);
          if (!isUtility && text.length > 4) {
            console.log(`  Week ${week}: Choosing "${text}"`);
            await clickEnabled(page, btn, `Week ${week} choice`, 2000);
            choiceMade = true;

            // Wait for AI response to the choice
            console.log('  Waiting for AI response...');
            await page.waitForTimeout(10000);
            await shot(page, `05_week${week}_after_choice`);
            await scanAllButtons(page, `week ${week} after choice`);
            break;
          }
        }
      }

      if (!choiceMade) {
        console.log(`  Week ${week}: No clear choice button found, looking for any clickable button...`);
        // Try to find a continue/proceed button
        const contBtn = page.locator('button').filter({ hasText: /继续|下一周|next week|continue/ }).first();
        if (await contBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await clickEnabled(page, contBtn, `Week ${week} continue`);
          await page.waitForTimeout(8000);
        }
      }

      await shot(page, `05_week${week}_end`);
    }

    // ============================================================
    // PHASE 6: TEST ALL SIDE FEATURES
    // ============================================================
    console.log('\n========== PHASE 6: SIDE FEATURES ==========');

    // Test each feature button on the play page
    const features = [
      { selector: page.locator('button').filter({ hasText: /收藏/ }).first(), name: 'Collection' },
      { selector: page.locator('button').filter({ hasText: /音乐/ }).first(), name: 'Music Player' },
      { selector: page.locator('button').filter({ hasText: /成就/ }).first(), name: 'Achievements' },
      { selector: page.locator('button').filter({ hasText: /回顾|历史/ }).first(), name: 'History' },
      { selector: page.locator('button').filter({ hasText: /分享/ }).first(), name: 'Share' },
      { selector: page.locator('button').filter({ hasText: /存档/ }).first(), name: 'Save' },
      { selector: page.locator('button').filter({ hasText: /设定|角色设定/ }).first(), name: 'Character Settings' },
      { selector: page.locator('button').filter({ hasText: /重写|重新生成|重来/ }).first(), name: 'Regenerate/Rewrite' },
      { selector: page.locator('button').filter({ hasText: /自定义|自由输入/ }).first(), name: 'Custom Choice' },
    ];

    for (const feature of features) {
      try {
        if (await feature.selector.isVisible({ timeout: 1500 }).catch(() => false)) {
          console.log(`  Testing: ${feature.name}`);

          // Before screenshot
          await shot(page, `06_pre_${feature.name.toLowerCase().replace(/[^a-z]/g, '_')}`);

          if (await feature.selector.isEnabled().catch(() => false)) {
            await feature.selector.click();
            await page.waitForTimeout(3000);
            await shot(page, `06_${feature.name.toLowerCase().replace(/[^a-z]/g, '_')}`);
            await scanAllButtons(page, `feature: ${feature.name}`);

            // Close/dismiss if a panel opened
            const closeBtn = page.locator('button').filter({ hasText: /关闭|✕|×|back|返回/ }).first();
            if (await closeBtn.isVisible({ timeout: 1500 }).catch(() => false)) {
              await closeBtn.click();
              await page.waitForTimeout(500);
            }
            await page.keyboard.press('Escape');
            await page.waitForTimeout(500);
          } else {
            addIssue(page, 'minor', 'ux', feature.name, `${feature.name} should be clickable`, `${feature.name} is disabled`, `Disabled`);
          }
        } else {
          console.log(`  Feature "${feature.name}" not visible on page`);
        }
      } catch (e: any) {
        console.log(`  Error testing ${feature.name}: ${e.message}`);
      }
    }

    // ============================================================
    // PHASE 7: PLAY A FEW MORE WEEKS + TEST CHAT BAR
    // ============================================================
    console.log('\n========== PHASE 7: EXTENDED PLAY + CHAT ==========');

    // Test the chat/free-input bar
    try {
      const chatInput = page.getByPlaceholder(/输入|说|写|聊天|chat|自由/).first();
      if (await chatInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await chatInput.fill('我想去探索一下这个世界的其他地方');
        console.log('  Filled chat bar with custom input');
        await shot(page, '07_chat_filled');

        const sendBtn = page.locator('button').filter({ hasText: /发送|确认|send/ }).first();
        if (await sendBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await clickEnabled(page, sendBtn, 'Send custom input');
          await page.waitForTimeout(10000);
          await shot(page, '07_chat_response');
        }
      }
    } catch (e: any) {
      console.log(`  Chat bar test skipped: ${e.message}`);
    }

    // Play 2 more rounds to get deeper into the story
    for (let extra = 5; extra <= 6; extra++) {
      console.log(`\n  === Extra Round ${extra} ===`);
      await page.waitForTimeout(8000);
      await scanAllButtons(page, `round ${extra}`);

      const btns = page.locator('button').filter({ hasText: /.{4,}/ });
      for (let c = 0; c < 5; c++) {
        const btn = btns.nth(c);
        if (await btn.isVisible({ timeout: 1000 }).catch(() => false) && await btn.isEnabled().catch(() => false)) {
          const text = (await btn.textContent())?.trim().slice(0, 120) || '';
          const isUtility = /返回|下一步|继续|设置|音乐|收藏|存档|分享|角色|登录|注册|新建|加载/.test(text);
          if (!isUtility && text.length > 4) {
            console.log(`  Round ${extra}: Choosing "${text}"`);
            await clickEnabled(page, btn, `Round ${extra} choice`, 2000);
            await page.waitForTimeout(10000);
            break;
          }
        }
      }
      await shot(page, `07_round_${extra}`);
    }

    // ============================================================
    // PHASE 8: FINAL SCREENSHOT & REPORT
    // ============================================================
    console.log('\n========== PHASE 8: FINAL SUMMARY ==========');
    await shot(page, '08_final_state');

    const finalUrl = page.url();
    const finalTitle = await page.title();
    console.log(`\n  Final URL: ${finalUrl}`);
    console.log(`  Final Title: ${finalTitle}`);

    // Summary
    const bySeverity: Record<string, number> = {};
    const byCategory: Record<string, number> = {};
    for (const issue of allIssues) {
      bySeverity[issue.severity] = (bySeverity[issue.severity] || 0) + 1;
      byCategory[issue.category] = (byCategory[issue.category] || 0) + 1;
    }
    console.log(`\n  Total Issues: ${allIssues.length}`);
    console.log(`  By Severity: ${JSON.stringify(bySeverity)}`);
    console.log(`  By Category: ${JSON.stringify(byCategory)}`);

    // Write reports
    const reportMd = generateReport(allIssues, finalUrl, finalTitle);
    fs.writeFileSync(path.join(REPORT_DIR, 'report.md'), reportMd);
    fs.writeFileSync(path.join(REPORT_DIR, 'issues.json'), JSON.stringify(allIssues, null, 2));
    console.log(`\n  Reports written to ${REPORT_DIR}/report.md and issues.json`);

    console.log('\n============================================================');
    console.log('  EXPLORATION COMPLETE');
    console.log('============================================================');
  });
});
