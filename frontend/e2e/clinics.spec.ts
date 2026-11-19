import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const json = (body: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

const LONG_NAME = 'Clínica Veterinária Parceira do Vale com Nome Extremamente Longo Ltda'

const clinic = {
  id: 'c1',
  name: LONG_NAME,
  tax_id: '12345678000199',
  phone: '11987654321',
  email: 'contato@alfa.example.com',
  status: 'ACTIVE',
  address_zip_code: '01001000',
  address_street: 'Praça da Sé',
  address_number: '10',
  address_neighborhood: 'Sé',
  address_city: 'São Paulo',
  address_state: 'SP',
  address_complement: null,
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
  veterinarians: [
    { veterinarian_id: 'v1', veterinarian_name: 'Dra. Ana', crmv: 'CRMV-SP 1234', primary_clinic: true },
  ],
}

const clinicWithManyVets = {
  ...clinic,
  veterinarians: Array.from({ length: 20 }, (_, index) => ({
    veterinarian_id: `v${index}`,
    veterinarian_name: `Dra. Veterinária ${String(index).padStart(2, '0')}`,
    crmv: `CRMV-SP ${1000 + index}`,
    primary_clinic: index === 0,
  })),
}

type Mode = 'ok' | 'empty' | 'error' | 'manyVets'

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
    if (path === '/clinics/c1')
      return route.fulfill(json(mode === 'manyVets' ? clinicWithManyVets : clinic))
    if (path === '/clinics') {
      if (mode === 'error') return route.fulfill(json({ error: { code: 'X', message: 'x' } }, 500))
      const items = mode === 'empty' ? [] : [clinic]
      return route.fulfill(json({ items, total: items.length, page: 1, page_size: 25 }))
    }
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

const MANAGER = ['clinics.read', 'clinics.manage']
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'tablet', width: 820, height: 1100 },
  { name: 'mobile', width: 390, height: 800 },
]

for (const viewport of VIEWPORTS) {
  test.describe(`clinics (${viewport.name})`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } })

    test('list with a long name is accessible and fits the viewport', async ({ page }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/clinicas')
      await expect(page.getByRole('heading', { name: 'Clínicas parceiras' })).toBeVisible()
      await expect(page.getByText(LONG_NAME).first()).toBeVisible()
      await expectAccessible(page)
    })

    test('row popover is accessible', async ({ page }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/clinicas')
      await page.getByRole('button', { name: LONG_NAME }).first().click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await expect(page.getByRole('complementary', { name: 'Detalhes da clínica' })).toBeVisible()
      await expectAccessible(page)
    })

    test('popover with 20 veterinarians shows a preview and a bounded, searchable full list', async ({
      page,
    }) => {
      await mockApi(page, MANAGER, 'manyVets')
      await page.goto('/cadastros/clinicas')
      await page.getByRole('button', { name: LONG_NAME }).first().click()
      const popover = page.getByRole('complementary', { name: 'Detalhes da clínica' })
      await expect(popover.getByRole('listitem')).toHaveCount(5)
      await expectAccessible(page)

      await popover.getByRole('button', { name: 'Ver todos (20)' }).click()
      const list = popover.getByRole('list', { name: 'Veterinários vinculados' })
      await expect(list.getByRole('listitem')).toHaveCount(20)
      const box = await list.boundingBox()
      expect(box?.height ?? 0).toBeLessThanOrEqual(260)
      await expectAccessible(page)

      await popover.getByLabel('Buscar veterinário vinculado').fill('veterinária 07')
      await expect(list.getByRole('listitem')).toHaveCount(1)
      await expectAccessible(page)
    })

    test('new and edit clinic forms are accessible', async ({ page }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/clinicas/nova')
      await expect(page.getByRole('heading', { name: 'Nova clínica' })).toBeVisible()
      await expectAccessible(page)
      await page.goto('/cadastros/clinicas/c1/editar')
      await expect(page.getByRole('heading', { name: 'Editar clínica' })).toBeVisible()
      await expect(page.getByLabel('Nome da clínica')).toHaveValue(LONG_NAME)
      await expectAccessible(page)
    })
  })
}

test('empty list shows the empty state and stays accessible', async ({ page }) => {
  await mockApi(page, MANAGER, 'empty')
  await page.goto('/cadastros/clinicas')
  await expect(page.getByText(/Nenhuma clínica/)).toBeVisible()
  await expectAccessible(page)
})

test('list error shows an alert and stays accessible', async ({ page }) => {
  await mockApi(page, MANAGER, 'error')
  await page.goto('/cadastros/clinicas')
  await expect(page.getByRole('alert')).toBeVisible()
  await expectAccessible(page)
})

test('without clinics.manage there is no create button and the form is blocked', async ({ page }) => {
  await mockApi(page, ['clinics.read'])
  await page.goto('/cadastros/clinicas')
  await expect(page.getByText(LONG_NAME).first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Nova clínica' })).toHaveCount(0)
  await expectAccessible(page)
  await page.goto('/cadastros/clinicas/nova')
  await expect(page.getByText('Você não tem permissão para gerenciar clínicas.')).toBeVisible()
  await expectAccessible(page)
})

test('keyboard: reach the new-clinic link and open and close the popover with Escape', async ({
  page,
}) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/clinicas')
  await expect(page.getByText(LONG_NAME).first()).toBeVisible()
  await page.getByRole('link', { name: 'Nova clínica' }).focus()
  await expect(page.getByRole('link', { name: 'Nova clínica' })).toBeFocused()
  await page.getByRole('button', { name: LONG_NAME }).first().focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
