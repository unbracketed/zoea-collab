import { BasePage } from './BasePage.js';

/**
 * Login Page Object Model
 * 
 * Encapsulates interactions with the login page.
 */
export class LoginPage extends BasePage {
  constructor(page) {
    super(page);
    
    // Selectors
    this.selectors = {
      usernameInput: '#username',
      passwordInput: '#password',
      submitButton: 'button[type="submit"]',
      loginForm: 'form',
      errorMessage: '.text-destructive',
    };
  }

  /**
   * Navigate to login page (goes to root, which shows login when unauthenticated)
   */
  async goto() {
    await super.goto('/');
    // Wait for auth check to complete and login form to appear
    await this.page.waitForSelector(this.selectors.loginForm, { state: 'visible', timeout: 10000 });
  }

  /**
   * Fill in login credentials
   */
  async fillCredentials(username, password) {
    await this.page.fill(this.selectors.usernameInput, username);
    await this.page.fill(this.selectors.passwordInput, password);
  }

  /**
   * Click submit button
   */
  async submit() {
    await this.page.click(this.selectors.submitButton);
  }

  /**
   * Perform login action
   */
  async login(username, password) {
    await this.fillCredentials(username, password);
    await this.submit();
    // Wait for navigation to complete
    await this.waitForLoad();
  }

  /**
   * Check if login form is visible
   */
  async isLoginFormVisible() {
    return await this.isVisible(this.selectors.loginForm);
  }

  /**
   * Get error message if present
   */
  async getErrorMessage() {
    const errorElement = await this.page.locator(this.selectors.errorMessage);
    if (await errorElement.isVisible()) {
      return await errorElement.textContent();
    }
    return null;
  }

}
