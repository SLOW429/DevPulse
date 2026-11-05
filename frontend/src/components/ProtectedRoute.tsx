import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="auth-loading" role="status">
        <span className="loading-mark" />
        <span>Securing your workspace…</span>
      </div>
    )
  }
  return user ? <Outlet /> : <Navigate to="/login" replace />
}
