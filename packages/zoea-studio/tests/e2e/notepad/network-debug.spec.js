import { test, expect } from '@playwright/test';

test.describe('Network Debug', () => {
  test('capture network requests during login', async ({ page }) => {
    // Collect all network requests and responses
    const requests = [];
    const responses = [];

    page.on('request', (request) => {
      if (request.url().includes('/api/')) {
        requests.push({
          url: request.url(),
          method: request.method(),
          headers: request.headers(),
          postData: request.postData(),
        });
      }
    });

    page.on('response', (response) => {
      if (response.url().includes('/api/')) {
        responses.push({
          url: response.url(),
          status: response.status(),
          statusText: response.statusText(),
        });
      }
    });

    // Navigate to login page
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    console.log('\n=== AFTER INITIAL LOAD ===');
    console.log('Requests:', JSON.stringify(requests, null, 2));
    console.log('Responses:', JSON.stringify(responses, null, 2));

    // Take screenshot
    await page.screenshot({ path: '/tmp/network_debug_1_initial.png', fullPage: true });

    // Try to fill in login form
    const usernameInput = page.locator('input[id="username"], input[name="username"], input[type="text"]').first();
    const passwordInput = page.locator('input[id="password"], input[name="password"], input[type="password"]').first();
    const submitButton = page.locator('button[type="submit"]');

    await usernameInput.fill('admin');
    await passwordInput.fill('admin');

    await page.screenshot({ path: '/tmp/network_debug_2_filled.png', fullPage: true });

    // Clear previous requests
    requests.length = 0;
    responses.length = 0;

    // Click submit
    await submitButton.click();

    // Wait for response
    await page.waitForTimeout(5000);

    await page.screenshot({ path: '/tmp/network_debug_3_after_login.png', fullPage: true });

    console.log('\n=== AFTER LOGIN ATTEMPT ===');
    console.log('Requests:', JSON.stringify(requests, null, 2));
    console.log('Responses:', JSON.stringify(responses, null, 2));

    // Print current URL
    console.log('Current URL:', page.url());

    // Check for errors on page
    const errorText = await page.locator('[role="alert"], .error, .text-red-500').textContent().catch(() => 'No error element found');
    console.log('Error text:', errorText);
  });
});
