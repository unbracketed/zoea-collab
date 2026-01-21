import { test, expect } from '@playwright/test'
import { ChatPage } from '../../pages/ChatPage.js'
import { loginAsDefaultUser } from '../../utils/test-helpers.js'

test.describe('Chat - layout sanity', () => {
  let chatPage

  test.beforeEach(async ({ page }) => {
    await loginAsDefaultUser(page)
    chatPage = new ChatPage(page)
    await chatPage.goto()
  })

  test('loads chat layout with header, recent conversations, and input', async () => {
    expect(await chatPage.isLoaded()).toBe(true)
    expect(await chatPage.headerVisible()).toBe(true)
    expect(await chatPage.recentConversationsVisible()).toBe(true)
    expect(await chatPage.inputVisible()).toBe(true)
  })

  test('input stays visible after scrolling messages area', async () => {
    expect(await chatPage.stickyInputVisibleAfterScroll()).toBe(true)
  })
})
