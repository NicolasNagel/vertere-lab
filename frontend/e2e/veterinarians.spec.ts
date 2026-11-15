import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const json = (body: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

const LONG_NAME = 'Dra. Maria Fernanda de Albuquerque Cavalcanti Souza Pereira Nogueira Lima'

const veterinarian = {
  id: 'v1',
  name: LONG_NAME,
  crmv: 'CRMV-SP 123456',
  phone: '11987654321',
  email: 'vet@example.com',
  is_autonomous: false,
  status: 'ACTIVE',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
}
const detail = {
  ...veterinarian,
  clinics: [{ clinic_id: 'c1', clinic_name: 'Clínica Central', primary_clinic: true }],
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
}

const LONG_CLINIC = 'Clínica Veterinária Integrada de Pequenos e Grandes Animais do Vale do Itajaí'
const CLINICS = [
  clinic,
  { ...clinic, id: 'c2', name: LONG_CLINIC },
  ...Array.from({ length: 118 }, (_, index) => ({
    ...clinic,
    id: `c${index + 3}`,
    name: `Clínica ${String(index + 3).padStart(3, '0')}`,
  })),
]

type Mode = 'ok' | 'empty' | 'error'

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
    if (path === '/veterinarians/v1') return route.fulfill(json(detail))
    if (path === '/veterinarians') {
      if (mode === 'error') return route.fulfill(json({ error: { code: 'X', message: 'x' } }, 500))
      const items = mode === 'empty' ? [] : [veterinarian]
      return route.fulfill(json({ items, total: items.length, page: 1, page_size: 25 }))
    }
    if (path === '/clinics') {
      const url = new URL(route.request().url())
      const search = (url.searchParams.get('search') ?? '').toLowerCase()
      const pageNumber = Number(url.searchParams.get('page') ?? 1)
      const pageSize = Number(url.searchParams.get('page_size') ?? 20)
      const filtered = CLINICS.filter((item) => item.name.toLowerCase().includes(search))
      return route.fulfill(
        json({
          items: filtered.slice((pageNumber - 1) * pageSize, pageNumber * pageSize),
          total: filtered.length,
          page: pageNumber,
          page_size: pageSize,
        }),
      )
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

const MANAGER = ['veterinarians.read', 'veterinarians.manage']
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'tablet', width: 820, height: 1100 },
  { name: 'mobile', width: 390, height: 800 },
]

for (const viewport of VIEWPORTS) {
  test.describe(`veterinarians (${viewport.name})`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } })

    test('list with a long name is accessible and fits the viewport', async ({ page }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/veterinarios')
      await expect(page.getByRole('heading', { name: 'Veterinários' })).toBeVisible()
      await expect(page.getByText(LONG_NAME).first()).toBeVisible()
      await expectAccessible(page)
    })

    test('row popover is accessible', async ({ page }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/veterinarios')
      await page.getByRole('button', { name: LONG_NAME }).first().click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await expect(page.getByRole('link', { name: 'Abrir veterinário' })).toBeVisible()
      await expectAccessible(page)
    })

    test('detail with blocks and the edit form are accessible', async ({ page }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/veterinarios/v1')
      await expect(page.getByRole('heading', { name: LONG_NAME })).toBeVisible()
      await expectAccessible(page)
      await page.getByRole('button', { name: 'Editar identificação' }).click()
      await expect(page.getByLabel('Motivo da alteração')).toBeVisible()
      await expectAccessible(page)
    })

    test('batch clinic picker with 120 clinics is accessible and fits the viewport', async ({
      page,
    }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/veterinarios/v1')
      await page.getByRole('button', { name: 'Editar clínicas vinculadas' }).click()
      await expect(page.getByRole('group', { name: 'Clínicas disponíveis' })).toBeVisible()
      await expect(page.getByText('1 clínica selecionada')).toBeVisible()
      await expectAccessible(page)
      await page.getByRole('button', { name: 'Selecionar todas (120)' }).click()
      await expect(page.getByText('120 clínicas selecionadas')).toBeVisible()
      await expect(page.getByText('Vincular 119 · Desvincular 0')).toBeVisible()
      await expectAccessible(page)
    })

    test('new veterinarian form is accessible', async ({ page }) => {
      await mockApi(page, MANAGER)
      await page.goto('/cadastros/veterinarios/novo')
      await expect(page.getByRole('heading', { name: 'Novo veterinário' })).toBeVisible()
      await expectAccessible(page)
    })
  })
}

test('empty list shows the empty state and stays accessible', async ({ page }) => {
  await mockApi(page, MANAGER, 'empty')
  await page.goto('/cadastros/veterinarios')
  await expect(page.getByText(/Nenhum veterinário encontrado/)).toBeVisible()
  await expectAccessible(page)
})

test('list error shows an alert and stays accessible', async ({ page }) => {
  await mockApi(page, MANAGER, 'error')
  await page.goto('/cadastros/veterinarios')
  await expect(page.getByRole('alert')).toBeVisible()
  await expectAccessible(page)
})

test('without veterinarians.manage there is no create button, no Editar and the form is blocked', async ({
  page,
}) => {
  await mockApi(page, ['veterinarians.read'])
  await page.goto('/cadastros/veterinarios')
  await expect(page.getByText(LONG_NAME).first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Novo veterinário' })).toHaveCount(0)
  await expectAccessible(page)
  await page.goto('/cadastros/veterinarios/v1')
  await expect(page.getByRole('heading', { name: LONG_NAME })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Editar/ })).toHaveCount(0)
  await page.goto('/cadastros/veterinarios/novo')
  await expect(page.getByText('Você não tem permissão para gerenciar veterinários.')).toBeVisible()
  await expectAccessible(page)
})

test('keyboard: reach the new link and open and close the popover with Escape', async ({
  page,
}) => {
  await mockApi(page, MANAGER)
  await page.goto('/cadastros/veterinarios')
  await expect(page.getByText(LONG_NAME).first()).toBeVisible()
  await page.getByRole('link', { name: 'Novo veterinário' }).focus()
  await expect(page.getByRole('link', { name: 'Novo veterinário' })).toBeFocused()
  await page.getByRole('button', { name: LONG_NAME }).first().focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
