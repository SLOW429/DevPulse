import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { AuthPage } from './components/AuthPage'
import { DashboardLayout } from './components/DashboardLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { DashboardPage } from './pages/DashboardPage'
const DeviceDetailPage = lazy(() =>
  import('./pages/DeviceDetailPage').then((module) => ({
    default: module.DeviceDetailPage,
  })),
)
const AlertsPage = lazy(() =>
  import('./pages/AlertsPage').then((module) => ({
    default: module.AlertsPage,
  })),
)

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<DashboardLayout />}>
              <Route index element={<DashboardPage />} />
              <Route
                path="alerts"
                element={
                  <Suspense fallback={<div className="page-loading"><span className="loading-mark" /> Loading alerts…</div>}>
                    <AlertsPage />
                  </Suspense>
                }
              />
              <Route
                path="devices/:deviceId"
                element={
                  <Suspense fallback={<div className="page-loading"><span className="loading-mark" /> Loading device view…</div>}>
                    <DeviceDetailPage />
                  </Suspense>
                }
              />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
