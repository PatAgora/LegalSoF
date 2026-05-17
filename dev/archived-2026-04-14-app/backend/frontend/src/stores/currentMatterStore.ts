// Small Zustand store: whichever matter the user is currently
// "inside". Set by MatterDetailPage on mount; cleared on unmount. The
// Layout reads it so it can swap the sidebar into matter-context
// mode (matter ref as title, tab links instead of workspace nav).
import { create } from 'zustand'

export interface CurrentMatter {
  id: number
  reference_number: string | null
  client_name: string | null
  transaction_type?: string | null
}

interface CurrentMatterState {
  matter: CurrentMatter | null
  setMatter: (m: CurrentMatter | null) => void
  clearMatter: () => void
}

export const useCurrentMatter = create<CurrentMatterState>((set) => ({
  matter: null,
  setMatter: (m) => set({ matter: m }),
  clearMatter: () => set({ matter: null }),
}))
