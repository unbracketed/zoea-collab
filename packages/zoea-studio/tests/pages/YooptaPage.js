import { BasePage } from './BasePage.js';

/**
 * Page Object for Yoopta document editor and viewer pages
 */
export class YooptaPage extends BasePage {
  constructor(page) {
    super(page);
    this.selectors = {
      // New document page
      titleInput: 'input[placeholder="Document title"]',
      descriptionInput: 'input[placeholder="Optional description"]',
      folderSelect: 'select',
      saveButton: 'button[title="Save document"]',
      backButton: 'button[title="Back to documents"]',
      statusMessage: '.text-primary',

      // Yoopta editor
      editorContainer: '.yoopta-editor-container',
      yooptaEditor: '[data-testid="yoopta-editor-core"], .yoopta-editor',
      imageLibraryButton: 'button:has-text("Insert from Library")',

      // Document detail page
      editButton: 'button[title="Edit document"]',
      convertButton: 'button[title="Convert to Rich Text (Yoopta)"]',
      exportButton: 'button[title="Export document"]',
      exportMenu: '.absolute.right-0.mt-2',
      downloadMarkdown: 'button:has-text("Markdown (.md)")',
      downloadHtml: 'button:has-text("HTML (.html)")',
      copyMarkdown: 'button:has-text("Copy as Markdown")',
      copyHtml: 'button:has-text("Copy as HTML")',

      // View mode
      yooptaViewer: '.yoopta-editor-container',
      noContentMessage: 'text=No content available.',

      // Document card in list
      yooptaDocCard: '.border.rounded-lg:has(.text-orange-500)',
      yooptaTypeIcon: '.text-orange-500',
    };
  }

  /**
   * Navigate to new rich text document page
   */
  async gotoNewDocument() {
    await super.goto('/documents/new/richtext');
  }

  /**
   * Navigate to a specific document
   */
  async gotoDocument(documentId) {
    await super.goto(`/documents/${documentId}`);
  }

  /**
   * Fill in document metadata
   */
  async fillMetadata(title, description = '') {
    await this.page.fill(this.selectors.titleInput, title);
    if (description) {
      await this.page.fill(this.selectors.descriptionInput, description);
    }
  }

  /**
   * Type content in the Yoopta editor
   */
  async typeContent(text) {
    // Focus the editor and type
    const editor = this.page.locator(this.selectors.editorContainer);
    await editor.click();
    await this.page.keyboard.type(text);
  }

  /**
   * Wait for editor to be ready
   */
  async waitForEditor() {
    await this.page.waitForSelector(this.selectors.editorContainer, { state: 'visible' });
  }

  /**
   * Save the document
   */
  async saveDocument() {
    await this.page.click(this.selectors.saveButton);
  }

  /**
   * Click edit button on document detail page
   */
  async clickEdit() {
    await this.page.click(this.selectors.editButton);
  }

  /**
   * Click export button on document detail page
   */
  async clickExport() {
    await this.page.click(this.selectors.exportButton);
  }

  /**
   * Export to markdown
   */
  async exportToMarkdown() {
    await this.clickExport();
    await this.page.click(this.selectors.downloadMarkdown);
  }

  /**
   * Export to HTML
   */
  async exportToHtml() {
    await this.clickExport();
    await this.page.click(this.selectors.downloadHtml);
  }

  /**
   * Copy as markdown
   */
  async copyAsMarkdown() {
    await this.clickExport();
    await this.page.click(this.selectors.copyMarkdown);
  }

  /**
   * Copy as HTML
   */
  async copyAsHtml() {
    await this.clickExport();
    await this.page.click(this.selectors.copyHtml);
  }

  /**
   * Check if editor is visible
   */
  async isEditorVisible() {
    return await this.isVisible(this.selectors.editorContainer);
  }

  /**
   * Check if export menu is visible
   */
  async isExportMenuVisible() {
    return await this.isVisible(this.selectors.exportMenu);
  }

  /**
   * Check if edit button is visible
   */
  async isEditButtonVisible() {
    return await this.isVisible(this.selectors.editButton);
  }

  /**
   * Check if export button is visible
   */
  async isExportButtonVisible() {
    return await this.isVisible(this.selectors.exportButton);
  }

  /**
   * Get status message text
   */
  async getStatusMessage() {
    const element = this.page.locator(this.selectors.statusMessage);
    if (await element.isVisible()) {
      return await element.textContent();
    }
    return null;
  }

  /**
   * Wait for redirect after save
   */
  async waitForDocumentRedirect() {
    await this.page.waitForURL(/\/documents\/\d+/);
  }

  /**
   * Check if on document detail page
   */
  isOnDocumentDetailPage() {
    return /\/documents\/\d+/.test(this.getURL());
  }
}
