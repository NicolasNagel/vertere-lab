import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const CLOSURE_ID = '11111111-1111-4111-8111-111111111111'
const CLINIC_ID = '22222222-2222-4222-8222-222222222222'

const closure = {
  id: CLOSURE_ID,
  clinic_id: CLINIC_ID,
  competence_year: 2026,
  competence_month: 7,
  period_start: '2026-07-01',
  period_end: '2026-07-31',
  status: 'CLOSED',
  item_count: 1,
  subtotal: '100.00',
  discount_total: '0.00',
  surcharge_total: '0.00',
  grand_total: '100.00',
  generated_by: null,
  closed_by: null,
  generated_at: '2026-07-31T12:00:00Z',
  closed_at: '2026-07-31T12:00:00Z',
  reopened_at: null,
  version: 1,
  items: [
    {
      id: '33333333-3333-4333-8333-333333333333',
      attendance_id: '44444444-4444-4444-8444-444444444444',
      attendance_exam_id: '55555555-5555-4555-8555-555555555555',
      protocol_number: '2026/000001',
      patient_name: 'Paciente com um nome excepcionalmente longo para validar o layout',
      exam_name: 'Hemograma completo',
      price_base: '100.00',
      quantity: 1,
      discount_amount: '0.00',
      surcharge_amount: '0.00',
      total_amount: '100.00',
    },
  ],
  adjustments: [],
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user: {
          id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          email: 'finance@qa.local',
          full_name: 'QA Financeiro',
          role_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
          role_name: 'FINANCE',
        },
        permissions: ['closures.read', 'closures.adjust', 'closures.reopen'],
      }),
    }),
  )
  await page.route(`**/api/v1/closures/${CLOSURE_ID}`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(closure) }),
  )
  await page.route(`**/api/v1/clinics/${CLINIC_ID}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: CLINIC_ID,
        name: 'Clínica QA',
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
      }),
    }),
  )
})

test('financial adjustment modal validates, submits once and remains accessible', async ({
  page,
}) => {
  let requests = 0
  await page.route(`**/api/v1/closures/${CLOSURE_ID}/adjustments`, async (route) => {
    requests += 1
    await new Promise((resolve) => setTimeout(resolve, 250))
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        id: '66666666-6666-4666-8666-666666666666',
        monthly_closure_id: CLOSURE_ID,
        monthly_closure_item_id: null,
        kind: 'DEBIT',
        amount: '12.50',
        reason: 'Correção financeira autorizada.',
        created_by: null,
        created_at: '2026-07-31T13:00:00Z',
      }),
    })
  })

  await page.goto(`/financeiro/fechamentos/${CLOSURE_ID}`)
  await page.getByRole('button', { name: 'Adicionar ajuste' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByLabel('Valor')).toBeFocused()

  const confirm = page
    .getByRole('dialog')
    .getByRole('button', { name: 'Adicionar ajuste', exact: true })
  await expect(confirm).toBeDisabled()
  await page.getByLabel('Valor').fill('-1')
  await page.getByLabel('Justificativa').fill('curta')
  await expect(confirm).toBeDisabled()
  await page.getByLabel('Valor').fill('12,50')
  await page.getByLabel('Justificativa').fill('Correção financeira autorizada.')
  await expect(confirm).toBeEnabled()
  await confirm.dblclick()
  await expect(page.getByRole('dialog')).toBeHidden()
  expect(requests).toBe(1)

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(hasHorizontalOverflow).toBe(false)
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
})
