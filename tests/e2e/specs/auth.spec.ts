import { test, expect } from '@playwright/test';
import { TEST_USER, loginUser } from '../helpers/auth';

test.describe('Authentication', () => {
  test('landing page loads and shows hero section', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /chronolegal/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /get started/i })).toBeVisible();
  });

  test('register → redirect to dashboard', async ({ page }) => {
    const unique = `test_${Date.now()}@chronolegal.test`;
    await page.goto('/register');
    await page.getByLabel(/full name/i).fill('Test User');
    await page.getByLabel(/email/i).fill(unique);
    await page.getByLabel(/password/i).fill('TestPass123!');
    await page.getByRole('button', { name: /register/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText(/welcome/i)).toBeVisible();
  });

  test('login with valid credentials → dashboard', async ({ page }) => {
    await loginUser(page);
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('login with wrong password → error message', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel(/email/i).fill(TEST_USER.email);
    await page.getByLabel(/password/i).fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByText(/incorrect email or password/i)).toBeVisible();
  });

  test('protected route redirects unauthenticated user to login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });

  test('logout clears session and redirects to login', async ({ page }) => {
    await loginUser(page);
    await page.getByRole('button', { name: /logout/i }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });
});
