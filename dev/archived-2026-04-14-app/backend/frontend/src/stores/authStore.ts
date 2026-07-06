import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { setStoredTokens, clearStoredTokens } from '../lib/api'

interface User {
  id: number
  email: string
  full_name: string
  role: string
  is_active: boolean
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  login: (accessToken: string, refreshToken: string, user: User) => void
  logout: () => void
  setUser: (user: User) => void
}

// Tokens live ONLY in the legacy localStorage keys, managed through the
// helpers in lib/api.ts (getAccessToken / setStoredTokens / ...). The
// store holds the user and the authenticated flag - it no longer keeps
// a duplicate copy of the tokens in its persisted state.
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,

      login: (accessToken, refreshToken, user) => {
        setStoredTokens(accessToken, refreshToken)
        set({
          user,
          isAuthenticated: true,
        })
      },

      logout: () => {
        clearStoredTokens()
        set({
          user: null,
          isAuthenticated: false,
        })
      },

      setUser: (user) => set({ user }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
