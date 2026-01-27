# Playwright E2E Test Suite

Comprehensive end-to-end testing for Zoea Studio using Playwright.

## Directory Structure

```
tests/
├── e2e/                    # End-to-end test specs
│   ├── auth/              # Authentication tests
│   ├── chat/              # Chat functionality tests
│   └── navigation/        # Navigation and routing tests
├── fixtures/              # Test data and fixtures
│   └── test-users.js      # User credentials for testing
├── pages/                 # Page Object Models (POMs)
│   ├── BasePage.js        # Base page with common methods
│   ├── LoginPage.js       # Login page interactions
│   ├── DashboardPage.js   # Dashboard page interactions
│   └── ChatPage.js        # Chat page interactions
├── utils/                 # Test utilities
│   └── test-helpers.js    # Common helper functions
└── README.md              # This file
```

## Running Tests

### Quick Start

```bash
# Run all E2E tests
npm run test:e2e

# Run with Playwright UI (interactive mode)
npm run test:e2e:ui

# Run in headed mode (see browser)
npm run test:e2e:headed

# Debug tests
npm run test:e2e:debug

# View test report
npm run test:e2e:report
```

### Using mise

```bash
# Run E2E tests
mise run test-e2e

# Run with UI
mise run test-e2e-ui

# Run all tests (backend + frontend + E2E)
mise run test-all
```

### Running Specific Tests

```bash
# Run a specific test file
npx playwright test tests/e2e/auth/login.spec.js

# Run tests in a specific directory
npx playwright test tests/e2e/chat

# Run tests matching a pattern
npx playwright test -g "should login"

# Run a single test
npx playwright test tests/e2e/auth/login.spec.js:12
```

## Configuration

Test configuration is in `playwright.config.js`. Key settings:

- **Port Configuration**: Reads from `.env` (`ZOEA_CORE_BACKEND_PORT`, `ZOEA_FRONTEND_PORT`)
- **Web Servers**: Automatically starts backend and frontend before tests
- **Browsers**: Chromium (default), Firefox, WebKit available
- **Reporters**: HTML, JSON, and console output

### Environment Variables

Tests use the same port configuration as the application:

```env
ZOEA_CORE_BACKEND_PORT=8000    # Django backend port
ZOEA_FRONTEND_PORT=5173   # Vite frontend port
```

## Writing Tests

### Using Page Object Models

Page Object Models (POMs) encapsulate page interactions:

```javascript
import { test, expect } from '@playwright/test';
import { LoginPage } from '../../pages/LoginPage.js';
import { ChatPage } from '../../pages/ChatPage.js';
import { loginAsDefaultUser } from '../../utils/test-helpers.js';

test.describe('My Feature', () => {
  let chatPage;

  test.beforeEach(async ({ page }) => {
    // Login before each test
    await loginAsDefaultUser(page);
    
    chatPage = new ChatPage(page);
    await chatPage.goto();
  });

  test('should do something', async () => {
    await chatPage.sendMessage('Hello');
    
    const messageCount = await chatPage.getMessageCount();
    expect(messageCount).toBeGreaterThanOrEqual(2);
  });
});
```

### Test Helpers

Common utilities in `utils/test-helpers.js`:

```javascript
import { loginAsDefaultUser, waitForAPIResponse, clearStorage } from '../../utils/test-helpers.js';

// Login with default user
await loginAsDefaultUser(page);

// Wait for API response
await waitForAPIResponse(page, '/api/chat');

// Clear browser storage
await clearStorage(page);

// Setup console error listener
const consoleErrors = setupConsoleErrorListener(page);
expect(consoleErrors.hasErrors()).toBe(false);
```

### Test Organization

- **Describe blocks**: Group related tests by feature
- **BeforeEach**: Setup common state (login, navigate, etc.)
- **Clear naming**: Use descriptive test names starting with "should"
- **Isolation**: Each test should be independent

### Best Practices

1. **Use Page Objects**: Don't interact with selectors directly in tests
2. **Use Test Helpers**: Reuse common operations (login, waiting, etc.)
3. **Wait for State**: Use `waitForURL`, `waitForSelector`, not arbitrary timeouts
4. **Check Console Errors**: Use `setupConsoleErrorListener` to catch JS errors
5. **Screenshot on Failure**: Automatic in config, but can take manual screenshots
6. **Clean State**: Use `beforeEach` to ensure clean state between tests

## Debugging

### Visual Debugging

```bash
# Run in headed mode to see browser
npm run test:e2e:headed

# Use Playwright UI for step-by-step debugging
npm run test:e2e:ui

# Use debug mode with Playwright Inspector
npm run test:e2e:debug
```

### Console Logs

```javascript
// Add console.log in your test
console.log(await chatPage.getMessages());

// Use page.pause() to pause execution
await page.pause();
```

### Screenshots

```javascript
import { takeScreenshot } from '../../utils/test-helpers.js';

// Take a screenshot
await takeScreenshot(page, 'my-test-screenshot');
```

## Test Reports

After running tests, view the HTML report:

```bash
npm run test:e2e:report
```

Reports include:
- Test results summary
- Screenshots on failure
- Video recordings on failure
- Execution traces

## CI/CD

Tests are configured for CI environments:

- `forbidOnly`: Prevents `.only` from being committed
- `retries`: 2 retries in CI, 0 locally
- `workers`: 1 worker in CI, parallel locally
- `webServer.reuseExistingServer`: false in CI

## Expanding the Test Suite

### Adding New Tests

1. Create a new spec file in appropriate directory (`e2e/feature/`)
2. Use existing Page Objects or create new ones
3. Import test helpers for common operations
4. Follow naming conventions and best practices

### Adding New Page Objects

1. Create new file in `tests/pages/`
2. Extend `BasePage` class
3. Define selectors in constructor
4. Add methods for page interactions
5. Export the class

### Adding New Fixtures

1. Add to `tests/fixtures/`
2. Export data/functions for reuse
3. Import in tests as needed

## Troubleshooting

### Tests Failing Locally

1. Ensure backend and frontend are not already running
2. Check `.env` has correct port configuration
3. Clear browser state: `await clearStorage(page)`
4. Run in headed mode to see what's happening

### Timeout Errors

- Increase timeout in `playwright.config.js`
- Check if backend/frontend started successfully
- Verify API is responding: `curl http://localhost:8000/api/health`

### Port Conflicts

- Change ports in `.env`
- Ensure no other services using the ports
- Restart test suite after port changes

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Page Object Model Pattern](https://playwright.dev/docs/pom)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [Debugging Tests](https://playwright.dev/docs/debug)
