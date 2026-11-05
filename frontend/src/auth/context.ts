import { createContext } from 'react'
import type { User } from '../types'

export interface AuthValue {
  user: User | null
  isLoading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => void
}

export const AuthContext = createContext<AuthValue | null>(null)
