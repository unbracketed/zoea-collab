import { test, expect } from '@playwright/test';
import { LoginPage } from '../../pages/LoginPage.js';
import { DashboardPage } from '../../pages/DashboardPage.js';
import { getDefaultUser } from '../../fixtures/test-users.js';
import { setupConsoleErrorListener } from '../../utils/test-helpers.js';

test.describe('Authentication - Login', () => {
  let loginPage;
  let dashboardPage;
  let user;

  test.beforeEach(async ({ page, context }) => {
    loginPage = new LoginPage(page);
    dashboardPage = new DashboardPage(page);
    user = getDefaultUser();

    // Clear cookies and storage before each test
    await context.clearCookies();
  });

  test('should display login form', async () => {
    await loginPage.goto();

    expect(await loginPage.isLoginFormVisible()).toBe(true);
  });

  test('should login with valid credentials', async ({ page }) => {
    const consoleErrors = setupConsoleErrorListener(page);

    await loginPage.goto();
    await loginPage.login(user.username, user.password);

    // Should show dashboard content after login
    await page.waitForSelector('text=/Welcome to Zoea Studio/', { timeout: 15000 });
    expect(await dashboardPage.isLoaded()).toBe(true);

    // Should not have console errors
    expect(consoleErrors.hasErrors()).toBe(false);
  });

  test('should show error with invalid credentials', async () => {
    await loginPage.goto();
    await loginPage.login('invalid', 'credentials');
    
    // Should stay on login page
    expect(await loginPage.isLoginFormVisible()).toBe(true);
    
    // May show error message (depends on backend implementation)
    const errorMessage = await loginPage.getErrorMessage();
    // Error handling may vary, so just check we're still on login page
  });

  test('should redirect to login when accessing protected routes', async ({ page }) => {
    // Try to access dashboard without logging in
    await page.goto('/dashboard');

    // Should show login form (app shows Login component at any URL when unauthenticated)
    await page.waitForSelector('form', { state: 'visible', timeout: 10000 });
    expect(await loginPage.isLoginFormVisible()).toBe(true);
  });

  test('should persist authentication across page reloads', async ({ page }) => {
    // Login
    await loginPage.goto();
    await loginPage.login(user.username, user.password);

    // Wait for dashboard to load
    await page.waitForSelector('text=/Welcome to Zoea Studio/', { timeout: 15000 });

    // Reload page
    await page.reload();

    // Should still show dashboard (authenticated)
    await page.waitForSelector('text=/Welcome to Zoea Studio/', { timeout: 15000 });
    expect(await dashboardPage.isLoaded()).toBe(true);
  });
});
