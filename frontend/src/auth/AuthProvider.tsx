import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import * as api from '../api/client'
import type { User } from '../types'
import { AuthContext } from './context'
import { clearAccessToken, currentAccessToken, saveAccessToken } from './session'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(
    () => currentAccessToken() !== null,
  )

  const signOut = useCallback(() => {
    clearAccessToken()
    setUser(null)
    setIsLoading(false)
  }, [])

  useEffect(() => {
    const handleUnauthorized = () => signOut()
    window.addEventListener('devpulse:unauthorized', handleUnauthorized)
    const token = currentAccessToken()
    if (token) {
      void api
        .getCurrentUser(token)
        .then(setUser)
        .catch(signOut)
        .finally(() => setIsLoading(false))
    }
    return () =>
      window.removeEventListener('devpulse:unauthorized', handleUnauthorized)
  }, [signOut])

  const signIn = useCallback(async (email: string, password: string) => {
    const token = await api.login(email, password)
    saveAccessToken(token)
    try {
      setUser(await api.getCurrentUser(token))
    } catch (error) {
      clearAccessToken()
      throw error
    }
  }, [])

  const signUp = useCallback(
    async (email: string, password: string) => {
      await api.register(email, password)
      await signIn(email, password)
    },
    [signIn],
  )

  const value = useMemo(
    () => ({ user, isLoading, signIn, signUp, signOut }),
    [user, isLoading, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
