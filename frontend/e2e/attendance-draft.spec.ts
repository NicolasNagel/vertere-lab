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
  name: 'Hemograma',
  category_id: 'cat1',
  description: null,
  species_ids: ['s1'],
  status: 'ACTIVE',
  row_version: 1,
  price_base: '100.00',
  updated_at: '2026-01-01T00:00:00Z',
  is_panel: false,
  component_exam_ids: [],
}

const confirmedAttendance = {
  id: 'a1',
  clinic_id: 'c1',
  veterinarian_id: 'v1',
  patient_id: 'p1',
  collection_method: 'INTERNAL',
  service_level: 'NORMAL',
  service_date: '2026-01-05',
  notes: 'Coleta em jejum',
  status: 'CONFIRMED',
  items: [
    {
      id: 'i1',
      exam_id: 'e1',
      exam_code: 'HEMO',
      exam_name: 'Hemograma',
      price_base: '90.00',
      components: [],
      quantity: 1,
      discount_amount: '0.00',
      surcharge_amount: '0.00',
      total_amount: '90.00',
      override_reason: null,
      status: 'ACTIVE',
    },
  ],
  billing_competence: '2026-01-01',
  subtotal: '90.00',
  discount_total: '0.00',
  surcharge_total: '0.00',
  on_call_fee: '0.00',
  grand_total: '90.00',
  protocol_number: 'P000001/26',
  cancel_reason: null,
  created_at: '2026-01-05T10:00:00Z',
  updated_at: '2026-01-05T10:00:00Z',
  row_version: 2,
}

const clinic = {
  id: 'c1',
  name: 'Clínica Central',
  tax_id: null,
  phone: null,
  email: null,
  status: 'ACTIVE',
  address_zip_code: null,
  address_street: null,
  address_number: null,
  address_neighborhood: null,
  address_city: null,
  address_state: null,
  address_complement: null,
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
  veterinarians: [],
}

const veterinarian = {
  id: 'v1',
  name: 'Dra. Ana',
  crmv: 'CRMV-SC 0001',
  phone: null,
  email: null,
  is_autonomous: true,
  status: 'ACTIVE',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
  clinics: [],
}

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
  owner_name: 'Maria Souza',
  owner_phone: null,
  owner_document: null,
  status: 'ACTIVE',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
}

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    const list = (items: unknown[]) => json({ items, total: items.length, page: 1, page_size: 100 })
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
          permissions: [
            'attendances.read',
            'attendances.create',
            'attendances.update',
            'attendances.cancel',
            'attendances.override_price',
            'pricing.read',
            'patients.manage',
          ],
        }),
      )
    if (path === '/attendances/drafts') return route.fulfill(json(attendance))
    if (path === '/attendances/a1') return route.fulfill(json(attendance))
    if (path === '/attendances/a1/timeline') return route.fulfill(list([]))
    if (path === '/clinics/c1') return route.fulfill(json(clinic))
    if (path === '/clinics') return route.fulfill(list([clinic]))
    if (path === '/veterinarians/v1') return route.fulfill(json(veterinarian))
    if (path === '/veterinarians') return route.fulfill(list([veterinarian]))
    if (path === '/patients/p1') return route.fulfill(json(patient))
    if (path === '/patients') return route.fulfill(list([patient]))
    if (path === '/species')
      return route.fulfill(
        json({ items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }] }),
      )
    if (path === '/exams/e1') return route.fulfill(json(exam))
    if (path === '/exams') return route.fulfill(list([exam]))
    if (path === '/exam-categories/active')
      return route.fulfill(
        json({ items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }] }),
      )
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })
}


const attendance = {
  ...confirmedAttendance,
  status: 'DRAFT',
  protocol_number: null,
  items: [],
  billing_competence: null,
  subtotal: '0.00',
  grand_total: '0.00',
}

async function expectAccessible(page: Page, options: { portaledPopup?: boolean } = {}) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(overflow).toBe(false)
  // O menu do Dropdown vai por portal para o <body> (para não ser cortado por overflow). Um popup
  // aberto fica fora dos landmarks por construção; ele é um listbox nomeado, não conteúdo de página.
  const builder = new AxeBuilder({ page })
  if (options.portaledPopup) builder.disableRules(['region'])
  const v = (await builder.analyze()).violations
  expect(v.map((x) => `${x.id}: ${x.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
}

test('new protocol asks for clinic, veterinarian and patient before listing exams', async ({
  page,
}) => {
  await mockApi(page)
  await page.goto('/operacao/novo')
  await expect(page.getByRole('heading', { name: 'Exames' })).toBeVisible()
  await expect(
    page.getByText('Para marcar exames, falta informar: clínica, veterinário, paciente.'),
  ).toBeVisible()
  await expect(page.getByRole('checkbox', { name: /Hemograma/ })).toHaveCount(0)
  await expectAccessible(page)
})

test('resumed draft shows the exam grid and stays accessible', async ({ page }) => {
  await mockApi(page)
  await page.goto('/operacao/a1')
  await expect(page.getByRole('checkbox', { name: /Hemograma/ })).toBeVisible()
  await page.getByRole('checkbox', { name: /Hemograma/ }).focus()
  await expectAccessible(page)
})

async function pickOption(page: Page, field: string, option: string) {
  await page.getByRole('button', { name: new RegExp(field) }).click()
  await expect(page.getByRole('listbox', { name: field })).toBeVisible()
  await expectAccessible(page, { portaledPopup: true })
  await page.getByRole('option', { name: option }).click()
}

test('filled new protocol keeps dropdowns, exam grid and summary bar accessible', async ({
  page,
}) => {
  await mockApi(page)
  await page.goto('/operacao/novo')
  await pickOption(page, 'Clínica solicitante', 'Clínica Central')
  await pickOption(page, 'Veterinário responsável', 'Dra. Ana')
  await page.getByRole('button', { name: '+ buscar do histórico' }).click()
  await page.getByRole('textbox', { name: 'Paciente', exact: true }).fill('Bidu')
  await expect(page.getByRole('option', { name: /Bidu/ })).toBeVisible()
  await expectAccessible(page)
  await page.getByRole('option', { name: /Bidu/ }).click()

  const hemograma = page.getByRole('checkbox', { name: /Hemograma/ })
  await expect(hemograma).toBeVisible()
  await page.locator('label', { has: hemograma }).click()
  await expect(hemograma).toBeChecked()
  await expect(page.getByRole('region', { name: 'Resumo do protocolo' })).toBeVisible()
  await expectAccessible(page)
})
