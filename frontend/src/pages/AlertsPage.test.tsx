import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AlertsPage } from './AlertsPage'
import type { DashboardOutlet } from '../components/DashboardLayout'
import type { AlertIncident, AlertPage, AlertRule } from '../types'

const api = vi.hoisted(() => ({
  createAlertRule: vi.fn(),
  deleteAlertRule: vi.fn(),
  getAlerts: vi.fn(),
  getAlertRules: vi.fn(),
  updateAlertRule: vi.fn(),
}))

vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {
    status = 500
  },
  ...api,
}))

const rule: AlertRule = {
  id: 3,
  owner_id: 1,
  device_id: null,
  name: 'Sustained CPU',
  metric: 'cpu',
  operator: 'gt',
  threshold: 85,
  severity: 'critical',
  evaluation_interval_seconds: 30,
  consecutive_violations: 2,
  enabled: true,
  created_at: '2026-11-06T12:00:00Z',
  updated_at: '2026-11-06T12:00:00Z',
}

const incident: AlertIncident = {
  id: 7,
  rule_id: 3,
  rule_name: rule.name,
  device_id: 4,
  device_name: 'prod-api',
  metric: 'cpu',
  metric_name: 'cpu',
  severity: 'critical',
  status: 'firing',
  threshold: 85,
  observed_value: 93.5,
  message: 'prod-api CPU above threshold',
  triggered_at: '2026-11-06T12:00:00Z',
  resolved_at: null,
  notifications: [],
}

const emptyPage: AlertPage = { items: [], total: 0, limit: 100, offset: 0 }

function renderAlerts() {
  const context: DashboardOutlet = {
    snapshot: { generated_at: '2026-11-06T12:00:00Z', devices: [] },
    loading: false,
    error: '',
    connected: true,
    setError: () => undefined,
  }
  return render(
    <MemoryRouter>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route path="/" element={<AlertsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('alerts page', () => {
  beforeEach(() => {
    sessionStorage.setItem('devpulse.accessToken', 'alerts-token')
    api.getAlertRules.mockResolvedValue([rule])
    api.getAlerts.mockImplementation((_token: string, options: { activeOnly: boolean }) =>
      Promise.resolve(options.activeOnly ? { ...emptyPage, items: [incident], total: 1 } : emptyPage),
    )
    api.createAlertRule.mockResolvedValue(rule)
    api.updateAlertRule.mockResolvedValue({ ...rule, enabled: false })
    api.deleteAlertRule.mockResolvedValue(undefined)
  })

  it('renders active incidents and real rule controls', async () => {
    renderAlerts()

    expect(await screen.findByText('prod-api CPU above threshold')).toBeInTheDocument()
    expect(screen.getByText('FIRING')).toBeInTheDocument()
    expect(screen.getAllByText('critical')).toHaveLength(2)
    expect(screen.getAllByText('Sustained CPU')).toHaveLength(2)
    fireEvent.click(screen.getByRole('button', { name: 'Disable' }))
    await waitFor(() =>
      expect(api.updateAlertRule).toHaveBeenCalledWith(
        'alerts-token',
        rule.id,
        { enabled: false },
      ),
    )
  })

  it('creates a threshold rule through the API and shows resolved history', async () => {
    api.getAlerts.mockImplementation((_token: string, options: { activeOnly: boolean }) =>
      Promise.resolve(options.activeOnly ? emptyPage : {
        ...emptyPage,
        total: 1,
        items: [{ ...incident, status: 'resolved', resolved_at: '2026-11-06T12:30:00Z' }],
      }),
    )
    renderAlerts()

    fireEvent.click(await screen.findByRole('button', { name: 'New rule' }))
    fireEvent.change(screen.getByLabelText('Rule name'), { target: { value: 'RAM pressure' } })
    fireEvent.change(screen.getByLabelText('Metric'), { target: { value: 'ram' } })
    fireEvent.change(screen.getByLabelText('Threshold (%)'), { target: { value: '90' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create rule' }))

    await waitFor(() => expect(api.createAlertRule).toHaveBeenCalledWith(
      'alerts-token',
      expect.objectContaining({
        name: 'RAM pressure',
        metric: 'ram',
        operator: 'gt',
        threshold: 90,
      }),
    ))
    fireEvent.click(screen.getByRole('button', { name: 'Resolved' }))
    expect(await screen.findByText('RESOLVED')).toBeInTheDocument()
    expect(api.getAlerts).toHaveBeenLastCalledWith(
      'alerts-token',
      { activeOnly: false, limit: 100 },
    )
  })

  it('does not present a failed alert request as an empty workspace', async () => {
    api.getAlertRules.mockRejectedValue(new Error('offline'))
    api.getAlerts.mockRejectedValue(new Error('offline'))
    renderAlerts()

    expect(await screen.findByText('Incident history is unavailable until the API responds.')).toBeInTheDocument()
    expect(screen.queryByText('No active incidents')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Unable to load alert data')
  })
})
