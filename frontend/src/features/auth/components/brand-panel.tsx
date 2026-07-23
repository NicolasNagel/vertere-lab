import { APP_VERSION, LAB_LOCATION } from '../../../shared/config/app-info'
import logoWhite from '../../../shared/assets/vertere-logo-white.png'
import './brand-panel.css'

export function BrandPanel() {
  return (
    <div className="brand-panel">
      {/* Círculos decorativos translúcidos — só estética, sem significado. */}
      <span className="brand-panel__circle brand-panel__circle--top" aria-hidden="true" />
      <span className="brand-panel__circle brand-panel__circle--bottom" aria-hidden="true" />
      <div className="brand-panel__content">
        <img
          className="brand-panel__logo"
          src={logoWhite}
          alt="Vertere — Laboratório Veterinário"
        />
        <p className="brand-panel__slogan">
          Cada amostra,
          <br />
          <em>uma história.</em>
          <br />
          Cada resultado,
          <br />
          <em>um cuidado.</em>
        </p>
      </div>
      <p className="brand-panel__footer">
        {APP_VERSION} · {LAB_LOCATION}
      </p>
    </div>
  )
}
