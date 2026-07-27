import { Checkbox } from '../../../shared/ui/checkbox'
import type { Species } from '../../patients/api/patients-api'
import type { ExamCategory } from '../api/catalog-api'
import './exam-catalog-sidebar.css'

interface ExamCatalogSidebarProps {
  categories: ExamCategory[]
  categoryCounts: Map<string, number>
  totalCount: number
  selectedCategoryId: string | null
  onSelectCategory: (categoryId: string | null) => void
  species: Species[]
  selectedSpeciesId: string | null
  onSelectSpecies: (speciesId: string | null) => void
}

// Espécie é filtro de seleção única aqui (mesma restrição do backend, que
// só aceita um `species_id` por vez em GET /exams — rule: .claude/rules/
// frontend.md, "não invente novo comportamento sem sinalizar").
export function ExamCatalogSidebar({
  categories,
  categoryCounts,
  totalCount,
  selectedCategoryId,
  onSelectCategory,
  species,
  selectedSpeciesId,
  onSelectSpecies,
}: ExamCatalogSidebarProps) {
  return (
    <div className="exam-catalog-sidebar">
      <div className="exam-catalog-sidebar__section-title">Categorias</div>
      <button
        type="button"
        className="exam-catalog-sidebar__category"
        data-selected={selectedCategoryId === null}
        onClick={() => onSelectCategory(null)}
      >
        <span>Todos</span>
        <span className="exam-catalog-sidebar__count">{totalCount}</span>
      </button>
      {categories.map((category) => (
        <button
          key={category.id}
          type="button"
          className="exam-catalog-sidebar__category"
          data-selected={selectedCategoryId === category.id}
          onClick={() => onSelectCategory(category.id)}
        >
          <span>{category.name}</span>
          <span className="exam-catalog-sidebar__count">{categoryCounts.get(category.id) ?? 0}</span>
        </button>
      ))}

      <div className="exam-catalog-sidebar__section-title">Espécies</div>
      <div className="exam-catalog-sidebar__species" role="group" aria-label="Filtrar por espécie">
        {species.map((item) => (
          <Checkbox
            key={item.id}
            label={item.name}
            checked={selectedSpeciesId === item.id}
            onChange={() => onSelectSpecies(selectedSpeciesId === item.id ? null : item.id)}
          />
        ))}
      </div>
    </div>
  )
}
