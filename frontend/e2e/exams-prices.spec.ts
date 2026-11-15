import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const json = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

const exam = {
  id: 'e1',
  code: 'HEMO',
  name: 'Hemograma completo com contagem diferencial de plaquetas e reticulócitos',
  category_id: 'cat1',
  description: null,
  species_ids: ['s1'],
  status: 'ACTIVE',
  row_version: 1,
  price_base: '100.00',
  price_valid_from: '2026-01-01',
  price_valid_to: null,
  updated_at: '2026-01-01T00:00:00Z',
  is_panel: false,
  component_exam_ids: [],
}

const fee = (level: string, amount: string) => ({
  id: `f-${level}`,
  service_level: level,
  fee_amount: amount,
  schedule_label: 'Fins de semana',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
})

async function mockApi(page: Page, permissions: string[]) {
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    const list = (items: unknown[]) => json({ items, total: items.length, page: 1, page_size: 25 })
    if (path === '/auth/me')
      return route.fulfill(
        json({
          user: {
            id: 'u1',
            email: 'qa@qa.local',
            full_name: 'QA',
            role_id: 'r1',
            role_name: 'LAB_ADMIN',
            role_scope: 'LAB',
            clinic_ids: [],
            row_version: 1,
          },
          permissions,
        }),
      )
    if (path === '/exams/e1') return route.fulfill(json(exam))
    if (path === '/exams') return route.fulfill(list([exam]))
    if (path === '/species')
      return route.fulfill(
        json({ items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }] }),
      )
    if (path === '/exam-categories/active')
      return route.fulfill(
        json({ items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }] }),
      )
    if (path === '/on-call-fee-settings')
      return route.fulfill(
        json({ items: [fee('PLANTAO_NORMAL', '50.00'), fee('PLANTAO_ESPECIAL', '90.00')] }),
      )
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })
}

async function expectAccessible(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(overflow).toBe(false)
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
}

const MANAGER = ['catalog.read', 'catalog.manage', 'pricing.read', 'pricing.manage']

test('exams table with filters is accessible and keeps long names inside the viewport', async ({
  page,
}) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/exames')
  await expect(page.getByRole('heading', { name: 'Exames & Preços' })).toBeVisible()
  await expect(page.getByText(/Hemograma completo com contagem/)).toBeVisible()
  await expect(page.getByRole('button', { name: /Categoria/ })).toBeVisible()
  await expectAccessible(page)
})

test('exam summary popover is accessible', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/exames')
  await page.getByRole('button', { name: /Hemograma completo com contagem/, exact: false }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Editar exame' })).toBeVisible()
  await expectAccessible(page)
})

test('without pricing.read the table shows no price column and stays accessible', async ({
  page,
}) => {
  await mockApi(page, ['catalog.read'])
  await page.goto('/cadastros/exames')
  await expect(page.getByText(/Hemograma completo com contagem/)).toBeVisible()
  await expect(page.getByText('R$ 100,00')).toHaveCount(0)
  await expectAccessible(page)
})

test('on-call fees tab is accessible', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/exames')
  await page.getByRole('tab', { name: 'Taxas de plantão' }).click()
  await expect(page.getByRole('tab', { name: 'Taxas de plantão' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expectAccessible(page)
})

test('exam detail with edit blocks is accessible, also with a block open', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/exames/e1')
  await expect(page.getByRole('button', { name: /^Editar/ }).first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'Resumo do exame' })).toBeVisible()
  await expectAccessible(page)
  await page.setViewportSize({ width: 390, height: 800 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.getByRole('button', { name: /^Editar/ }).first().click()
  await expectAccessible(page)
})

test('exam detail for a read-only price viewer shows no edit buttons', async ({ page }) => {
  await mockApi(page, ['catalog.read', 'pricing.read'])
  await page.goto('/cadastros/exames/e1')
  await expect(page.getByText('HEMO').first()).toBeVisible()
  await expect(page.getByRole('button', { name: /^Editar/ })).toHaveCount(0)
  await expectAccessible(page)
})

test('new exam and new panel forms are accessible and fit the viewport', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/exames/novo')
  await expect(page.getByRole('heading', { name: 'Novo exame' })).toBeVisible()
  await expectAccessible(page)
  await page.goto('/cadastros/exames/novo-pacote')
  await expect(page.getByRole('heading', { name: 'Novo pacote' })).toBeVisible()
  await expectAccessible(page)
})
