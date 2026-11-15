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
  schedule_label: 'Fim de semana · 18h às 07h',
  weekdays: [5, 6],
  start_time: '18:00:00',
  end_time: '07:00:00',
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
    if (path === '/urgency-fee-setting')
      return route.fulfill(
        json({
          id: 'u',
          fee_amount: '30.00',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        }),
      )
    if (path === '/clinics')
      return route.fulfill(
        json({
          items: [{ id: 'c1', name: 'Clínica Alfa', status: 'ACTIVE', row_version: 1 }],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      )
    if (path === '/clinic-fee-rules')
      return route.fulfill(
        json({
          items: [
            {
              id: 'r1',
              clinic_id: 'c1',
              name: 'Taxa de coleta',
              fee_amount: '5.00',
              valid_from: '2026-01-01',
              valid_to: null,
              is_active: true,
              exam_ids: ['e1'],
              attendance_types: ['URGENTE'],
              updated_at: '2026-01-01T00:00:00Z',
              row_version: 1,
            },
          ],
        }),
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
  await expect(page.getByRole('link', { name: 'Abrir exame' })).toBeVisible()
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

test('fees tab and its three registers and dialogs are accessible', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/exames')
  await page.getByRole('tab', { name: 'Plantão', exact: true }).click()
  await expect(page.getByRole('tab', { name: 'Plantão', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByText('R$ 50,00')).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Dias' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Horário' })).toBeVisible()
  await expect(page.getByText('18h às 07h').first()).toBeVisible()
  await expectAccessible(page)

  // Clicar na linha abre o resumo; "Editar taxa" leva ao formulário.
  await page.getByRole('button', { name: 'Plantão normal', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expectAccessible(page)
  await page.getByRole('button', { name: 'Editar taxa' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sábado' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Seg-Sex' }).click()
  await expect(page.getByRole('button', { name: 'Segunda-feira' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByText(/vira a meia-noite/)).toBeVisible()
  await expectAccessible(page)
  await page.setViewportSize({ width: 390, height: 800 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.keyboard.press('Escape')

  await page.getByRole('tab', { name: 'Urgência' }).click()
  await expect(page.getByText('R$ 30,00')).toBeVisible()
  await expectAccessible(page)
  await page.getByRole('button', { name: 'Ações para Urgência' }).click()
  await page.getByRole('menuitem', { name: 'Editar taxa' }).click()
  await expect(page.getByLabel('Valor da taxa (R$)')).toBeVisible()
  await expect(page.getByLabel('Horário de início')).toHaveCount(0)
  await expectAccessible(page)
  await page.keyboard.press('Escape')

  await page.getByRole('tab', { name: 'Por clínica' }).click()
  await expect(page.getByText('Taxa de coleta')).toBeVisible()
  await expect(page.getByText(/ · Urgente$/)).toBeVisible()
  await expectAccessible(page)
  await page.getByRole('button', { name: 'Taxa de coleta', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expectAccessible(page)
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: /nova taxa/i }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Urgente', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Urgente', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expectAccessible(page)
  await page.setViewportSize({ width: 390, height: 800 })
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
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
