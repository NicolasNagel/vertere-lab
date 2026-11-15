import { Badge } from '../../../shared/ui/badge'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { AttendanceListPagination } from '../../attendances/components/attendance-list-pagination'
import type { Veterinarian } from '../api/veterinarians-api'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-list-pagination.css'
import '../../attendances/components/attendance-list-table.css'
import './veterinarian-table.css'

interface VeterinarianTableProps {
  veterinarians: Veterinarian[]
  canManage: boolean
  selectedId: string | null
  isLoading: boolean
  isError: boolean
  page: number
  pageSize: number
  total: number
  onSelect: (id: string) => void
  onDeactivate: (id: string) => void
  onPageChange: (page: number) => void
}

/** Tabela de veterinários no padrão da lista de atendimentos (Operação). */
export function VeterinarianTable({
  veterinarians,
  canManage,
  selectedId,
  isLoading,
  isError,
  page,
  pageSize,
  total,
  onSelect,
  onDeactivate,
  onPageChange,
}: VeterinarianTableProps) {
  return (
    <>
      {isLoading && <p className="attendance-list-page__hint">Carregando…</p>}
      {isError && (
        <p role="alert" className="attendance-list-page__error">
          Não foi possível carregar os veterinários.
        </p>
      )}
      {!isLoading && !isError && veterinarians.length === 0 && (
        <p className="attendance-list-page__hint">
          Nenhum veterinário encontrado para os filtros selecionados.
        </p>
      )}
      {veterinarians.length > 0 && (
        <div className="attendance-list-table">
          <table className="attendance-list-table__table veterinarian-table__table">
            <thead>
              <tr>
                <th scope="col">Veterinário</th>
                <th scope="col">CRMV</th>
                <th scope="col" className="veterinarian-table__optional">
                  Telefone
                </th>
                <th scope="col">Vínculo</th>
                <th scope="col">Status</th>
                {canManage && (
                  <th scope="col" className="veterinarian-table__actions">
                    <span className="veterinarian-table__sr">Ações</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {veterinarians.map((veterinarian) => {
                const items: KebabMenuItem[] =
                  veterinarian.status === 'ACTIVE'
                    ? [
                        {
                          label: 'Inativar veterinário',
                          onSelect: () => onDeactivate(veterinarian.id),
                          destructive: true,
                        },
                      ]
                    : []
                return (
                  <tr
                    key={veterinarian.id}
                    data-selectable
                    data-selected={veterinarian.id === selectedId || undefined}
                    onClick={() => onSelect(veterinarian.id)}
                  >
                    <td>
                      <button
                        type="button"
                        className="veterinarian-table__name"
                        title={veterinarian.name}
                        onClick={(event) => {
                          event.stopPropagation()
                          onSelect(veterinarian.id)
                        }}
                      >
                        {veterinarian.name}
                      </button>
                    </td>
                    <td className="attendance-list-table__protocol">{veterinarian.crmv}</td>
                    <td className="attendance-list-table__protocol veterinarian-table__optional">
                      {veterinarian.phone ?? '—'}
                    </td>
                    <td>{veterinarian.isAutonomous ? 'Autônomo' : 'Vinculado a clínica'}</td>
                    <td>
                      <Badge tone={veterinarian.status === 'ACTIVE' ? 'success' : 'neutral'}>
                        {veterinarian.status === 'ACTIVE' ? 'Ativo' : 'Inativo'}
                      </Badge>
                    </td>
                    {canManage && (
                      <td
                        className="veterinarian-table__actions"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {items.length > 0 && (
                          <KebabMenu label={`Ações para ${veterinarian.name}`} items={items} />
                        )}
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <AttendanceListPagination
        itemLabel={['veterinário', 'veterinários']}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
      />
    </>
  )
}
