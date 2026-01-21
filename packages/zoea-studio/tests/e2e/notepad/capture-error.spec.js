import { test, expect } from '@playwright/test';
import { loginAsDefaultUser } from '../../utils/test-helpers.js';

test('capture notepad page errors', async ({ page }) => {
  // Collect ALL console messages
  const consoleMessages = [];
  page.on('console', (msg) => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });

  // Collect page errors (uncaught exceptions)
  const pageErrors = [];
  page.on('pageerror', (error) => {
    pageErrors.push(`${error.name}: ${error.message}\n${error.stack}`);
  });

  // Login first
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  // Fill login form
  await page.locator('input[id="username"]').fill('admin');
  await page.locator('input[id="password"]').fill('admin');
  await page.locator('button[type="submit"]').click();

  // Wait for login to complete
  await page.waitForURL(/\/(dashboard|home)/);
  await page.waitForLoadState('networkidle');

  console.log('\n=== AFTER LOGIN ===');
  console.log('URL:', page.url());

  // Clear messages before navigating to notepad
  consoleMessages.length = 0;
  pageErrors.length = 0;

  // Navigate to notepad
  console.log('\n=== NAVIGATING TO NOTEPAD ===');
  await page.goto('/notepad');

  // Wait a bit for any errors
  await page.waitForTimeout(5000);

  // Take screenshot
  await page.screenshot({ path: '/tmp/notepad_error_capture.png', fullPage: true });

  console.log('\n=== CONSOLE MESSAGES ===');
  for (const msg of consoleMessages) {
    console.log(msg);
  }

  console.log('\n=== PAGE ERRORS ===');
  for (const err of pageErrors) {
    console.log(err);
  }

  // Get page HTML
  const html = await page.content();
  console.log('\n=== PAGE BODY (first 3000 chars) ===');
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  if (bodyMatch) {
    console.log(bodyMatch[1].slice(0, 3000));
  }

  // This test should fail if there are page errors
  if (pageErrors.length > 0) {
    console.log('\n=== FAILING DUE TO PAGE ERRORS ===');
  }
  expect(pageErrors).toHaveLength(0);
});
