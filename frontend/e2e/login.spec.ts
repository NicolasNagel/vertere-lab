import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'UNAUTHENTICATED',
          message: 'Sessão não encontrada.',
          request_id: 'e2e',
          details: [],
        },
      }),
    })
  })
})

test('login is accessible, keyboard operable and has no horizontal overflow', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await page.goto('/login')
  const login = page.getByLabel('Usuário')
  const password = page.getByLabel('Senha', { exact: true })
  const submit = page.getByRole('button', { name: 'Entrar' })

  await expect(login).toBeVisible()
  await login.focus()
  await page.keyboard.type('admin@example.test')
  await page.keyboard.press('Tab')
  await expect(password).toBeFocused()
  await page.keyboard.type('senha-invalida')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await expect(submit).toBeFocused()

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(hasHorizontalOverflow).toBe(false)
  expect(
    consoleErrors.filter(
      (message) => !message.includes('server responded with a status of 401 (Unauthorized)'),
    ),
  ).toEqual([])

  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations).toEqual([])
})
