import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getAlerts,
  getDashboard,
  getDashboardSocketUrl,
  getAlertRules,
  login,
} from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API client', () => {
  it('sends the OAuth2 form expected by the FastAPI login endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'jwt', token_type: 'bearer' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(login('person@example.com', 'password')).resolves.toBe('jwt')
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(options.method).toBe('POST')
    expect(options.headers).toMatchObject({
      'Content-Type': 'application/x-www-form-urlencoded',
    })
    expect(String(options.body)).toContain('username=person%40example.com')
  })

  it('attaches bearer authentication to dashboard data requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ generated_at: '2026-11-05T12:00:00Z', devices: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await getDashboard('session-jwt')
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(fetchMock.mock.calls[0][0]).toContain('/dashboard')
    expect(new Headers(options.headers).get('Authorization')).toBe('Bearer session-jwt')
  })

  it('uses the correct WebSocket protocol and ticket query without user JWTs', () => {
    const url = new URL(getDashboardSocketUrl('single-use-ticket'))

    expect(url.protocol).toBe('ws:')
    expect(url.pathname).toBe('/ws/dashboard')
    expect(url.searchParams.get('ticket')).toBe('single-use-ticket')
    expect(url.searchParams.has('token')).toBe(false)
  })

  it('authenticates alert requests and applies status filters', async () => {
    const fetchMock = vi.fn().mockImplementation(
      () => new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await getAlertRules('alerts-jwt')
    await getAlerts('alerts-jwt', { activeOnly: false, limit: 25, offset: 25 })

    expect(fetchMock.mock.calls[0][0]).toContain('/alerts/rules')
    const firstOptions = fetchMock.mock.calls[0][1] as RequestInit
    const authorization = new Headers(firstOptions.headers).get('Authorization')
    expect(authorization?.startsWith('Bearer ')).toBe(true)
    expect(authorization?.slice(7)).toBe('alerts' + '-jwt')
    const url = new URL(fetchMock.mock.calls[1][0] as string)
    expect(url.searchParams.get('active_only')).toBe('false')
    expect(url.searchParams.get('limit')).toBe('25')
    expect(url.searchParams.get('offset')).toBe('25')
  })
})
