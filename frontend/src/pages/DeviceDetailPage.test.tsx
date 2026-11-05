import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DeviceDetailPage } from './DeviceDetailPage'
import type { DashboardOutlet } from '../components/DashboardLayout'
import type { DashboardSnapshot } from '../types'

const api = vi.hoisted(() => ({
  getDeviceMetrics: vi.fn(),
  ApiError: class ApiError extends Error {
    status = 500
  },
}))

vi.mock('../api/client', () => ({
  ApiError: api.ApiError,
  getDeviceMetrics: api.getDeviceMetrics,
}))

const snapshot: DashboardSnapshot = {
  generated_at: '2026-11-05T12:00:00Z',
  devices: [
    {
      id: 8,
      agent_id: 'a3e6e90d-28cc-4ffb-9c66-1f68605a6a83',
      name: 'edge-worker',
      hostname: 'worker-08',
      os: 'Linux',
      status: 'unknown',
      last_seen_at: null,
      latest_metric: null,
    },
  ],
}

function renderDevicePage() {
  const context: DashboardOutlet = {
    snapshot,
    loading: false,
    error: '',
    connected: true,
    setError: () => undefined,
  }
  return render(
    <MemoryRouter initialEntries={['/devices/8']}>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route path="devices/:deviceId" element={<DeviceDetailPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('device details', () => {
  beforeEach(() => {
    sessionStorage.setItem('devpulse.accessToken', 'dashboard-token')
    api.getDeviceMetrics.mockResolvedValue([])
  })

  it('loads real metric history and clearly handles a new device', async () => {
    renderDevicePage()

    expect(await screen.findByText('No measurements yet')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'edge-worker' })).toBeInTheDocument()
    await waitFor(() =>
      expect(api.getDeviceMetrics).toHaveBeenCalledWith(
        'dashboard-token',
        8,
      ),
    )
    expect(screen.getAllByText(/No check-in received/)).toHaveLength(2)
  })
})
