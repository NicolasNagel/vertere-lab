import { useAuth } from '../../features/auth/auth-provider'
import vertereMark from '../assets/vertere-mark.png'
import {
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

const mainNavEntries: SidebarNavItemProps[] = [
  { icon: <DashboardIcon />, label: 'Dashboard', to: '/' },
  { icon: <OperationIcon />, label: 'Operação', to: null },
  { icon: <LaudosIcon />, label: 'Laudos', to: null },
  { icon: <PatientsIcon />, label: 'Pacientes', to: null },
]

const registrationNavEntries: SidebarNavItemProps[] = [
  { icon: <ClinicsIcon />, label: 'Clínicas', to: '/cadastros/clinicas' },
  { icon: <UserIcon />, label: 'Veterinários', to: '/cadastros/veterinarios' },
  { icon: <ExamsIcon />, label: 'Exames & Preços', to: null },
]

const adminNavEntries: SidebarNavItemProps[] = [
  { icon: <ReportsIcon />, label: 'Relatórios', to: null },
  { icon: <UsersIcon />, label: 'Usuários', to: null },
]

function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : ''
  return `${first}${last}`.toUpperCase()
}

export function Sidebar() {
  const { user } = useAuth()

  return (
    <div className="sidebar">
      <div className="sidebar__brand">
        <img className="sidebar__brand-mark" src={vertereMark} alt="" />
        <div>
          <div className="sidebar__brand-name">VERTERE</div>
          <div className="sidebar__brand-subtitle">LAB</div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {mainNavEntries.map((entry) => (
          <SidebarNavItem key={entry.label} {...entry} />
        ))}

        <div className="sidebar__section-label">Cadastros</div>
        {registrationNavEntries.map((entry) => (
          <SidebarNavItem key={entry.label} {...entry} />
        ))}

        <div className="sidebar__section-label">Administração</div>
        {adminNavEntries.map((entry) => (
          <SidebarNavItem key={entry.label} {...entry} />
        ))}
      </nav>

      {user && (
        <div className="sidebar__footer">
          <div className="sidebar__avatar">{getInitials(user.fullName)}</div>
          <div className="sidebar__footer-info">
            <div className="sidebar__footer-name">{user.fullName}</div>
            <div className="sidebar__footer-role">{user.roleName}</div>
          </div>
        </div>
      )}
    </div>
  )
}
