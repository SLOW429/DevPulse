export type DeviceStatus = 'online' | 'offline' | 'unknown'

export interface Metric {
  id: number
  device_id: number
  collected_at: string
  received_at: string
  cpu_percent: number
  ram_percent: number
  disk_percent: number
  net_bytes_sent: number
  net_bytes_recv: number
  uptime_seconds: number
}

export interface Device {
  id: number
  agent_id: string
  name: string
  hostname: string | null
  os: string | null
  status: DeviceStatus
  last_seen_at: string | null
  latest_metric: Metric | null
}

export interface DashboardSnapshot {
  generated_at: string
  devices: Device[]
}

export interface User {
  id: number
  email: string
  role: 'admin' | 'viewer'
  is_active: boolean
  created_at: string
}

export interface AgentCredential {
  device: Omit<Device, 'latest_metric'> & { latest_metric?: Metric | null }
  agent_key: string
}

export type AlertMetric = 'cpu' | 'ram' | 'disk' | 'device_offline'
export type AlertOperator = 'gt' | 'gte' | 'lt' | 'lte'
export type AlertSeverity = 'info' | 'warning' | 'critical'
export type AlertState = 'firing' | 'resolved'
export type NotificationStatus =
  | 'pending'
  | 'sending'
  | 'delivered'
  | 'disabled'
  | 'failed'

export interface AlertRule {
  id: number
  owner_id: number
  device_id: number | null
  name: string
  metric: AlertMetric
  operator: AlertOperator | null
  threshold: number | null
  severity: AlertSeverity
  evaluation_interval_seconds: number
  consecutive_violations: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AlertNotification {
  id: number
  event_type: 'fired' | 'resolved'
  status: NotificationStatus
  attempts: number
  next_attempt_at: string | null
  delivered_at: string | null
  last_error: string | null
  created_at: string
}

export interface AlertIncident {
  id: number
  rule_id: number | null
  rule_name: string | null
  device_id: number
  device_name: string
  metric: AlertMetric | null
  metric_name: string
  severity: AlertSeverity
  status: AlertState
  threshold: number | null
  observed_value: number | null
  message: string
  triggered_at: string
  resolved_at: string | null
  notifications: AlertNotification[]
}

export interface AlertPage {
  items: AlertIncident[]
  total: number
  limit: number
  offset: number
}

export interface AlertRulePayload {
  name: string
  device_id: number | null
  metric: AlertMetric
  operator: AlertOperator | null
  threshold: number | null
  severity: AlertSeverity
  evaluation_interval_seconds: number
  consecutive_violations: number
  enabled: boolean
}
