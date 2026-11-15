import { useState } from 'react'

import { ClinicFeeRulesPanel } from './clinic-fee-rules-panel'
import { OnCallFeeSettingsPanel } from './on-call-fee-settings-panel'
import { UrgencyFeePanel } from './urgency-fee-panel'
import '../../attendances/components/attendance-status-tabs.css'
import './fees.css'

type FeeSection = 'plantao' | 'urgencia' | 'clinicas'

const SECTIONS: { id: FeeSection; label: string }[] = [
  { id: 'plantao', label: 'Plantão' },
  { id: 'urgencia', label: 'Urgência' },
  { id: 'clinicas', label: 'Por clínica' },
]

/** Aba "Taxas": plantão, urgência e taxas personalizadas por clínica. Todas somam ao total. */
export function FeesTab() {
  const [section, setSection] = useState<FeeSection>('plantao')

  return (
    <div>
      <div className="fees__tabs">
        <div className="attendance-status-tabs" role="tablist" aria-label="Tipos de taxa">
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`fees-tab-${item.id}`}
              aria-selected={section === item.id}
              aria-controls="fees-panel"
              className="attendance-status-tabs__tab"
              data-active={section === item.id}
              onClick={() => setSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div id="fees-panel" role="tabpanel" aria-labelledby={`fees-tab-${section}`}>
        {section === 'plantao' && <OnCallFeeSettingsPanel />}
        {section === 'urgencia' && <UrgencyFeePanel />}
        {section === 'clinicas' && <ClinicFeeRulesPanel />}
      </div>
    </div>
  )
}
