import { defineConfig, devices } from '@playwright/test';
import { loadEnv } from 'vite';

// Load environment variables from project root
const env = loadEnv('development', '../', '');
const BACKEND_PORT = env.ZOEA_CORE_BACKEND_PORT || '8000';
const FRONTEND_PORT = env.ZOEA_FRONTEND_PORT || '5173';

/**
 * Playwright Test Configuration
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './tests/e2e',
  
  // Maximum time one test can run for
  timeout: 30 * 1000,
  
  // Test execution settings
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter to use
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['list']
  ],
  
  // Shared settings for all projects
  use: {
    // Base URL for navigation - use local.zoea.studio to match API domain for cookie sharing
    baseURL: `http://local.zoea.studio:${FRONTEND_PORT}`,
    
    // Collect trace on first retry
    trace: 'on-first-retry',
    
    // Screenshot on failure
    screenshot: 'only-on-failure',
    
    // Video on failure
    video: 'retain-on-failure',
    
    // Timeout for each action
    actionTimeout: 10 * 1000,
    
    // Timeout for navigation
    navigationTimeout: 10 * 1000,
  },
  
  // Configure projects for different browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    
    // Uncomment to test on additional browsers
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],
  
  // Web server configuration
  webServer: [
    {
      command: `cd ../backend && uv run python manage.py runserver ${BACKEND_PORT}`,
      url: `http://local.zoea.studio:${BACKEND_PORT}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
    {
      command: 'npm run dev',
      url: `http://local.zoea.studio:${FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});
