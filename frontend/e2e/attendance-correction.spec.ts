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

const attendance = {
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

async function expectAccessible(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(overflow).toBe(false)
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
}

test('attendance detail and each block editor are accessible and fit the viewport', async ({
  page,
}) => {
  await mockApi(page)
  await page.goto('/operacao/a1')
  await expect(page.getByRole('heading', { name: 'P000001/26' })).toBeVisible()
  await expectAccessible(page)

  for (const block of ['solicitante', 'paciente', 'atendimento', 'observações']) {
    await page.getByRole('button', { name: `Editar ${block}`, exact: true }).click()
    await expect(page.getByLabel('Motivo da alteração')).toBeVisible()
    await expectAccessible(page)
    await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
  }

  await page.getByRole('button', { name: 'Editar exames', exact: true }).click()
  await expect(page.getByRole('checkbox', { name: /Hemograma/ })).toBeChecked()
  await expect(page.getByText(/R\$\s*90,00/).first()).toBeVisible()
  await expectAccessible(page)
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click()

  await page.getByRole('button', { name: 'Corrigir cadastro' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expectAccessible(page)
})
