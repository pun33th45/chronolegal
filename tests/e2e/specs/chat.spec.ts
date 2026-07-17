import { test, expect } from '@playwright/test';
import { loginUser } from '../helpers/auth';

test.describe('Chat / RAG Q&A', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page);
    await page.goto('/chat');
  });

  test('chat page loads with empty state', async ({ page }) => {
    await expect(page.getByPlaceholder(/ask a legal question/i)).toBeVisible();
  });

  test('submitting a question shows streaming response', async ({ page }) => {
    const input = page.getByPlaceholder(/ask a legal question/i);
    await input.fill('What is the basic structure doctrine?');
    await page.keyboard.press('Enter');

    // Streaming indicator
    await expect(page.getByTestId('streaming-indicator')).toBeVisible({ timeout: 5000 });

    // Answer appears
    await expect(page.getByTestId('assistant-message')).toBeVisible({ timeout: 30000 });
    const answer = await page.getByTestId('assistant-message').first().textContent();
    expect(answer?.length).toBeGreaterThan(50);
  });

  test('answer includes citations', async ({ page }) => {
    await page.getByPlaceholder(/ask a legal question/i).fill('Explain Maneka Gandhi judgment');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('citation-card')).toBeVisible({ timeout: 30000 });
  });

  test('new conversation button resets chat', async ({ page }) => {
    await page.getByPlaceholder(/ask a legal question/i).fill('What is Article 21?');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('assistant-message')).toBeVisible({ timeout: 30000 });

    await page.getByRole('button', { name: /new chat/i }).click();
    await expect(page.getByTestId('assistant-message')).toHaveCount(0);
  });

  test('conversation is saved in sidebar', async ({ page }) => {
    await page.getByPlaceholder(/ask a legal question/i).fill('Brief history of Indian constitution');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('assistant-message')).toBeVisible({ timeout: 30000 });

    const sidebarConversations = page.locator('[data-testid="conversation-item"]');
    await expect(sidebarConversations.first()).toBeVisible({ timeout: 5000 });
  });

  test('keyboard shortcut Ctrl+Enter submits message', async ({ page }) => {
    await page.getByPlaceholder(/ask a legal question/i).fill('What is habeas corpus?');
    await page.keyboard.press('Control+Enter');
    await expect(page.getByTestId('assistant-message')).toBeVisible({ timeout: 30000 });
  });
});
