import { test, expect } from '@playwright/test'

test('dashboard loads hotspots', async ({ page }) => {
  await page.goto('/#/dashboard')
  await expect(page.locator('h1')).toContainText('AI 热点')
})
