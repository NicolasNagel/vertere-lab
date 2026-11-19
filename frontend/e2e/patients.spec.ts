import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const json = (body: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

const patient = {
  id: 'p1',
  clinic_id: 'c1',
  name: 'Bidu',
  species_id: 's1',
  sex: 'MALE',
  breed: null,
  age_value: 3,
  age_unit: 'YEARS',
  age_description: '3 anos',
  age_recorded_on: null,
  owner_name: 'Maria Souza',
  owner_phone: null,
  owner_document: null,
  status: 'ACTIVE',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
}

async function mockApi(page: Page, options: { listStatus?: number } = {}) {
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
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
          permissions: ['patients.read', 'patients.manage'],
        }),
      )
    if (path === '/patients') {
      if (options.listStatus && options.listStatus >= 400) return route.fulfill(json({}, options.listStatus))
      return route.fulfill(json({ items: [patient], total: 1, page: 1, page_size: 20 }))
    }
    if (path === '/patients/p1') return route.fulfill(json(patient))
    if (path === '/clinics')
      return route.fulfill(
        json({ items: [{ id: 'c1', name: 'Clínica Central', status: 'ACTIVE' }], total: 1, page: 1, page_size: 100 }),
      )
    if (path === '/species')
      return route.fulfill(
        json({ items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }] }),
      )
    return route.fulfill(json({}, 404))
  })
}

async function expectAccessible(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(overflow).toBe(false)
  const violations = (await new AxeBuilder({ page }).analyze()).violations
  expect(violations.map((v) => v.id)).toEqual([])
}

test('patients list is accessible and fits the viewport', async ({ page }) => {
  await mockApi(page)
  await page.goto('/pacientes')
  await expect(page.getByText('Bidu')).toBeVisible()
  await expectAccessible(page)
})

test('"Novo paciente" opens a form that is actually usable at every viewport', async ({ page }) => {
  await mockApi(page)
  await page.goto('/pacientes')
  await page.getByRole('button', { name: /Novo paciente/ }).click()

  // QA 2026-11-19: on mobile the list kept a fixed 380px column and squeezed the form to ~70px.
  const field = page.getByLabel('Nome do paciente')
  await expect(field).toBeVisible()
  const box = await field.boundingBox()
  expect(box?.width ?? 0).toBeGreaterThan(120)
  await expectAccessible(page)
})

test('a failing list request shows an error, not the empty state', async ({ page }) => {
  await mockApi(page, { listStatus: 500 })
  await page.goto('/pacientes')
  await expect(page.getByRole('alert')).toContainText('Não foi possível carregar os pacientes.')
  await expect(page.getByText('Nenhum paciente encontrado.')).toHaveCount(0)
})
