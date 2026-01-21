import { BasePage } from './BasePage.js'

/**
 * Chat Page Object Model aligned to the new layout
 */
export class ChatPage extends BasePage {
  constructor(page) {
    super(page)
    this.selectors = {
      headerTitle: 'text=Chat',
      recentConversationsTitle: 'text=Recent Conversations',
      messageInput: '.message-input',
      sendButton: '.send-button',
      stickyInputContainer: '.chat-floating-input',
      messagesContainer: '.messages-container',
    }
  }

  async goto() {
    await super.goto('/chat')
  }

  async isLoaded() {
    return this.isVisible(this.selectors.messageInput)
  }

  async headerVisible() {
    return this.isVisible(this.selectors.headerTitle)
  }

  async recentConversationsVisible() {
    return this.isVisible(this.selectors.recentConversationsTitle)
  }

  async inputVisible() {
    return this.isVisible(this.selectors.messageInput)
  }

  async stickyInputVisibleAfterScroll() {
    const container = this.page.locator(this.selectors.messagesContainer)
    const sticky = this.page.locator(this.selectors.stickyInputContainer)
    await container.evaluate((el) => {
      el.scrollTop = el.scrollHeight
    })
    return sticky.isVisible()
  }
}
