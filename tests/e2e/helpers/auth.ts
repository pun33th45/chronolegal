import { Page, expect } from '@playwright/test';

export const TEST_USER = {
  email: 'e2e_user@chronolegal.test',
  password: 'TestPass123!',
  name: 'E2E Tester',
};

export const ADMIN_USER = {
  email: 'e2e_admin@chronolegal.test',
  password: 'AdminPass123!',
  name: 'E2E Admin',
};

export async function registerUser(page: Page, user = TEST_USER) {
  await page.goto('/register');
  await page.getByLabel('Full Name').fill(user.name);
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: /register/i }).click();
  await expect(page).toHaveURL('/dashboard');
}

export async function loginUser(page: Page, user = TEST_USER) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL('/dashboard');
}

export async function apiLogin(baseURL: string, user = TEST_USER): Promise<string> {
  const res = await fetch(`${baseURL.replace('5173', '8000')}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: user.email, password: user.password }),
  });
  const data = await res.json();
  return data.access_token;
}
