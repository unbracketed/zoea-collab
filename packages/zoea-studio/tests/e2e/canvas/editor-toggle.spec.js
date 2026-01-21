import { test, expect } from '@playwright/test'
import { loginAsDefaultUser } from '../../utils/test-helpers.js'
import { CanvasPage } from '../../pages/CanvasPage.js'

test.describe('Canvas editor toggle', () => {
  let canvasPage

  test.beforeEach(async ({ page }) => {
    await loginAsDefaultUser(page)
    canvasPage = new CanvasPage(page)
    await canvasPage.goto()
  })

  test('editor can be toggled and remains focusable', async ({ page }) => {
    // Editor should be visible initially
    expect(await canvasPage.editorVisible()).toBe(true)

    // Hide editor
    await canvasPage.toggleEditor()
    expect(await canvasPage.editorVisible()).toBe(false)

    // Show editor again
    await canvasPage.toggleEditor()
    expect(await canvasPage.editorVisible()).toBe(true)

    // Focus and type
    await page.fill('.d2-editor', 'x -> y: test')
    const value = await page.$eval('.d2-editor', (el) => el.value)
    expect(value).toContain('x -> y: test')
  })
})
