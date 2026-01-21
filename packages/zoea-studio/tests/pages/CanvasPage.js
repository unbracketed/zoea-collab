import { BasePage } from './BasePage.js'

export class CanvasPage extends BasePage {
  constructor(page) {
    super(page)
    this.selectors = {
      editorToggle: 'text=/D2 Code Editor/i',
      editorHideShow: 'button:has-text("Hide"), button:has-text("Show")',
      editorTextarea: '.d2-editor',
    }
  }

  async goto() {
    await super.goto('/canvas')
  }

  async toggleEditor() {
    await this.page.click(this.selectors.editorHideShow)
  }

  async editorVisible() {
    return this.isVisible(this.selectors.editorTextarea)
  }
}
