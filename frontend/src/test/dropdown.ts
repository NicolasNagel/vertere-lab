import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

/** Botão do `Dropdown` de formulário (variant `field`): nome acessível = rótulo + valor atual. */
export function dropdownTrigger(label: string, scope: HTMLElement = document.body): HTMLElement {
  return within(scope).getByRole('button', { name: new RegExp(`^${label}`) })
}

/** Escolhe uma opção do `Dropdown`: abre o menu e clica na opção pelo nome. */
export async function pickOption(
  user: UserEvent,
  label: string,
  option: string,
  scope: HTMLElement = document.body,
): Promise<void> {
  await user.click(dropdownTrigger(label, scope))
  await user.click(await screen.findByRole('option', { name: option }))
}
