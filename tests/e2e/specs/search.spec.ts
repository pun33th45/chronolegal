import { test, expect } from '@playwright/test';
import { loginUser } from '../helpers/auth';

test.describe('Search', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto('/search');
  });

  test('search page renders with input', async ({ page }) => {
    await expect(page.getByPlaceholder(/search legal cases/i)).toBeVisible();
  });

  test('typing query shows results', async ({ page }) => {
    await page.getByPlaceholder(/search legal cases/i).fill('fundamental rights');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('search-result-card')).toHaveCount.callsFake
      ? undefined
      : await expect(page.locator('[data-testid="search-result-card"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('filter by court narrows results', async ({ page }) => {
    await page.getByPlaceholder(/search legal cases/i).fill('privacy');
    await page.keyboard.press('Enter');
    await page.waitForSelector('[data-testid="search-result-card"]', { timeout: 10000 });

    await page.getByLabel(/court/i).selectOption('Supreme Court of India');
    await page.keyboard.press('Enter');

    const results = page.locator('[data-testid="search-result-card"]');
    await expect(results.first()).toBeVisible({ timeout: 10000 });
  });

  test('clicking result opens case viewer', async ({ page }) => {
    await page.getByPlaceholder(/search legal cases/i).fill('kesavananda bharati');
    await page.keyboard.press('Enter');
    await page.locator('[data-testid="search-result-card"]').first().click();
    await expect(page).toHaveURL(/\/cases\//);
  });

  test('empty query shows placeholder text', async ({ page }) => {
    await expect(page.getByText(/enter a query to search/i)).toBeVisible();
  });
});
