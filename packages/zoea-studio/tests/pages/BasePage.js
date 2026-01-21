/**
 * Base Page Object Model
 * 
 * Provides common functionality for all page objects.
 */
export class BasePage {
  constructor(page) {
    this.page = page;
  }

  /**
   * Navigate to a specific path
   */
  async goto(path = '/') {
    await this.page.goto(path);
  }

  /**
   * Wait for page to be fully loaded
   */
  async waitForLoad() {
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Get page title
   */
  async getTitle() {
    return await this.page.title();
  }

  /**
   * Check if element is visible
   */
  async isVisible(selector) {
    return await this.page.isVisible(selector);
  }

  /**
   * Wait for selector to be visible
   */
  async waitForSelector(selector, options = {}) {
    return await this.page.waitForSelector(selector, options);
  }

  /**
   * Take a screenshot
   */
  async screenshot(name) {
    await this.page.screenshot({ path: `test-results/screenshots/${name}.png` });
  }

  /**
   * Get current URL
   */
  getURL() {
    return this.page.url();
  }

  /**
   * Check if on expected path
   */
  isOnPath(expectedPath) {
    return this.getURL().includes(expectedPath);
  }
}
