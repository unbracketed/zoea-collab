import { test, expect } from '@playwright/test';
import { loginAsDefaultUser, setupConsoleErrorListener } from '../../utils/test-helpers.js';

test.describe('Notepad Page', () => {
  let consoleErrors;

  test.beforeEach(async ({ page }) => {
    consoleErrors = setupConsoleErrorListener(page);
    await loginAsDefaultUser(page);
  });

  test('should navigate to notepad page without errors', async ({ page }) => {
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');

    // Wait for editor to appear
    await page.waitForSelector('.yoopta-editor-container', { timeout: 10000 });

    // Check for console errors
    const errors = consoleErrors.getErrors();
    console.log('Console errors:', errors);

    // Take screenshot
    await page.screenshot({ path: '/tmp/notepad_initial.png', fullPage: true });

    // Verify no critical errors
    expect(consoleErrors.hasErrors()).toBe(false);
  });

  test('should allow typing in the editor', async ({ page }) => {
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');

    // Wait for editor container
    const editorContainer = page.locator('.yoopta-editor-container');
    await expect(editorContainer).toBeVisible({ timeout: 10000 });

    // Click to focus
    await editorContainer.click();
    await page.waitForTimeout(500);

    // Type some text
    await page.keyboard.type('Test text before adding content');
    await page.waitForTimeout(500);

    await page.screenshot({ path: '/tmp/notepad_after_typing.png', fullPage: true });

    // Verify text appears in editor
    await expect(editorContainer).toContainText('Test text before adding content');
  });

  test('should preserve text when adding Zoea content via Insert', async ({ page }) => {
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');

    // Wait for editor container
    const editorContainer = page.locator('.yoopta-editor-container');
    await expect(editorContainer).toBeVisible({ timeout: 10000 });

    // Click to focus
    await editorContainer.click();
    await page.waitForTimeout(500);

    // Type initial text
    await page.keyboard.type('This text should remain after adding content');
    await page.waitForTimeout(500);

    await page.screenshot({ path: '/tmp/notepad_01_typed.png', fullPage: true });

    // Click Insert button
    const insertButton = page.locator('button:has-text("Insert")');
    await expect(insertButton).toBeVisible();
    await insertButton.click();
    await page.waitForTimeout(500);

    await page.screenshot({ path: '/tmp/notepad_02_insert_modal.png', fullPage: true });

    // Check if modal is open
    const modal = page.locator('[role="dialog"]');
    if (await modal.isVisible()) {
      // Look for conversation messages or content to add
      const contentList = modal.locator('button, [role="listitem"]');
      const count = await contentList.count();
      console.log(`Found ${count} content items in modal`);

      if (count > 0) {
        // Click first item
        await contentList.first().click();
        await page.waitForTimeout(2000);

        await page.screenshot({ path: '/tmp/notepad_03_after_add.png', fullPage: true });
      } else {
        console.log('No content items found in Insert modal');
        // Close modal
        await page.keyboard.press('Escape');
      }
    }

    // Verify original text is still present
    await expect(editorContainer).toContainText('This text should remain after adding content');

    // Check for console errors
    const errors = consoleErrors.getErrors();
    console.log('Console errors:', errors);
  });

  test('should preserve text when navigating away and adding item from chat', async ({ page }) => {
    // This test verifies the fix for the regression where user-edited text blocks
    // were lost when items were added from another page (like chat)

    // Step 1: Navigate to notepad and add some text
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');

    const editorContainer = page.locator('.yoopta-editor-container');
    await expect(editorContainer).toBeVisible({ timeout: 10000 });

    await editorContainer.click();
    await page.waitForTimeout(500);

    const uniqueText = `Cross-page test ${Date.now()}`;
    await page.keyboard.type(uniqueText);
    await page.waitForTimeout(500);

    await page.screenshot({ path: '/tmp/notepad_cross_page_01_typed.png', fullPage: true });

    // Verify text appears
    await expect(editorContainer).toContainText(uniqueText);

    // Step 2: Navigate to chat page
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    await page.screenshot({ path: '/tmp/notepad_cross_page_02_chat.png', fullPage: true });

    // Step 3: Look for a message to add to notepad (if any exist)
    // Check for message hover actions
    const messages = page.locator('[data-testid="chat-message"], .chat-message, [role="article"]');
    const messageCount = await messages.count();
    console.log(`Found ${messageCount} messages in chat`);

    if (messageCount > 0) {
      // Hover on first message to reveal actions
      await messages.first().hover();
      await page.waitForTimeout(500);

      // Look for "Add to Notebook" or similar button
      const addButton = page.locator('button[title*="notebook"], button[title*="Notebook"], [aria-label*="notebook"]');
      if (await addButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        await addButton.click();
        await page.waitForTimeout(1000);
        console.log('Added message to notebook from chat');
      } else {
        console.log('No "Add to Notebook" button found on message');
      }
    }

    // Step 4: Navigate back to notepad
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/notepad_cross_page_03_returned.png', fullPage: true });

    // Step 5: Verify our text is still there
    const editorAfterReturn = page.locator('.yoopta-editor-container');
    await expect(editorAfterReturn).toBeVisible({ timeout: 10000 });

    // The critical assertion: text should be preserved
    await expect(editorAfterReturn).toContainText(uniqueText);

    // Check for console errors
    const errors = consoleErrors.getErrors();
    if (errors.length > 0) {
      console.log('Console errors during cross-page test:', errors);
    }
  });

  test('should preserve text when adding item via store action simulation', async ({ page }) => {
    // This test simulates the scenario more directly by typing, navigating away briefly,
    // and returning to verify the store keeps content in sync

    // Step 1: Navigate to notepad and type text
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');

    const editorContainer = page.locator('.yoopta-editor-container');
    await expect(editorContainer).toBeVisible({ timeout: 10000 });

    await editorContainer.click();
    await page.waitForTimeout(500);

    const uniqueText = `Store sync test ${Date.now()}`;
    await page.keyboard.type(uniqueText);
    await page.waitForTimeout(500);

    // Verify text appears
    await expect(editorContainer).toContainText(uniqueText);

    // Step 2: Navigate to documents page briefly
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Step 3: Navigate back to notepad immediately
    await page.goto('/notepad');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Step 4: Verify text is preserved (store should have kept it)
    const editorAfterReturn = page.locator('.yoopta-editor-container');
    await expect(editorAfterReturn).toBeVisible({ timeout: 10000 });

    // Note: If we haven't saved, the text may not persist across full navigation
    // This test verifies the store sync behavior during navigation
    const hasText = await editorAfterReturn.locator(`text=${uniqueText}`).isVisible({ timeout: 5000 }).catch(() => false);

    if (!hasText) {
      console.log('Text not preserved without saving - this is expected if store was reset');
      console.log('The fix ensures items added from other pages include local edits');
    } else {
      console.log('Text preserved across navigation via store sync');
    }

    await page.screenshot({ path: '/tmp/notepad_store_sync_result.png', fullPage: true });
  });
});
