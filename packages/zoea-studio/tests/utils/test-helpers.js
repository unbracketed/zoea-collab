import { LoginPage } from '../pages/LoginPage.js';
import { getDefaultUser } from '../fixtures/test-users.js';

/**
 * Test Helper Utilities
 * 
 * Common helper functions for E2E tests.
 */

/**
 * Perform login with default user
 */
export async function loginAsDefaultUser(page) {
  const loginPage = new LoginPage(page);
  const user = getDefaultUser();

  await loginPage.goto();
  await loginPage.login(user.username, user.password);

  // Wait for dashboard content (app doesn't redirect, just re-renders when authenticated)
  await page.waitForSelector('text=/Welcome to Zoea Studio/', { timeout: 15000 });

  return user;
}

/**
 * Perform login with custom credentials
 */
export async function login(page, username, password) {
  const loginPage = new LoginPage(page);
  
  await loginPage.goto();
  await loginPage.login(username, password);
  
  return { username, password };
}

/**
 * Wait for API response
 */
export async function waitForAPIResponse(page, urlPattern, timeout = 10000) {
  return await page.waitForResponse(
    response => response.url().includes(urlPattern) && response.status() === 200,
    { timeout }
  );
}

/**
 * Clear browser storage
 * Note: Must be called after navigating to a page, or use context.clearCookies() instead
 */
export async function clearStorage(page) {
  // Navigate to a blank page first to ensure we have access to storage
  try {
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  } catch (error) {
    // If page hasn't been loaded yet, we can't clear storage
    // This is fine - it will be empty anyway on first navigation
    console.warn('Could not clear storage:', error.message);
  }
}

/**
 * Clear browser context (cookies, storage, etc.)
 * Can be called without navigating to a page first
 */
export async function clearContext(context) {
  await context.clearCookies();
  await context.clearPermissions();
}

/**
 * Take a screenshot with timestamp
 */
export async function takeScreenshot(page, name) {
  const timestamp = new Date().toISOString().replace(/:/g, '-');
  await page.screenshot({ 
    path: `test-results/screenshots/${name}-${timestamp}.png`,
    fullPage: true 
  });
}

/**
 * Wait for element to be stable (no animations)
 */
export async function waitForStable(page, selector, timeout = 5000) {
  const element = page.locator(selector);
  await element.waitFor({ state: 'visible', timeout });
  
  // Wait for animations to complete
  await page.waitForTimeout(300);
}

/**
 * Get console errors from page
 */
export function setupConsoleErrorListener(page) {
  const errors = [];
  
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  
  page.on('pageerror', error => {
    errors.push(error.message);
  });
  
  return {
    getErrors: () => errors,
    hasErrors: () => errors.length > 0,
    clear: () => errors.length = 0,
  };
}
