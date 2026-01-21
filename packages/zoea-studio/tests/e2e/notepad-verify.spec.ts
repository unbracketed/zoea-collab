import { test, expect, chromium } from '@playwright/test';

test('verify ClipboardItem blocks render on page load', async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Login
  await page.goto('http://local.zoea.studio:20000/');
  await page.waitForTimeout(2000);
  await page.locator('input[id="username"]').fill('admin');
  await page.locator('input[id="password"]').fill('admin');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(2000);

  // Navigate to clipboards
  await page.goto('http://local.zoea.studio:20000/clipboards');
  await page.waitForTimeout(5000);

  // Verify blocks render
  const yooptaBlocks = page.locator('[data-yoopta-block]');
  const blockCount = await yooptaBlocks.count();
  console.log('Yoopta blocks rendered:', blockCount);
  expect(blockCount).toBeGreaterThan(0);

  // Verify ClipboardItem embeds
  const embedBlocks = page.locator('.zoea-clipboard-item-embed');
  const embedCount = await embedBlocks.count();
  console.log('ClipboardItem embeds:', embedCount);
  expect(embedCount).toBeGreaterThan(0);

  // Screenshot
  await page.screenshot({ path: '/tmp/notepad_verify.png', fullPage: true });

  // Refresh and verify persistence
  console.log('\nRefreshing page...');
  await page.reload();
  await page.waitForTimeout(5000);

  const blockCountAfterRefresh = await yooptaBlocks.count();
  const embedCountAfterRefresh = await embedBlocks.count();
  console.log('After refresh - Yoopta blocks:', blockCountAfterRefresh);
  console.log('After refresh - ClipboardItem embeds:', embedCountAfterRefresh);

  expect(blockCountAfterRefresh).toBeGreaterThan(0);
  expect(embedCountAfterRefresh).toBeGreaterThan(0);

  await page.screenshot({ path: '/tmp/notepad_verify_after_refresh.png', fullPage: true });

  await browser.close();
});
