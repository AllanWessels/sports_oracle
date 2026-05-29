import { expect, test } from '@playwright/test'
import { mockBackend } from './fixtures'

test.beforeEach(async ({ page }) => {
  await mockBackend(page)
})

test('navigates from chat to the routing dashboard and renders live data', async ({ page }) => {
  await page.goto('/')

  // Real navigation: click the sidebar link, not a direct goto.
  await page.getByRole('link', { name: /Routing dashboard/i }).click()

  await expect(page).toHaveURL(/\/dashboard\/routing$/)
  await expect(page.getByText('LangGraph Routing')).toBeVisible()

  // Values from the mocked /metrics/routing payload actually rendered.
  await expect(page.getByTestId('stat-Total turns')).toHaveText('5')
  await expect(page.getByTestId('stat-Cache hit rate')).toHaveText('20%')
  await expect(page.getByTestId('route-factual')).toContainText('3')
  await expect(page.getByTestId('route-prediction')).toBeVisible()
})

test('navigates routing -> eval via the dashboard nav and shows RAGAS scores', async ({ page }) => {
  await page.goto('/dashboard/routing')

  await page.getByRole('link', { name: 'Evaluation' }).click()

  await expect(page).toHaveURL(/\/dashboard\/eval$/)
  await expect(page.getByTestId('score-Faithfulness')).toHaveText('80%')
  await expect(page.getByTestId('score-Citation valid')).toHaveText('50%')
  await expect(page.getByTestId('judged')).toHaveText('2')
  // recent-traces table populated from /metrics/traces
  await expect(page.getByTestId('trace-row')).toContainText('offside?')
})
