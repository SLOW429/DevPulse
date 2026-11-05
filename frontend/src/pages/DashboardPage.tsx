import {
  ArrowRight,
  Clock3,
  HardDrive,
  MemoryStick,
  Plus,
  Server,
  Wifi,
  X,
  Cpu,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import type { ReactNode } from 'react'
import { AddDeviceDialog } from '../components/AddDeviceDialog'
import type { DashboardOutlet } from '../components/DashboardLayout'
import type { Device } from '../types'

export function DashboardPage() {
  const { snapshot, loading, error, connected, setError } =
    useOutletContext<DashboardOutlet>()
  const [showAddDevice, setShowAddDevice] = useState(false)
  const devices = snapshot?.devices ?? []
  const failedToLoad = Boolean(error && !snapshot)
  const metrics = devices.flatMap((device) =>
    device.latest_metric ? [device.latest_metric] : [],
  )
  const average = (key: 'cpu_percent' | 'ram_percent' | 'disk_percent') =>
    metrics.length
      ? metrics.reduce((sum, metric) => sum + metric[key], 0) / metrics.length
      : null
  const networkSent = metrics.reduce((sum, metric) => sum + metric.net_bytes_sent, 0)
  const networkReceived = metrics.reduce((sum, metric) => sum + metric.net_bytes_recv, 0)
  const longestUptime = metrics.reduce(
    (max, metric) => Math.max(max, metric.uptime_seconds),
    0,
  )
  const onlineCount = devices.filter((device) => device.status === 'online').length
  const offlineCount = devices.filter((device) => device.status === 'offline').length

  return (
    <>
      <section className="page-heading">
        <div>
          <p className="eyebrow"><span className="eyebrow-dot" /> INFRASTRUCTURE OVERVIEW</p>
          <h1>Good to see you.</h1>
          <p className="page-description">Here’s the latest from your monitored infrastructure.</p>
        </div>
        <div className="heading-actions">
          <span className={`sync-label ${connected ? 'sync-ok' : ''}`}><span className="sync-dot" />{connected ? 'Live sync active' : 'Reconnecting'}</span>
          <button className="button button-primary" type="button" onClick={() => setShowAddDevice(true)}><Plus size={17} /> Add device</button>
        </div>
      </section>
      {error && !failedToLoad && (
        <div className="inline-alert" role="alert">
          <span>{error}</span><button type="button" className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button>
        </div>
      )}
      <div className="section-title-row">
        <div><h2>Fleet health</h2><p>Live status across your devices</p></div>
        <span className="last-updated">{snapshot ? `Updated ${new Date(snapshot.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : 'Waiting for first update'}</span>
      </div>
      {loading && !snapshot ? (
        <div className="stats-grid" aria-label="Loading dashboard">
          {Array.from({ length: 6 }, (_, index) => <div className="stat-card skeleton-card" key={index}><span className="skeleton-line" /><span className="skeleton-line skeleton-value" /></div>)}
        </div>
      ) : failedToLoad ? (
        <div className="data-error-card" role="alert">
          <Wifi size={19} />
          <div><strong>Dashboard data is unavailable</strong><span>{error}</span><small>Live updates will retry automatically.</small></div>
        </div>
      ) : (
        <div className="stats-grid">
          <StatCard label="Registered devices" value={String(devices.length)} icon={<Server size={18} />} tone="blue" detail={`${onlineCount} currently online`} />
          <StatCard label="CPU utilization" value={formatPercent(average('cpu_percent'))} icon={<Cpu size={18} />} tone="violet" detail={`${onlineCount} reporting hosts`} progress={average('cpu_percent')} />
          <StatCard label="Memory usage" value={formatPercent(average('ram_percent'))} icon={<MemoryStick size={18} />} tone="mint" detail="Across latest samples" progress={average('ram_percent')} />
          <StatCard label="Disk utilization" value={formatPercent(average('disk_percent'))} icon={<HardDrive size={18} />} tone="amber" detail="Average reported usage" progress={average('disk_percent')} />
          <StatCard label="Network counters" value={metrics.length ? `${formatBytes(networkReceived + networkSent)}` : '—'} icon={<Wifi size={18} />} tone="sky" detail={metrics.length ? `↑ ${formatBytes(networkSent)} sent · ↓ ${formatBytes(networkReceived)} received` : 'Waiting for agent data'} />
          <StatCard label="Longest uptime" value={metrics.length ? formatUptime(longestUptime) : '—'} icon={<Clock3 size={18} />} tone="rose" detail={`${offlineCount} offline · ${devices.length - onlineCount - offlineCount} awaiting check-in`} />
        </div>
      )}

      <section className="devices-section" id="devices">
        <div className="section-title-row device-section-heading">
          <div><h2>Your devices</h2><p>Monitor health and inspect recent performance</p></div>
          <div className="device-count"><span className="status-dot status-online" />{onlineCount} online <span className="count-divider" />{offlineCount} offline</div>
        </div>
        {loading && !snapshot ? (
          <div className="devices-loading"><span className="loading-mark" /> Loading registered devices…</div>
        ) : failedToLoad ? null : devices.length === 0 ? (
          <div className="empty-state">
            <div className="empty-illustration"><Server size={29} /></div>
            <h3>No devices in your workspace yet</h3>
            <p>Add your first host to start collecting real-time CPU, memory, disk, network, and uptime metrics.</p>
            <button className="button button-primary" type="button" onClick={() => setShowAddDevice(true)}><Plus size={17} /> Register your first device</button>
          </div>
        ) : (
          <div className="device-table-wrap">
            <table className="device-table">
              <thead><tr><th>DEVICE</th><th>STATUS</th><th>CPU</th><th>MEMORY</th><th>DISK</th><th>NETWORK</th><th>UPTIME</th><th /></tr></thead>
              <tbody>
                {devices.map((device) => <DeviceRow key={device.id} device={device} />)}
              </tbody>
            </table>
            <div className="mobile-device-list">{devices.map((device) => <MobileDeviceCard key={device.id} device={device} />)}</div>
          </div>
        )}
      </section>
      {showAddDevice && (
        <AddDeviceDialog
          onClose={() => setShowAddDevice(false)}
          onCreated={() => setError('')}
        />
      )}
    </>
  )
}

function StatCard({
  label,
  value,
  icon,
  tone,
  detail,
  progress,
}: {
  label: string
  value: string
  icon: ReactNode
  tone: string
  detail: string
  progress?: number | null
}) {
  return (
    <article className="stat-card">
      <div className="stat-card-top"><span className={`stat-icon icon-${tone}`}>{icon}</span><span className="stat-card-label">{label}</span></div>
      <div className="stat-value">{value}</div>
      <div className="stat-foot"><span>{detail}</span>{progress !== undefined && progress !== null && <span className="mini-progress"><i style={{ width: `${Math.min(progress, 100)}%` }} /></span>}</div>
    </article>
  )
}

function DeviceRow({ device }: { device: Device }) {
  const metric = device.latest_metric
  return (
    <tr>
      <td><Link to={`/devices/${device.id}`} className="device-name-link"><span className="device-avatar"><Server size={17} /></span><span className="device-name-copy"><strong>{device.name}</strong><small>{device.hostname ?? device.os ?? `Agent ${device.agent_id.slice(0, 8)}`}</small></span></Link></td>
      <td><StatusBadge status={device.status} /></td>
      <td><MetricCell value={metric?.cpu_percent} /></td>
      <td><MetricCell value={metric?.ram_percent} /></td>
      <td><MetricCell value={metric?.disk_percent} /></td>
      <td><span className="network-cell">{metric ? `${formatBytes(metric.net_bytes_sent)} ↑` : '—'}<small>{metric ? `${formatBytes(metric.net_bytes_recv)} ↓` : 'No sample'}</small></span></td>
      <td><span className="table-uptime">{metric ? formatUptime(metric.uptime_seconds) : '—'}</span></td>
      <td><Link className="row-arrow" to={`/devices/${device.id}`} aria-label={`View ${device.name} details`}><ArrowRight size={16} /></Link></td>
    </tr>
  )
}

function MobileDeviceCard({ device }: { device: Device }) {
  const metric = device.latest_metric
  return (
    <Link className="mobile-device-card" to={`/devices/${device.id}`}>
      <span className="device-avatar"><Server size={17} /></span>
      <span className="mobile-device-copy"><strong>{device.name}</strong><small>{device.hostname ?? device.os ?? 'Monitoring agent'}</small><StatusBadge status={device.status} /></span>
      <span className="mobile-device-metrics"><span><Cpu size={13} /> {metric ? `${metric.cpu_percent.toFixed(0)}%` : '—'}</span><span><MemoryStick size={13} /> {metric ? `${metric.ram_percent.toFixed(0)}%` : '—'}</span></span>
      <ArrowRight size={16} />
    </Link>
  )
}

export function StatusBadge({ status }: { status: Device['status'] }) {
  return <span className={`status-badge status-${status}`}><i />{status === 'unknown' ? 'Awaiting data' : status}</span>
}

function MetricCell({ value }: { value?: number }) {
  if (value === undefined) return <span className="metric-muted">—</span>
  const color = value >= 85 ? 'metric-high' : value >= 65 ? 'metric-warn' : 'metric-normal'
  return <span className={`metric-cell ${color}`}><i style={{ width: `${Math.min(value, 100)}%` }} /><strong>{value.toFixed(1)}%</strong></span>
}

function formatPercent(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let amount = bytes
  let index = -1
  do {
    amount /= 1024
    index++
  } while (amount >= 1024 && index < units.length - 1)
  return `${amount.toFixed(1)} ${units[index]}`
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}m` : `${minutes}m`
}
