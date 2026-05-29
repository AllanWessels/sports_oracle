import { expect, test } from '@playwright/test'
import { mockBackend } from './fixtures'

test.beforeEach(async ({ page }) => {
  await mockBackend(page)
})

test('sends a message and streams a cited answer into a bubble', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('Message input').fill('Tell me about Arsenal')
  await page.getByLabel('Send message').click()

  // The streamed token text lands in an assistant bubble...
  await expect(page.getByTestId('message-content').last()).toContainText(
    'Arsenal play in the Premier League.',
  )
  // ...and the citation from the SSE stream renders in the Sources list.
  await expect(page.getByText('Sources')).toBeVisible()
  await expect(page.getByText('offside.md')).toBeVisible()
})
