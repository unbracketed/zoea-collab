import { BasePage } from './BasePage.js'

export class DocumentsPage extends BasePage {
  constructor(page) {
    super(page)
    this.selectors = {
      gridToggle: 'button[aria-label="Grid view"]',
      listToggle: 'button[aria-label="List view"]',
      card: '.grid .border.rounded-lg',
      row: '.grid.grid-cols-[1.5fr_2fr_1fr_auto] + div',
      folderSidebar: 'div:has(> .folder-item)',
      documentsHeader: 'text=Documents',
    }
  }

  async goto() {
    await super.goto('/documents')
  }

  async switchToGrid() {
    await this.page.click(this.selectors.gridToggle)
  }

  async switchToList() {
    await this.page.click(this.selectors.listToggle)
  }

  async gridVisible() {
    return this.isVisible(this.selectors.card)
  }

  async listVisible() {
    return this.isVisible(this.selectors.row)
  }
}
