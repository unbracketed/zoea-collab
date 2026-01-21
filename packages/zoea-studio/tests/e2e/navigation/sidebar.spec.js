import { test, expect } from '@playwright/test'
import { DashboardPage } from '../../pages/DashboardPage.js'
import { ChatPage } from '../../pages/ChatPage.js'
import { LoginPage } from '../../pages/LoginPage.js'
import { loginAsDefaultUser } from '../../utils/test-helpers.js'

test.describe('Navigation - App Shell', () => {
  let dashboardPage
  let chatPage

  test.beforeEach(async ({ page }) => {
    await loginAsDefaultUser(page)
    dashboardPage = new DashboardPage(page)
    chatPage = new ChatPage(page)
  })

  test('sidebar/navigation visible on dashboard', async () => {
    await dashboardPage.goto()
    expect(await dashboardPage.isSidebarVisible()).toBe(true)
  })

  test('navigate via nav bar: dashboard -> chat -> dashboard', async ({ page }) => {
    await dashboardPage.goto()
    await dashboardPage.navigateToChat()
    await page.waitForURL('**/chat')
    expect(await chatPage.isLoaded()).toBe(true)

    await dashboardPage.navigateToDashboard()
    await page.waitForURL('**/dashboard')
    expect(await dashboardPage.isLoaded()).toBe(true)
  })

  test('logout from dashboard', async ({ page }) => {
    const loginPage = new LoginPage(page)
    await dashboardPage.goto()
    await dashboardPage.logout()
    await page.waitForURL('**/login')
    expect(await loginPage.isLoginFormVisible()).toBe(true)
  })
})
