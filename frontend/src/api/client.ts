import type {
  AgentCredential,
  AlertPage,
  AlertRule,
  AlertRulePayload,
  DashboardSnapshot,
  Metric,
  User,
} from '../types'

const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(
  /\/$/,
  '',
)

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(
  path: string,
  token?: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new Event('devpulse:unauthorized'))
    }
    let message = `Request failed (${response.status})`
    try {
      const body: { detail?: string | { msg?: string }[] } = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) {
        message = body.detail.map((item) => item.msg).filter(Boolean).join(', ')
      }
    } catch {
      // Keep the HTTP status message when the server does not return JSON.
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function register(email: string, password: string): Promise<User> {
  return request<User>('/auth/register', undefined, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password })
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  })
  if (!response.ok) {
    let message = 'Unable to sign in'
    try {
      const data: { detail?: string } = await response.json()
      if (data.detail) message = data.detail
    } catch {
      // Keep a useful authentication error when the response is not JSON.
    }
    throw new ApiError(message, response.status)
  }
  const data: { access_token: string; token_type: string } = await response.json()
  return data.access_token
}

export function getCurrentUser(token: string): Promise<User> {
  return request<User>('/auth/me', token)
}

export function getDashboard(token: string): Promise<DashboardSnapshot> {
  return request<DashboardSnapshot>('/dashboard', token)
}

export function getDeviceMetrics(
  token: string,
  deviceId: number,
  limit = 500,
): Promise<Metric[]> {
  return request<Metric[]>(`/devices/${deviceId}/metrics?limit=${limit}`, token)
}

export function getAlertRules(token: string): Promise<AlertRule[]> {
  return request<AlertRule[]>('/alerts/rules', token)
}

export function getAlerts(
  token: string,
  options: { activeOnly?: boolean; limit?: number; offset?: number } = {},
): Promise<AlertPage> {
  const query = new URLSearchParams({
    limit: String(options.limit ?? 50),
    offset: String(options.offset ?? 0),
  })
  if (options.activeOnly !== undefined) {
    query.set('active_only', String(options.activeOnly))
  }
  return request<AlertPage>(`/alerts?${query}`, token)
}

export function createAlertRule(
  token: string,
  data: AlertRulePayload,
): Promise<AlertRule> {
  return request<AlertRule>('/alerts/rules', token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function updateAlertRule(
  token: string,
  ruleId: number,
  data: Partial<AlertRulePayload>,
): Promise<AlertRule> {
  return request<AlertRule>(`/alerts/rules/${ruleId}`, token, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function deleteAlertRule(token: string, ruleId: number): Promise<void> {
  return request<void>(`/alerts/rules/${ruleId}`, token, { method: 'DELETE' })
}

export async function createDevice(
  token: string,
  data: { name: string; hostname?: string; os?: string },
): Promise<AgentCredential> {
  return request<AgentCredential>('/devices', token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function createWebSocketTicket(token: string): Promise<string> {
  const response = await request<{ ticket: string }>('/realtime/ticket', token, {
    method: 'POST',
  })
  return response.ticket
}

export function getDashboardSocketUrl(ticket: string): string {
  const url = new URL(API_BASE)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `${url.pathname.replace(/\/$/, '')}/ws/dashboard`
  url.search = new URLSearchParams({ ticket }).toString()
  return url.toString()
}
