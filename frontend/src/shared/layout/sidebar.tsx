import { useAuth } from '../../features/auth/auth-context'
import vertereMark from '../assets/vertere-mark-blue.png'
import {
  BillingIcon,
  ChevronLeftIcon,
  ClinicsIcon,
  DashboardIcon,
  ExamsIcon,
  LaudosIcon,
  OperationIcon,
  PatientsIcon,
  ReportsIcon,
  UserIcon,
  UsersIcon,
} from '../ui/icons'
import { SidebarNavItem, type SidebarNavItemProps } from './sidebar-nav-item'
import './sidebar.css'

interface GatedEntry extends SidebarNavItemProps {
  permission?: string
}

const baseMainNavEntries: SidebarNavItemProps[] = [
  { icon: <DashboardIcon />, label: 'Dashboard', to: '/' },
]

const afterOperationNavEntries: GatedEntry[] = [
  { icon: <LaudosIcon />, label: 'Laudos', to: null },
  { icon: <PatientsIcon />, label: 'Pacientes', to: '/pacientes', permission: 'patients.read' },
]

const registrationNavEntries: GatedEntry[] = [
  { icon: <ClinicsIcon />, label: 'Clínicas', to: '/cadastros/clinicas', permission: 'clinics.read' },
  {
    icon: <UserIcon />,
    label: 'Veterinários',
    to: '/cadastros/veterinarios',
    permission: 'veterinarians.read',
  },
  { icon: <ExamsIcon />, label: 'Exames & Preços', to: '/cadastros/exames', permission: 'catalog.read' },
]


const baseAdminNavEntries: SidebarNavItemProps[] = [
  { icon: <ReportsIcon />, label: 'Relatórios', to: null },
]

function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : ''
  return `${first}${last}`.toUpperCase()
}

interface SidebarProps {
  mobileOpen?: boolean
  collapsed?: boolean
  onToggleCollapsed?: () => void
  onNavigate?: () => void
}

export function Sidebar({
  mobileOpen = false,
  collapsed = false,
  onToggleCollapsed,
  onNavigate,
}: SidebarProps) {
  const { user } = useAuth()
  const permissions = user?.permissions ?? []

  // Item oculto sem a permissão correspondente (não checa nome de papel —
  // regra do domínio: `.claude/rules/01-product-domain.md`). Esconder é UX, a
  // autoridade continua sendo o backend em cada página.
  const adminNavEntries: SidebarNavItemProps[] = [
    ...(permissions.includes('users.read')
      ? [{ icon: <UsersIcon />, label: 'Usuários', to: '/administracao/usuarios' }]
      : []),
    ...baseAdminNavEntries,
  ]

  const financeNavEntries: SidebarNavItemProps[] = [
    ...(permissions.includes('closures.read') || permissions.includes('closures.preview')
      ? [{ icon: <BillingIcon />, label: 'Fechamento', to: '/financeiro/fechamento' }]
      : []),
  ]

  const allowed = (entries: GatedEntry[]): SidebarNavItemProps[] =>
    entries
      .filter((entry) => !entry.permission || permissions.includes(entry.permission))
      .map(({ permission: _permission, ...entry }) => entry)
  const registrationEntries = allowed(registrationNavEntries)

  const mainNavEntries: SidebarNavItemProps[] = [
    ...baseMainNavEntries,
    {
      icon: <OperationIcon />,
      label: 'Operação',
      to: permissions.includes('attendances.read') ? '/operacao' : null,
    },
    ...allowed(afterOperationNavEntries),
  ]

  return (
    <aside
      className={`sidebar${mobileOpen ? ' sidebar--mobile-open' : ''}${collapsed ? ' sidebar--collapsed' : ''}`}
      aria-label="Navegação principal"
      onClick={(event) => {
        if ((event.target as HTMLElement).closest('a')) onNavigate?.()
      }}
    >
      <div className="sidebar__brand">
        <img className="sidebar__brand-mark" src={vertereMark} alt="" />
        <div>
          <div className="sidebar__brand-name">Vertere</div>
          <div className="sidebar__brand-subtitle">Laboratório veterinário</div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {mainNavEntries.map((entry) => (
          <SidebarNavItem
            key={entry.label}
            {...entry}
            title={collapsed ? entry.label : undefined}
          />
        ))}

        {registrationEntries.length > 0 && (
          <>
            <div className="sidebar__section-label">Cadastros</div>
            {registrationEntries.map((entry) => (
              <SidebarNavItem
                key={entry.label}
                {...entry}
                title={collapsed ? entry.label : undefined}
              />
            ))}
          </>
        )}

        {financeNavEntries.length > 0 && (
          <>
            <div className="sidebar__section-label">Financeiro</div>
            {financeNavEntries.map((entry) => (
              <SidebarNavItem
                key={entry.label}
                {...entry}
                title={collapsed ? entry.label : undefined}
              />
            ))}
          </>
        )}

        <div className="sidebar__section-label">Administração</div>
        {adminNavEntries.map((entry) => (
          <SidebarNavItem
            key={entry.label}
            {...entry}
            title={collapsed ? entry.label : undefined}
          />
        ))}
      </nav>

      <button
        type="button"
        className="sidebar__collapse"
        aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
        aria-expanded={!collapsed}
        title={collapsed ? 'Expandir menu' : undefined}
        onClick={onToggleCollapsed}
      >
        <ChevronLeftIcon />
        <span className="sidebar__collapse-label">Recolher menu</span>
      </button>

      {user && (
        <div className="sidebar__footer">
          <div className="sidebar__avatar">{getInitials(user.fullName)}</div>
          <div className="sidebar__footer-info">
            <div className="sidebar__footer-name">{user.fullName}</div>
            <div className="sidebar__footer-role">{user.roleName}</div>
          </div>
        </div>
      )}
    </aside>
  )
}
