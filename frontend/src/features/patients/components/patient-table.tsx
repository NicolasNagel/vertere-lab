import { Badge } from '../../../shared/ui/badge'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { AttendanceListPagination } from '../../attendances/components/attendance-list-pagination'
import type { Patient } from '../api/patients-api'
import { displayValue, PATIENT_STATUS_LABELS, patientListErrorMessage } from './patient-labels'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-list-pagination.css'
import '../../attendances/components/attendance-list-table.css'
import './patient-table.css'

interface PatientTableProps {
  patients: Patient[]
  speciesNameById: ReadonlyMap<string, string>
  clinicNameById: ReadonlyMap<string, string>
  canManage: boolean
  selectedId: string | null
  isLoading: boolean
  error: unknown
  page: number
  pageSize: number
  total: number
  onSelect: (id: string) => void
  onDeactivate: (id: string) => void
  onReactivate: (id: string) => void
  onPageChange: (page: number) => void
}

/** Tabela de pacientes no padrão da lista de atendimentos (Operação). */
export function PatientTable({
  patients,
  speciesNameById,
  clinicNameById,
  canManage,
  selectedId,
  isLoading,
  error,
  page,
  pageSize,
  total,
  onSelect,
  onDeactivate,
  onReactivate,
  onPageChange,
}: PatientTableProps) {
  const isError = error !== null && error !== undefined
  return (
    <>
      {isLoading && <p className="attendance-list-page__hint">Carregando…</p>}
      {isError && (
        <p role="alert" className="attendance-list-page__error">
          {patientListErrorMessage(error)}
        </p>
      )}
      {!isLoading && !isError && patients.length === 0 && (
        <p className="attendance-list-page__hint">
          Nenhum paciente encontrado para os filtros selecionados.
        </p>
      )}
      {patients.length > 0 && (
        <div className="attendance-list-table">
          <table className="attendance-list-table__table patient-table__table">
            <thead>
              <tr>
                <th scope="col">Paciente</th>
                <th scope="col">Espécie</th>
                <th scope="col">Tutor</th>
                <th scope="col" className="patient-table__optional">
                  Clínica
                </th>
                <th scope="col" className="patient-table__optional">
                  Idade
                </th>
                <th scope="col">Status</th>
                {canManage && (
                  <th scope="col" className="patient-table__actions">
                    <span className="patient-table__sr">Ações</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {patients.map((patient) => {
                const items: KebabMenuItem[] =
                  patient.status === 'ACTIVE'
                    ? [
                        {
                          label: 'Inativar paciente',
                          onSelect: () => onDeactivate(patient.id),
                          destructive: true,
                        },
                      ]
                    : [{ label: 'Reativar paciente', onSelect: () => onReactivate(patient.id) }]
                return (
                  <tr
                    key={patient.id}
                    data-selectable
                    data-selected={patient.id === selectedId || undefined}
                    onClick={() => onSelect(patient.id)}
                  >
                    <td>
                      <button
                        type="button"
                        className="patient-table__name"
                        title={patient.name}
                        onClick={(event) => {
                          event.stopPropagation()
                          onSelect(patient.id)
                        }}
                      >
                        {patient.name}
                      </button>
                    </td>
                    <td>{speciesNameById.get(patient.speciesId) ?? '—'}</td>
                    <td className="patient-table__owner" title={patient.ownerName}>
                      {patient.ownerName}
                    </td>
                    <td className="patient-table__optional patient-table__clinic">
                      {patient.clinicId ? (clinicNameById.get(patient.clinicId) ?? '—') : '—'}
                    </td>
                    <td className="patient-table__optional">
                      {displayValue(patient.ageDescription)}
                    </td>
                    <td>
                      <Badge tone={patient.status === 'ACTIVE' ? 'success' : 'neutral'}>
                        {PATIENT_STATUS_LABELS[patient.status]}
                      </Badge>
                    </td>
                    {canManage && (
                      <td
                        className="patient-table__actions"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <KebabMenu label={`Ações para ${patient.name}`} items={items} />
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
        itemLabel={['paciente', 'pacientes']}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
      />
    </>
  )
}
