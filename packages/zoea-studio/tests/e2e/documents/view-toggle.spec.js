import { test, expect } from '@playwright/test'
import { loginAsDefaultUser } from '../../utils/test-helpers.js'
import { DocumentsPage } from '../../pages/DocumentsPage.js'

test.describe('Documents view toggle', () => {
  let documentsPage

  test.beforeEach(async ({ page }) => {
    await loginAsDefaultUser(page)
    documentsPage = new DocumentsPage(page)
    await documentsPage.goto()
  })

  test('switches between grid and list views', async () => {
    // Default grid
    await expect(await documentsPage.gridVisible()).toBe(true)

    // Switch to list
    await documentsPage.switchToList()
    await expect(await documentsPage.listVisible()).toBe(true)

    // Switch back to grid
    await documentsPage.switchToGrid()
    await expect(await documentsPage.gridVisible()).toBe(true)
  })
})
