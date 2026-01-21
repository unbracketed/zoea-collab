"""Test notepad functionality with Playwright."""
from playwright.sync_api import sync_playwright
import time

BASE_URL = "http://local.zoea.studio:20000"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Capture console messages
    console_messages = []
    page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))

    # Step 1: Login
    print("Step 1: Logging in...")
    page.goto(BASE_URL, wait_until='networkidle')
    time.sleep(1)

    page.fill('#username', 'admin')
    page.fill('#password', 'admin')
    page.click('button[type="submit"]')

    page.wait_for_load_state('networkidle')
    time.sleep(2)

    page.screenshot(path='/tmp/01_after_login.png', full_page=True)
    print(f"URL after login: {page.url}")

    # Step 2: Navigate to notepad
    print("\nStep 2: Navigating to notepad...")
    page.goto(f"{BASE_URL}/notepad", wait_until='networkidle')
    time.sleep(3)

    page.screenshot(path='/tmp/02_notepad_initial.png', full_page=True)
    print(f"URL: {page.url}")

    # Check for errors
    errors = [msg for msg in console_messages if msg.startswith('[error]')]
    if errors:
        print("\n--- Console Errors ---")
        for err in errors:
            print(f"  {err[:300]}")

    # Look for Yoopta editor
    editor_container = page.locator('.yoopta-editor-container')
    print(f"\nYoopta editor containers: {editor_container.count()}")

    contenteditable = page.locator('[contenteditable="true"]')
    print(f"Contenteditable elements: {contenteditable.count()}")

    # Look for any error alerts on the page
    alerts = page.locator('[role="alert"]')
    if alerts.count() > 0:
        print(f"\nAlert messages found: {alerts.count()}")
        for i in range(alerts.count()):
            print(f"  Alert {i}: {alerts.nth(i).text_content()[:200]}")

    # Try to find and interact with the editor
    print("\n--- Trying to interact with editor ---")
    yoopta_editor = page.locator('.yoopta-editor')
    if yoopta_editor.count() > 0:
        print(f"Found .yoopta-editor element")
        # Click to focus
        yoopta_editor.first.click()
        time.sleep(1)

        # Try typing
        page.keyboard.type("Test text before adding content")
        time.sleep(1)
        page.screenshot(path='/tmp/03_after_typing.png', full_page=True)
        print("Typed some text")
    else:
        print("No .yoopta-editor element found")

    # Print all visible text content in the notebook area
    notebook_section = page.locator('.bg-surface.border.border-border')
    if notebook_section.count() > 0:
        print(f"\nNotebook section text: {notebook_section.first.text_content()[:500]}")

    browser.close()
    print("\nDone! Screenshots saved to /tmp/")
