import { test, expect } from '@playwright/test';
import { loginAsDefaultUser } from '../../utils/test-helpers.js';

test.describe('Notepad Debug', () => {
  test('capture console errors on notepad page', async ({ page }) => {
    // Collect ALL console messages
    const consoleMessages = [];
    page.on('console', (msg) => {
      consoleMessages.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location(),
      });
    });

    // Collect page errors
    const pageErrors = [];
    page.on('pageerror', (error) => {
      pageErrors.push({
        message: error.message,
        stack: error.stack,
      });
    });

    await loginAsDefaultUser(page);
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');

    // Wait a bit for any async errors
    await page.waitForTimeout(3000);

    // Take screenshot
    await page.screenshot({ path: '/tmp/notepad_debug.png', fullPage: true });

    // Print all console messages
    console.log('\n=== CONSOLE MESSAGES ===');
    for (const msg of consoleMessages) {
      console.log(`[${msg.type}] ${msg.text}`);
      if (msg.location?.url) {
        console.log(`  at ${msg.location.url}:${msg.location.lineNumber}`);
      }
    }

    // Print page errors
    console.log('\n=== PAGE ERRORS ===');
    for (const err of pageErrors) {
      console.log(`Error: ${err.message}`);
      if (err.stack) {
        console.log(`Stack: ${err.stack.slice(0, 500)}`);
      }
    }

    // Get page HTML
    const html = await page.content();
    console.log('\n=== PAGE HTML (first 2000 chars) ===');
    console.log(html.slice(0, 2000));

    // Check if there's an error displayed
    const errorAlert = page.locator('[role="alert"]');
    if (await errorAlert.count() > 0) {
      console.log('\n=== ERROR ALERT TEXT ===');
      console.log(await errorAlert.first().textContent());
    }

    // Assert something to fail the test if there are page errors
    expect(pageErrors.length).toBe(0);
  });
});
