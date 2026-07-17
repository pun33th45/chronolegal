import { test, expect } from '@playwright/test';
import { loginUser } from '../helpers/auth';

test.describe('Analytics Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto('/analytics');
  });

  test('renders all chart sections', async ({ page }) => {
    await expect(page.getByText(/case trends/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/top courts/i)).toBeVisible();
    await expect(page.getByText(/top acts/i)).toBeVisible();
    await expect(page.getByText(/decision types/i)).toBeVisible();
  });

  test('displays total case count stat', async ({ page }) => {
    await expect(page.getByTestId('stat-total-cases')).toBeVisible({ timeout: 10000 });
    const text = await page.getByTestId('stat-total-cases').textContent();
    expect(Number(text?.replace(/,/g, ''))).toBeGreaterThan(0);
  });
});
