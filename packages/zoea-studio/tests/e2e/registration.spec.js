/**
 * Registration Flow E2E Tests
 *
 * Tests the user registration flow including:
 * - Registration form validation
 * - Successful registration
 * - Email verification page
 */

import { test, expect } from '@playwright/test';

test.describe('User Registration', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app - should show login page when not authenticated
    await page.goto('/');

    // Wait for login form to be visible
    await page.waitForSelector('text=Zoea Studio', { timeout: 10000 });
  });

  test('should show registration form when clicking Sign up link', async ({ page }) => {
    // Click the "Sign up" link
    await page.click('text=Sign up');

    // Wait for registration form to appear
    await expect(page.locator('text=Create Account')).toBeVisible();
    await expect(page.locator('text=Sign up for Zoea Studio')).toBeVisible();

    // Verify form fields are present
    await expect(page.locator('input#username')).toBeVisible();
    await expect(page.locator('input#email')).toBeVisible();
    await expect(page.locator('input#password1')).toBeVisible();
    await expect(page.locator('input#password2')).toBeVisible();

    // Verify sign up button is present
    await expect(page.locator('button:has-text("Sign Up")')).toBeVisible();

    // Verify "Sign in" link is present to go back
    await expect(page.locator('text=Sign in')).toBeVisible();
  });

  test('should validate password mismatch', async ({ page }) => {
    // Click the "Sign up" link
    await page.click('text=Sign up');

    // Fill in the form with mismatched passwords
    await page.fill('input#username', 'testuser');
    await page.fill('input#email', 'test@example.com');
    await page.fill('input#password1', 'password123');
    await page.fill('input#password2', 'password456');

    // Click submit
    await page.click('button:has-text("Sign Up")');

    // Should show error message
    await expect(page.locator('text=Passwords do not match')).toBeVisible();
  });

  test('should validate password length', async ({ page }) => {
    // Click the "Sign up" link
    await page.click('text=Sign up');

    // Fill in the form with short password
    await page.fill('input#username', 'testuser');
    await page.fill('input#email', 'test@example.com');
    await page.fill('input#password1', 'short');
    await page.fill('input#password2', 'short');

    // Click submit
    await page.click('button:has-text("Sign Up")');

    // Should show error message
    await expect(page.locator('text=Password must be at least 8 characters long')).toBeVisible();
  });

  test('should validate required fields', async ({ page }) => {
    // Click the "Sign up" link
    await page.click('text=Sign up');

    // Try to submit with empty fields
    await page.click('button:has-text("Sign Up")');

    // Should show error message
    await expect(page.locator('text=All fields are required')).toBeVisible();
  });

  test('should allow switching back to login form', async ({ page }) => {
    // Click the "Sign up" link
    await page.click('text=Sign up');

    // Verify we're on registration form
    await expect(page.locator('text=Create Account')).toBeVisible();

    // Click "Sign in" link
    await page.click('text=Sign in');

    // Should be back on login form
    await expect(page.locator('text=Sign in to continue')).toBeVisible();
    await expect(page.locator('button:has-text("Sign In")')).toBeVisible();
  });

  test('should show success message after registration (mock API)', async ({ page }) => {
    // Intercept the signup API call and mock success response
    await page.route('**/api/auth/signup', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Registration successful. Please check your email to verify your account.',
          username: 'testuser',
          email: 'test@example.com',
        }),
      });
    });

    // Click the "Sign up" link
    await page.click('text=Sign up');

    // Fill in valid registration data
    await page.fill('input#username', 'testuser');
    await page.fill('input#email', 'test@example.com');
    await page.fill('input#password1', 'testpassword123');
    await page.fill('input#password2', 'testpassword123');

    // Submit the form
    await page.click('button:has-text("Sign Up")');

    // Wait for success state
    await expect(page.locator('text=Check Your Email')).toBeVisible();
    await expect(page.locator('text=Registration successful!')).toBeVisible();
    await expect(page.locator('text=test@example.com')).toBeVisible();

    // Verify action buttons are present
    await expect(page.locator('button:has-text("Resend Verification Email")')).toBeVisible();
    await expect(page.locator('button:has-text("Back to Login")')).toBeVisible();
  });
});

test.describe('Email Verification', () => {
  test('should handle email verification with valid key', async ({ page }) => {
    // Mock the verify-email API call
    await page.route('**/api/auth/verify-email', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Email verified successfully. You can now log in.',
        }),
      });
    });

    // Navigate to verify-email page with a mock key
    await page.goto('/verify-email?key=mock-verification-key-123');

    // Should show success state
    await expect(page.locator('text=Email Verification')).toBeVisible();
    await expect(page.locator('text=Verification successful')).toBeVisible();
    await expect(page.locator('text=Email verified successfully')).toBeVisible();

    // Should have a button to continue to login
    await expect(page.locator('button:has-text("Continue to Login")')).toBeVisible();
  });

  test('should handle email verification with invalid key', async ({ page }) => {
    // Mock the verify-email API call with error
    await page.route('**/api/auth/verify-email', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Invalid or expired verification key.',
        }),
      });
    });

    // Navigate to verify-email page with invalid key
    await page.goto('/verify-email?key=invalid-key');

    // Should show error state
    await expect(page.locator('text=Email Verification')).toBeVisible();
    await expect(page.locator('text=Verification failed')).toBeVisible();

    // Should have options to resend or go back to login
    await expect(page.locator('button:has-text("Resend Verification Email")')).toBeVisible();
    await expect(page.locator('button:has-text("Back to Login")')).toBeVisible();
  });

  test('should handle missing verification key', async ({ page }) => {
    // Navigate to verify-email page without key parameter
    await page.goto('/verify-email');

    // Should show error state
    await expect(page.locator('text=Verification failed')).toBeVisible();
    await expect(page.locator('text=Invalid verification link. No verification key provided.')).toBeVisible();
  });
});
