import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { AuthPage } from '../components/AuthPage'
import type { User } from '../types'

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  getCurrentUser: vi.fn(),
  ApiError: class ApiError extends Error {
    status = 401
  },
}))

vi.mock('../api/client', () => ({
  ApiError: api.ApiError,
  login: api.login,
  register: api.register,
  getCurrentUser: api.getCurrentUser,
}))

const user: User = {
  id: 7,
  email: 'operator@example.com',
  role: 'viewer',
  is_active: true,
  created_at: '2026-11-05T12:00:00Z',
}

function LocationOutput() {
  return <div data-testid="location">{useLocation().pathname}</div>
}

function renderAuth(mode: 'login' | 'register') {
  return render(
    <MemoryRouter initialEntries={[`/${mode}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route path="/" element={<LocationOutput />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('authentication flows', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
    api.login.mockResolvedValue('signed.jwt.token')
    api.getCurrentUser.mockResolvedValue(user)
    api.register.mockResolvedValue(user)
  })

  it('signs in using the backend and redirects to the dashboard', async () => {
    const userEventInstance = userEvent.setup()
    renderAuth('login')

    await userEventInstance.type(screen.getByLabelText('Work email'), user.email)
    await userEventInstance.type(screen.getByLabelText('Password'), 'a-valid-password')
    await userEventInstance.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByTestId('location')).toHaveTextContent('/')
    expect(api.login).toHaveBeenCalledWith(user.email, 'a-valid-password')
    expect(api.getCurrentUser).toHaveBeenCalledWith('signed.jwt.token')
    expect(sessionStorage.getItem('devpulse.accessToken')).toBe('signed.jwt.token')
  })

  it('registers then authenticates a new account', async () => {
    const userEventInstance = userEvent.setup()
    renderAuth('register')

    await userEventInstance.type(screen.getByLabelText('Work email'), user.email)
    await userEventInstance.type(screen.getByLabelText('Password'), 'long-enough-password')
    await userEventInstance.click(screen.getByRole('button', { name: /create workspace/i }))

    expect(await screen.findByTestId('location')).toHaveTextContent('/')
    expect(api.register).toHaveBeenCalledWith(user.email, 'long-enough-password')
    expect(api.login).toHaveBeenCalledWith(user.email, 'long-enough-password')
  })

  it('shows backend authentication errors without storing a token', async () => {
    const userEventInstance = userEvent.setup()
    api.login.mockRejectedValueOnce(new api.ApiError('Invalid email or password'))
    renderAuth('login')

    await userEventInstance.type(screen.getByLabelText('Work email'), user.email)
    await userEventInstance.type(screen.getByLabelText('Password'), 'wrong-password')
    await userEventInstance.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password')
    expect(sessionStorage.getItem('devpulse.accessToken')).toBeNull()
    await waitFor(() => expect(api.getCurrentUser).not.toHaveBeenCalled())
  })
})
