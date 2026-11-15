const ACTION_LABELS: Record<string, string> = {
  'attendances.draft_created': 'Rascunho criado',
  'attendances.confirmed': 'Atendimento confirmado',
  'attendances.cancelled': 'Atendimento cancelado',
  'attendances.updated': 'Atendimento editado',
  'attendances.items_updated': 'Exames editados',
}

export function describeTimelineAction(action: string): string {
  return ACTION_LABELS[action] ?? action
}
