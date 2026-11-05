import {
  ArrowLeft,
  ArrowDownLeft,
  ArrowUpRight,
  Clock3,
  HardDrive,
  MemoryStick,
  RefreshCw,
  Wifi,
  Cpu,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import type { ReactNode } from 'react'
import { ApiError, getDeviceMetrics } from '../api/client'
import { currentAccessToken } from '../auth/session'
import { MetricChart } from '../components/MetricChart'
import { StatusBadge } from './DashboardPage'
import type { DashboardOutlet } from '../components/DashboardLayout'
import type { Metric } from '../types'

const RANGE_OPTIONS = [
  { label: '1 hour', hours: 1 },
  { label: '24 hours', hours: 24 },
  { label: '7 days', hours: 168 },
]

export function DeviceDetailPage() {
  const { deviceId } = useParams()
  const {
    snapshot,
    loading: dashboardLoading,
    connected,
    error: dashboardError,
  } =
    useOutletContext<DashboardOutlet>()
  const [history, setHistory] = useState<{
    deviceId: number
    metrics: Metric[]
    loading: boolean
    error: string
  }>({ deviceId: Number(deviceId), metrics: [], loading: true, error: '' })
  const [range, setRange] = useState(24)
  const id = Number(deviceId)
  const device = snapshot?.devices.find((item) => item.id === id)
  const historyMatchesDevice = history.deviceId === id
  const historyLoading = !historyMatchesDevice || history.loading
  const error = historyMatchesDevice ? history.error : ''

  useEffect(() => {
    let active = true
    const token = currentAccessToken()
    if (!token || !Number.isInteger(id) || id < 1) return
    void getDeviceMetrics(token, id)
      .then((history) => {
        if (active) {
          setHistory({ deviceId: id, metrics: history, loading: false, error: '' })
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setHistory({
            deviceId: id,
            metrics: [],
            loading: false,
            error: cause instanceof ApiError ? cause.message : 'Unable to load metric history',
          })
        }
      })
    return () => {
      active = false
    }
  }, [id])

  const metrics = useMemo(() => {
    const stored = historyMatchesDevice ? history.metrics : []
    const latest = device?.latest_metric
    if (!latest || stored.some((metric) => metric.id === latest.id)) return stored
    return [latest, ...stored].slice(0, 500)
  }, [device?.latest_metric, history.metrics, historyMatchesDevice])

  const filteredMetrics = useMemo(() => {
    const newest = metrics.reduce(
      (max, metric) => Math.max(max, new Date(metric.collected_at).getTime()),
      0,
    )
    const cutoff = newest - range * 60 * 60 * 1000
    return metrics.filter((metric) => new Date(metric.collected_at).getTime() >= cutoff)
  }, [metrics, range])

  if (!Number.isInteger(id) || id < 1) return <ErrorState message="That device address is not valid." />
  if (dashboardLoading && !snapshot) return <div className="page-loading"><span className="loading-mark" /> Loading device…</div>
  if (!snapshot) return <ErrorState message={dashboardError || 'Dashboard data is unavailable.'} />
  if (snapshot && !device) return <ErrorState message="This device doesn’t exist or you don’t have access to it." />

  const latest = device?.latest_metric
  const latestSeen = device?.last_seen_at
    ? new Date(device.last_seen_at).toLocaleString()
    : 'No check-in received'

  return (
    <>
      <Link to="/" className="back-link"><ArrowLeft size={16} /> All devices</Link>
      <section className="detail-heading">
        <div className="detail-device-avatar"><Cpu size={24} /></div>
        <div className="detail-title">
          <div className="detail-name-line"><h1>{device?.name ?? 'Device details'}</h1>{device && <StatusBadge status={device.status} />}</div>
          <p>{device?.hostname ?? device?.os ?? `Agent ${device?.agent_id.slice(0, 8) ?? ''}`}</p>
        </div>
        <div className="detail-live-status"><span className={`connection-dot ${connected ? 'connection-dot-live' : ''}`} />{connected ? 'Live monitoring' : 'Reconnecting'}</div>
      </section>
      {error && <div className="inline-alert" role="alert">{error}</div>}
      <section className="detail-metrics-grid">
        <DetailMetric label="CPU utilization" value={latest ? `${latest.cpu_percent.toFixed(1)}%` : '—'} icon={<Cpu size={18} />} tone="violet" />
        <DetailMetric label="Memory usage" value={latest ? `${latest.ram_percent.toFixed(1)}%` : '—'} icon={<MemoryStick size={18} />} tone="mint" />
        <DetailMetric label="Disk utilization" value={latest ? `${latest.disk_percent.toFixed(1)}%` : '—'} icon={<HardDrive size={18} />} tone="amber" />
        <DetailMetric label="System uptime" value={latest ? formatUptime(latest.uptime_seconds) : '—'} icon={<Clock3 size={18} />} tone="blue" />
      </section>
      <section className="history-section">
        <div className="history-heading">
          <div><h2>Performance history</h2><p>Real measurements collected by this device’s agent</p></div>
          <div className="range-selector" aria-label="History time range">
            {RANGE_OPTIONS.map((option) => <button key={option.hours} type="button" className={range === option.hours ? 'range-active' : ''} onClick={() => setRange(option.hours)}>{option.label}</button>)}
          </div>
        </div>
        {historyLoading ? (
          <div className="history-loading"><span className="loading-mark" /> Loading historical metrics…</div>
        ) : metrics.length === 0 ? (
          <div className="history-empty"><div className="empty-illustration"><Wifi size={26} /></div><h3>No measurements yet</h3><p>Once this device’s agent checks in, its CPU, memory, disk, network, and uptime history will appear here.</p><span>Last check-in: {latestSeen}</span></div>
        ) : (
          <div className="charts-grid">
            <ChartPanel title="CPU utilization" subtitle={`${filteredMetrics.length} data points`} color="#7775e8" metrics={filteredMetrics} lines={[{ key: 'cpu_percent', label: 'CPU', color: '#7775e8' }]} />
            <ChartPanel title="Memory usage" subtitle="Virtual memory utilization" color="#24a47b" metrics={filteredMetrics} lines={[{ key: 'ram_percent', label: 'Memory', color: '#24a47b' }]} />
            <ChartPanel title="Disk utilization" subtitle="Root volume usage" color="#d79a35" metrics={filteredMetrics} lines={[{ key: 'disk_percent', label: 'Disk', color: '#d79a35' }]} />
            <ChartPanel title="Network activity" subtitle="Cumulative bytes transferred" color="#4b8dd8" metrics={filteredMetrics} unit="bytes" lines={[{ key: 'net_bytes_sent', label: 'Sent', color: '#4b8dd8' }, { key: 'net_bytes_recv', label: 'Received', color: '#24a47b' }]} />
          </div>
        )}
      </section>
      <section className="detail-meta">
        <span><Clock3 size={15} /> Last seen: {latestSeen}</span>
        <span><Wifi size={15} /> {latest ? `Sent ${formatBytes(latest.net_bytes_sent)} · Received ${formatBytes(latest.net_bytes_recv)}` : 'Network metrics unavailable'}</span>
        {device?.last_seen_at && <span><RefreshCw size={15} /> Sample received {new Date(latest?.received_at ?? device.last_seen_at).toLocaleTimeString()}</span>}
      </section>
    </>
  )
}

function DetailMetric({ label, value, icon, tone }: { label: string; value: string; icon: ReactNode; tone: string }) {
  return <article className="detail-metric-card"><span className={`stat-icon icon-${tone}`}>{icon}</span><span className="detail-metric-label">{label}</span><strong>{value}</strong></article>
}

function ChartPanel({
  title,
  subtitle,
  color,
  metrics,
  lines,
  unit,
}: {
  title: string
  subtitle: string
  color: string
  metrics: Metric[]
  lines: { key: keyof Metric; label: string; color: string }[]
  unit?: string
}) {
  return (
    <article className="chart-panel">
      <div className="chart-panel-heading"><span className="chart-key" style={{ backgroundColor: color }} /><div><h3>{title}</h3><p>{subtitle}</p></div></div>
      <MetricChart metrics={metrics} lines={lines} unit={unit} />
      {unit === 'bytes' && <div className="chart-lines-legend"><span><i style={{ backgroundColor: lines[0].color }} />Sent <ArrowUpRight size={13} /></span><span><i style={{ backgroundColor: lines[1].color }} />Received <ArrowDownLeft size={13} /></span></div>}
    </article>
  )
}

function ErrorState({ message }: { message: string }) {
  return <div className="empty-state"><div className="empty-illustration"><Wifi size={26} /></div><h3>Unable to open device</h3><p>{message}</p><Link className="button button-secondary" to="/">Back to overview</Link></div>
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}m` : `${minutes}m`
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
