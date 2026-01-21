import { test, expect } from '@playwright/test'
import { loginAsDefaultUser } from '../../utils/test-helpers.js'
import path from 'path'

test.describe('Documents - Image Upload', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsDefaultUser(page)
  })

  test('uploads image and shows status', async ({ page }) => {
    await page.goto('/documents/new/image')

    const filePath = path.resolve('tests/fixtures/image-sample.png')
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.getByRole('button', { name: 'Choose File' }).click(),
    ])
    await fileChooser.setFiles(filePath)

    await page.fill('input[placeholder="Optional description"]', 'test image')
    await page.click('button:has-text("Upload Image")')

    // Without explicit project/workspace selection, we expect a validation message
    const statusLocator = page.getByText('Select a project and workspace before uploading.')
    await expect(statusLocator).toBeVisible({ timeout: 10000 })
  })
})
