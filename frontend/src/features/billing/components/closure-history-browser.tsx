import { useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useMonthlyClosuresQuery } from '../api/use-monthly-closures-query'
import { ClosuresListPagination } from './closures-list-pagination'
import { ClosuresListTable } from './closures-list-table'
import './closure-history-browser.css'

const PAGE_SIZE = 20

/** Estado inicial da tela unificada de fechamento (Tela 15) quando nenhuma
 * clínica está selecionada — histórico de todos os fechamentos, cada linha
 * levando para o mesmo detalhe (`/financeiro/fechamento?clinicId=&periodStart=&periodEnd=`)
 * já usado pelo filtro do topo. Só é renderizado quando o usuário tem
 * `closures.read` — a permissão já foi checada por quem chama este
 * componente (`ClosurePage`).
 *
 * Sem filtro de clínica próprio: o filtro "Clínica" do topo já existe nesta
 * mesma tela, e duplicar o rótulo aqui (com comportamento diferente — um
 * troca a clínica selecionada, o outro só filtraria a lista) confundiria
 * mais do que ajudaria. Quem quer ver o histórico de uma clínica específica
 * pode escolhê-la no filtro do topo e voltar por aqui depois. */
export function ClosureHistoryBrowser() {
  const [page, setPage] = useState(1)

  const clinicsQuery = useAllClinicsQuery()
  const clinicNameById: Record<string, string> = Object.fromEntries(
    (clinicsQuery.data?.items ?? []).map((clinic) => [clinic.id, clinic.name]),
  )

  const closuresQuery = useMonthlyClosuresQuery({ page, pageSize: PAGE_SIZE })

  const isForbidden = closuresQuery.error instanceof ApiError && closuresQuery.error.status === 403
  const isGenericError = closuresQuery.isError && !isForbidden

  return (
    <div className="closure-history-browser">
      {closuresQuery.isLoading && <p className="closure-history-browser__hint">Carregando…</p>}

      {isForbidden && (
        <p className="closure-history-browser__forbidden">
          Você não tem permissão para visualizar fechamentos.
        </p>
      )}

      {isGenericError && (
        <p className="closure-history-browser__error">
          Não foi possível carregar os fechamentos. Tente novamente.
        </p>
      )}

      {!closuresQuery.isLoading && closuresQuery.data && (
        <>
          <ClosuresListTable closures={closuresQuery.data.items} clinicNameById={clinicNameById} />
          <ClosuresListPagination
            page={closuresQuery.data.page}
            pageSize={closuresQuery.data.pageSize}
            total={closuresQuery.data.total}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  )
}
