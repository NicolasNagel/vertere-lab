import { useLocation } from 'react-router'

import './topbar.css'

const ROUTE_TRAILS: { match: RegExp; trail: string[] }[] = [
  { match: /^\/$/, trail: ['Dashboard'] },
  { match: /^\/operacao$/, trail: ['Operação', 'Atendimentos'] },
  { match: /^\/operacao\/novo$/, trail: ['Operação', 'Atendimentos', 'Novo protocolo'] },
  { match: /^\/operacao\/[^/]+$/, trail: ['Operação', 'Atendimentos', 'Protocolo'] },
  { match: /^\/cadastros\/clinicas/, trail: ['Cadastros', 'Clínicas'] },
  { match: /^\/cadastros\/veterinarios/, trail: ['Cadastros', 'Veterinários'] },
  { match: /^\/pacientes/, trail: ['Pacientes'] },
  { match: /^\/cadastros\/exames\/novo$/, trail: ['Cadastros', 'Exames & Preços', 'Novo exame'] },
  {
    match: /^\/cadastros\/exames\/[^/]+\/editar$/,
    trail: ['Cadastros', 'Exames & Preços', 'Editar'],
  },
  { match: /^\/cadastros\/exames/, trail: ['Cadastros', 'Exames & Preços'] },
  { match: /^\/administracao\/usuarios/, trail: ['Administração', 'Usuários'] },
  { match: /^\/financeiro\/fechamento/, trail: ['Financeiro', 'Fechamento'] },
]

export function Topbar() {
  const { pathname } = useLocation()
  const trail = ROUTE_TRAILS.find((route) => route.match.test(pathname))?.trail ?? []
  if (trail.length === 0) return null

  return (
    <div className="topbar">
      <nav aria-label="Caminho da página">
        <ol className="topbar__trail">
          {trail.map((label, index) => (
            <li
              key={label}
              className="topbar__crumb"
              aria-current={index === trail.length - 1 ? 'page' : undefined}
            >
              {label}
            </li>
          ))}
        </ol>
      </nav>
    </div>
  )
}
