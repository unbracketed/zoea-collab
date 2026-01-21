import { BasePage } from './BasePage.js'

export class DashboardPage extends BasePage {
  constructor(page) {
    super(page)
    this.selectors = {
      welcomeMessage: 'text=/Welcome to Zoea Studio/',
      navDashboard: 'button[aria-label="Dashboard"]',
      navChat: 'button[aria-label="Chat"]',
      sidebarSection: 'aside.w-[280px]',
      logoutButton: 'button:has-text("Logout")',
    }
  }

  async goto() {
    await super.goto('/dashboard')
  }

  async isLoaded() {
    return this.isVisible(this.selectors.welcomeMessage)
  }

  async navigateToChat() {
    await this.page.click(this.selectors.navChat)
    await this.waitForLoad()
  }

  async navigateToDashboard() {
    await this.page.click(this.selectors.navDashboard)
    await this.waitForLoad()
  }

  async logout() {
    await this.page.click(this.selectors.logoutButton)
    await this.waitForLoad()
  }

  async isSidebarVisible() {
    return this.isVisible(this.selectors.sidebarSection)
  }
}
