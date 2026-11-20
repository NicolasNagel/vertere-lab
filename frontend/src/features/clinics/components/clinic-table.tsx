import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { formatTaxId } from '../../../shared/lib/formatters'
import { AttendanceListPagination } from '../../attendances/components/attendance-list-pagination'
import type { Clinic } from '../api/clinics-api'
import { ClinicStatusBadge } from './clinic-status-badge'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-list-pagination.css'
import '../../attendances/components/attendance-list-table.css'
import '../../../shared/ui/registry-table.css'

interface ClinicTableProps {
  clinics: Clinic[]
  canManage: boolean
  selectedId: string | null
  isLoading: boolean
  isError: boolean
  isForbidden?: boolean
  page: number
  pageSize: number
  total: number
  onSelect: (id: string) => void
  onEdit: (id: string) => void
  onPageChange: (page: number) => void
}

/** Tabela de clínicas no padrão da lista de atendimentos (Operação). */
export function ClinicTable({
  clinics,
  canManage,
  selectedId,
  isLoading,
  isError,
  isForbidden = false,
  page,
  pageSize,
  total,
  onSelect,
  onEdit,
  onPageChange,
}: ClinicTableProps) {
  return (
    <>
      {isLoading && <p className="attendance-list-page__hint">Carregando…</p>}
      {isError && (
        <p role="alert" className="attendance-list-page__error">
          {isForbidden
            ? 'Você não tem permissão para ver esta lista.'
            : 'Não foi possível carregar as clínicas.'}
        </p>
      )}
      {!isLoading && !isError && clinics.length === 0 && (
        <p className="attendance-list-page__hint">Nenhuma clínica encontrada para os filtros selecionados.</p>
      )}
      {clinics.length > 0 && (
        <div className="attendance-list-table">
          <table className="attendance-list-table__table registry-table__table">
            <thead>
              <tr>
                <th scope="col">Clínica</th>
                <th scope="col" className="registry-table__optional">
                  CNPJ
                </th>
                <th scope="col">Cidade / UF</th>
                <th scope="col" className="registry-table__optional">
                  Telefone
                </th>
                <th scope="col">Status</th>
                {canManage && (
                  <th scope="col" className="registry-table__actions">
                    <span className="registry-table__sr">Ações</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {clinics.map((clinic) => {
                const items: KebabMenuItem[] = [
                  { label: 'Editar clínica', onSelect: () => onEdit(clinic.id) },
                ]
                return (
                  <tr
                    key={clinic.id}
                    data-selectable
                    data-selected={clinic.id === selectedId || undefined}
                    onClick={() => onSelect(clinic.id)}
                  >
                    <td>
                      <button
                        type="button"
                        className="registry-table__name"
                        title={clinic.name}
                        onClick={(event) => {
                          event.stopPropagation()
                          onSelect(clinic.id)
                        }}
                      >
                        {clinic.name}
                      </button>
                    </td>
                    <td className="attendance-list-table__protocol registry-table__optional">
                      {formatTaxId(clinic.taxId) ?? '—'}
                    </td>
                    <td>
                      {clinic.addressCity
                        ? `${clinic.addressCity} / ${clinic.addressState ?? '—'}`
                        : '—'}
                    </td>
                    <td className="attendance-list-table__protocol registry-table__optional">
                      {clinic.phone ?? '—'}
                    </td>
                    <td>
                      <ClinicStatusBadge status={clinic.status} />
                    </td>
                    {canManage && (
                      <td className="registry-table__actions" onClick={(event) => event.stopPropagation()}>
                        <KebabMenu label={`Ações para ${clinic.name}`} items={items} />
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
        itemLabel={['clínica', 'clínicas']}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
      />
    </>
  )
}
