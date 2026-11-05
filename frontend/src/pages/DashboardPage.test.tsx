import { render, screen } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { DashboardPage } from './DashboardPage'
import type { DashboardOutlet } from '../components/DashboardLayout'
import type { DashboardSnapshot } from '../types'

const snapshot: DashboardSnapshot = {
  generated_at: '2026-11-05T12:00:00Z',
  devices: [
    {
      id: 1,
      agent_id: 'a3e6e90d-28cc-4ffb-9c66-1f68605a6a83',
      name: 'prod-api-01',
      hostname: 'api.example.com',
      os: 'Linux',
      status: 'online',
      last_seen_at: '2026-11-05T12:00:00Z',
      latest_metric: {
        id: 12,
        device_id: 1,
        collected_at: '2026-11-05T12:00:00Z',
        received_at: '2026-11-05T12:00:01Z',
        cpu_percent: 36.2,
        ram_percent: 67.1,
        disk_percent: 42.8,
        net_bytes_sent: 1048576,
        net_bytes_recv: 2097152,
        uptime_seconds: 90061,
      },
    },
  ],
}

function renderDashboard(value: DashboardOutlet) {
  return render(
    <MemoryRouter>
      <Routes>
        <Route element={<Outlet context={value} />}>
          <Route index element={<DashboardPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('dashboard', () => {
  it('renders device state and metric summaries from the API snapshot', () => {
    renderDashboard({
      snapshot,
      loading: false,
      error: '',
      connected: true,
      setError: () => undefined,
    })

    expect(screen.getAllByText('prod-api-01')).toHaveLength(2)
    expect(screen.getAllByText('online')).toHaveLength(2)
    expect(screen.getAllByText('36.2%')).toHaveLength(2)
    expect(screen.getAllByText('67.1%')).toHaveLength(2)
    expect(screen.getAllByText('42.8%')).toHaveLength(2)
    expect(screen.getAllByText('1d 1h')).toHaveLength(2)
  })

  it('shows the empty state when the API reports no devices', () => {
    renderDashboard({
      snapshot: { generated_at: snapshot.generated_at, devices: [] },
      loading: false,
      error: '',
      connected: false,
      setError: () => undefined,
    })

    expect(screen.getByText('No devices in your workspace yet')).toBeInTheDocument()
    expect(screen.getByText('Registered devices')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('does not present an unavailable snapshot as an empty workspace', () => {
    renderDashboard({
      snapshot: null,
      loading: false,
      error: 'API is unavailable',
      connected: false,
      setError: () => undefined,
    })

    expect(screen.getByText('Dashboard data is unavailable')).toBeInTheDocument()
    expect(screen.queryByText('No devices in your workspace yet')).not.toBeInTheDocument()
  })
})
