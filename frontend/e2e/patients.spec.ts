import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const json = (body: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

const LONG_NAME = 'Sir Bartholomew Maximilian von Hohenzollern de la Cruz Segundo'
const LONG_OWNER = 'Maria Fernanda de Albuquerque Cavalcanti Souza Pereira Nogueira Lima'

const patient = {
  id: 'p1',
  clinic_id: 'c1',
  name: 'Bidu',
  species_id: 's1',
  sex: 'MALE',
  breed: 'SRD',
  age_value: 3,
  age_unit: 'YEARS',
  age_description: '3 anos',
  age_recorded_on: null,
  owner_name: 'Maria Souza',
  owner_phone: '(47) 99999-0000',
  owner_document: null,
  status: 'ACTIVE',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
}
const PATIENTS = [
  patient,
  { ...patient, id: 'p2', name: LONG_NAME, owner_name: LONG_OWNER, species_id: 's2' },
  { ...patient, id: 'p3', name: 'Mimi', status: 'INACTIVE', species_id: 's2' },
]

type Mode = 'ok' | 'empty' | 'error' | 'forbidden'

async function mockApi(page: Page, permissions: string[], mode: Mode = 'ok') {
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
          permissions,
        }),
      )
    if (path === '/patients/summary')
      return route.fulfill(json({ total: PATIENTS.length, active: 2, inactive: 1 }))
    if (path === '/patients/p1') return route.fulfill(json(patient))
    if (path === '/patients') {
      if (mode === 'error') return route.fulfill(json({ error: { code: 'X', message: 'x' } }, 500))
      if (mode === 'forbidden')
        return route.fulfill(json({ error: { code: 'FORBIDDEN', message: 'x' } }, 403))
      const items = mode === 'empty' ? [] : PATIENTS
      return route.fulfill(json({ items, total: items.length, page: 1, page_size: 25 }))
    }
    if (path === '/clinics')
      return route.fulfill(
        json({
          items: [{ id: 'c1', name: 'Clínica Central', status: 'ACTIVE' }],
          total: 1,
          page: 1,
          page_size: 100,
        }),
      )
    if (path === '/species')
      return route.fulfill(
        json({
          items: [
            { id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' },
            { id: 's2', name: 'Felino', created_at: '2026-01-01T00:00:00Z' },
          ],
        }),
      )
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })
}

async function expectAccessible(page: Page, options: { portaledPopup?: boolean } = {}) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(overflow).toBe(false)
  // O menu do Dropdown vai por portal para o <body> (para não ser cortado por overflow); aberto,
  // ele fica fora dos landmarks por construção e é um listbox nomeado, não conteúdo de página.
  const builder = new AxeBuilder({ page })
  if (options.portaledPopup) builder.disableRules(['region'])
  const violations = (await builder.analyze()).violations
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
}

const MANAGER = ['patients.read', 'patients.manage']

test('list with long names is accessible and fits the viewport', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/pacientes')
  await expect(page.getByRole('heading', { name: 'Pacientes' })).toBeVisible()
  await expect(page.getByRole('button', { name: LONG_NAME, exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Resumo dos pacientes' })).toBeVisible()
  await expectAccessible(page)
})

test('row popover is accessible and links to the patient page', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/pacientes')
  await page.getByRole('button', { name: 'Bidu', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Resumo do paciente' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Abrir paciente' })).toHaveAttribute(
    'href',
    '/pacientes/p1',
  )
  await expectAccessible(page)
})

test('filter dropdowns open accessibly', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/pacientes')
  await page.getByRole('button', { name: /^Espécie/ }).click()
  await expect(page.getByRole('listbox', { name: 'Espécie' })).toBeVisible()
  await expectAccessible(page, { portaledPopup: true })
})

for (const mode of ['empty', 'error', 'forbidden'] as const) {
  test(`${mode} state is announced and accessible`, async ({ page }) => {
    await mockApi(page, MANAGER, mode)
    await page.goto('/pacientes')
    if (mode === 'empty') {
      await expect(
        page.getByText('Nenhum paciente encontrado para os filtros selecionados.'),
      ).toBeVisible()
    } else {
      await expect(page.getByRole('alert')).toContainText(
        mode === 'error'
          ? 'Não foi possível carregar os pacientes.'
          : 'Você não tem permissão para ver pacientes.',
      )
    }
    await expectAccessible(page)
  })
}

test('without patients.manage there is no create button and the form is blocked', async ({
  page,
}) => {
  await mockApi(page, ['patients.read'])
  await page.goto('/pacientes')
  await expect(page.getByRole('button', { name: 'Bidu', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /Novo paciente/ })).toHaveCount(0)
  await page.goto('/pacientes/novo')
  await expect(page.getByRole('alert')).toContainText('não tem permissão')
})

test('new patient page is usable and accessible at every viewport', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/pacientes/novo')
  await expect(page.getByRole('heading', { name: 'Novo paciente' })).toBeVisible()
  // QA 2026-11-19: on mobile this form used to be squeezed to about 70px of width.
  const box = await page.getByLabel('Nome do paciente').boundingBox()
  expect(box?.width ?? 0).toBeGreaterThan(120)
  await expectAccessible(page)
})

test('patient page is accessible and fits the viewport', async ({ page }) => {
  await mockApi(page, MANAGER)
  await page.goto('/pacientes/p1')
  await expect(page.getByRole('heading', { name: 'Bidu' })).toBeVisible()
  await expectAccessible(page)
})
