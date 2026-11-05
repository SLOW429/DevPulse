import {
  Bell,
  Check,
  Clock3,
  Pencil,
  Plus,
  ShieldAlert,
  Trash2,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { FormEvent } from 'react'
import {
  ApiError,
  createAlertRule,
  deleteAlertRule,
  getAlerts,
  getAlertRules,
  updateAlertRule,
} from '../api/client'
import { currentAccessToken } from '../auth/session'
import type { DashboardOutlet } from '../components/DashboardLayout'
import type {
  AlertIncident,
  AlertMetric,
  AlertOperator,
  AlertRule,
  AlertRulePayload,
  AlertSeverity,
} from '../types'

interface RuleForm {
  name: string
  deviceId: string
  metric: AlertMetric
  operator: AlertOperator
  threshold: string
  severity: AlertSeverity
  interval: string
  consecutive: string
}

const EMPTY_FORM: RuleForm = {
  name: '',
  deviceId: '',
  metric: 'cpu',
  operator: 'gt',
  threshold: '80',
  severity: 'warning',
  interval: '30',
  consecutive: '1',
}

const METRIC_LABELS: Record<AlertMetric, string> = {
  cpu: 'CPU usage',
  ram: 'Memory usage',
  disk: 'Disk usage',
  device_offline: 'Device offline',
}

export function AlertsPage() {
  const { snapshot } = useOutletContext<DashboardOutlet>()
  const [rules, setRules] = useState<AlertRule[]>([])
  const [incidents, setIncidents] = useState<AlertIncident[]>([])
  const [activeOnly, setActiveOnly] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<AlertRule | null>(null)
  const [form, setForm] = useState<RuleForm>({ ...EMPTY_FORM })
  const [formOpen, setFormOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const refresh = useCallback(async () => {
    const token = currentAccessToken()
    if (!token) {
      setLoading(false)
      setError('Your session has expired. Sign in again to manage alerts.')
      return
    }
    try {
      const [nextRules, nextAlerts] = await Promise.all([
        getAlertRules(token),
        getAlerts(token, { activeOnly, limit: 100 }),
      ])
      setRules(nextRules)
      setIncidents(nextAlerts.items)
      setError('')
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : 'Unable to load alert data. Please try again.',
      )
    } finally {
      setLoading(false)
    }
  }, [activeOnly])

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void refresh(), 0)
    const timer = window.setInterval(() => void refresh(), 15_000)
    return () => {
      window.clearTimeout(initialLoad)
      window.clearInterval(timer)
    }
  }, [refresh])

  function startCreate() {
    setEditing(null)
    setForm({ ...EMPTY_FORM })
    setFormOpen(true)
  }

  function startEdit(rule: AlertRule) {
    setEditing(rule)
    setFormOpen(true)
    setForm({
      name: rule.name,
      deviceId: rule.device_id === null ? '' : String(rule.device_id),
      metric: rule.metric,
      operator: rule.operator ?? 'gt',
      threshold: rule.threshold === null ? '' : String(rule.threshold),
      severity: rule.severity,
      interval: String(rule.evaluation_interval_seconds),
      consecutive: String(rule.consecutive_violations),
    })
  }

  async function saveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const token = currentAccessToken()
    if (!token) {
      setError('Your session has expired. Sign in again to manage alerts.')
      return
    }
    const offline = form.metric === 'device_offline'
    const payload: AlertRulePayload = {
      name: form.name.trim(),
      device_id: form.deviceId ? Number(form.deviceId) : null,
      metric: form.metric,
      operator: offline ? null : form.operator,
      threshold: Number(form.threshold),
      severity: form.severity,
      evaluation_interval_seconds: Number(form.interval),
      consecutive_violations: Number(form.consecutive),
      enabled: editing?.enabled ?? true,
    }
    setSaving(true)
    try {
      if (editing) await updateAlertRule(token, editing.id, payload)
      else await createAlertRule(token, payload)
      setEditing(null)
      setFormOpen(false)
      await refresh()
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : 'Unable to save this alert rule.',
      )
    } finally {
      setSaving(false)
    }
  }

  async function toggleRule(rule: AlertRule) {
    const token = currentAccessToken()
    if (!token) return
    try {
      await updateAlertRule(token, rule.id, { enabled: !rule.enabled })
      await refresh()
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to update the rule.')
    }
  }

  async function removeRule(rule: AlertRule) {
    const token = currentAccessToken()
    if (!token) return
    try {
      await deleteAlertRule(token, rule.id)
      await refresh()
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to delete the rule.')
    }
  }

  return (
    <>
      <section className="page-heading">
        <div>
          <p className="eyebrow"><span className="eyebrow-dot" /> ALERT MANAGEMENT</p>
          <h1>Alerts &amp; rules</h1>
          <p className="page-description">Define conditions and review incidents across your devices.</p>
        </div>
        <button className="button button-primary" type="button" onClick={startCreate}>
          <Plus size={17} /> New rule
        </button>
      </section>

      {error && <div className="inline-alert" role="alert">{error}</div>}

      <section className="alerts-panel">
        <div className="section-title-row">
          <div><h2>Incident history</h2><p>Active conditions and resolved incidents</p></div>
          <div className="alert-tabs" role="group" aria-label="Incident status">
            <button type="button" className={activeOnly ? 'alert-tab-active' : ''} onClick={() => setActiveOnly(true)}>Active</button>
            <button type="button" className={!activeOnly ? 'alert-tab-active' : ''} onClick={() => setActiveOnly(false)}>Resolved</button>
          </div>
        </div>
        {loading ? (
          <div className="alert-list-loading"><span className="loading-mark" /> Loading alerts…</div>
        ) : error && incidents.length === 0 ? (
          <div className="alert-load-error">Incident history is unavailable until the API responds.</div>
        ) : incidents.length === 0 ? (
          <div className="alerts-empty">
            <span className="empty-illustration"><Bell size={24} /></span>
            <strong>{activeOnly ? 'No active incidents' : 'No resolved incidents yet'}</strong>
            <p>{activeOnly ? 'When a rule condition is met, its incident will appear here.' : 'Resolved alert history will be available here.'}</p>
          </div>
        ) : (
          <div className="incident-list">
            {incidents.map((incident) => <IncidentCard key={incident.id} incident={incident} />)}
          </div>
        )}
      </section>

      <section className="alerts-panel alert-rules-panel">
        <div className="section-title-row">
          <div><h2>Alert rules</h2><p>Thresholds are evaluated against real device measurements</p></div>
          <span className="alert-rule-count">{rules.length} {rules.length === 1 ? 'rule' : 'rules'}</span>
        </div>
        {loading ? (
          <div className="alert-list-loading"><span className="loading-mark" /> Loading rules…</div>
        ) : error && rules.length === 0 ? (
          <div className="alert-load-error">Alert rules are unavailable until the API responds.</div>
        ) : rules.length === 0 ? (
          <div className="alerts-empty">
            <span className="empty-illustration"><ShieldAlert size={24} /></span>
            <strong>No alert rules configured</strong>
            <p>Create a CPU, memory, disk, or offline rule to start tracking incidents.</p>
            <button className="button button-secondary" type="button" onClick={startCreate}><Plus size={15} /> Create a rule</button>
          </div>
        ) : (
          <div className="alert-rule-list">
            {rules.map((rule) => (
              <article className={`alert-rule-card ${rule.enabled ? '' : 'rule-disabled'}`} key={rule.id}>
                <span className={`severity-mark severity-${rule.severity}`} />
                <div className="alert-rule-main">
                  <strong>{rule.name}</strong>
                  <span><i className={`severity-label severity-${rule.severity}`}>{rule.severity}</i> · {describeRule(rule)} · {rule.device_id === null ? 'All devices' : snapshot?.devices.find((device) => device.id === rule.device_id)?.name ?? `Device ${rule.device_id}`}</span>
                  <small>Every {rule.evaluation_interval_seconds}s · {rule.consecutive_violations} consecutive {rule.consecutive_violations === 1 ? 'violation' : 'violations'}</small>
                </div>
                <span className={`rule-state ${rule.enabled ? 'rule-enabled' : ''}`}>{rule.enabled ? 'Enabled' : 'Disabled'}</span>
                <div className="rule-actions">
                  <button type="button" className="icon-button" aria-label={`Edit ${rule.name}`} onClick={() => startEdit(rule)}><Pencil size={15} /></button>
                  <button type="button" className="text-button" onClick={() => void toggleRule(rule)}>{rule.enabled ? 'Disable' : 'Enable'}</button>
                  <button type="button" className="icon-button danger-icon" aria-label={`Delete ${rule.name}`} onClick={() => void removeRule(rule)}><Trash2 size={15} /></button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {formOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !saving) setFormOpen(false)
        }}>
          <section className="modal-card alert-rule-modal" role="dialog" aria-modal="true" aria-labelledby="alert-rule-title">
            <div className="modal-heading">
              <div><p className="eyebrow">RULE CONFIGURATION</p><h2 id="alert-rule-title">{editing ? 'Edit alert rule' : 'Create alert rule'}</h2></div>
              <button type="button" className="icon-button" aria-label="Close dialog" onClick={() => setFormOpen(false)}><X size={18} /></button>
            </div>
            <form className="alert-rule-form" onSubmit={(event) => void saveRule(event)}>
              <label>Rule name<input required maxLength={120} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
              <label>Metric<select value={form.metric} onChange={(event) => {
                const metric = event.target.value as AlertMetric
                setForm({
                  ...form,
                  metric,
                  threshold: metric === 'device_offline' ? '90' : '80',
                })
              }}>
                {Object.entries(METRIC_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
              </select></label>
              <label>Device scope<select value={form.deviceId} onChange={(event) => setForm({ ...form, deviceId: event.target.value })}>
                <option value="">All devices</option>
                {(snapshot?.devices ?? []).map((device) => <option value={device.id} key={device.id}>{device.name}</option>)}
              </select></label>
              {form.metric !== 'device_offline' && (
                <div className="rule-condition-fields">
                  <label>Condition<select value={form.operator} onChange={(event) => setForm({ ...form, operator: event.target.value as AlertOperator })}>
                    <option value="gt">Above (&gt;)</option><option value="gte">At least (≥)</option><option value="lt">Below (&lt;)</option><option value="lte">At most (≤)</option>
                  </select></label>
                  <ThresholdInput form={form} setForm={setForm} />
                </div>
              )}
              {form.metric === 'device_offline' && (
                <ThresholdInput form={form} setForm={setForm} />
              )}
              <div className="rule-condition-fields">
                <label>Severity<select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value as AlertSeverity })}>
                  <option value="info">Info</option><option value="warning">Warning</option><option value="critical">Critical</option>
                </select></label>
                <label>Evaluation interval (seconds)<input type="number" min="5" max="3600" required value={form.interval} onChange={(event) => setForm({ ...form, interval: event.target.value })} /></label>
              </div>
              <label>Consecutive violations<input type="number" min="1" max="10" required value={form.consecutive} onChange={(event) => setForm({ ...form, consecutive: event.target.value })} /></label>
              <div className="modal-actions"><button type="button" className="button button-secondary" onClick={() => setFormOpen(false)}>Cancel</button><button type="submit" className="button button-primary" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save changes' : 'Create rule'}</button></div>
            </form>
          </section>
        </div>
      )}
    </>
  )
}

function describeRule(rule: AlertRule): string {
  if (rule.metric === 'device_offline') {
    return `${METRIC_LABELS.device_offline} after ${rule.threshold ?? 90}s`
  }
  const operators: Record<AlertOperator, string> = {
    gt: '>',
    gte: '≥',
    lt: '<',
    lte: '≤',
  }
  return `${METRIC_LABELS[rule.metric]} ${operators[rule.operator ?? 'gt']} ${rule.threshold}%`
}

function ThresholdInput({
  form,
  setForm,
}: {
  form: RuleForm
  setForm: (next: RuleForm) => void
}) {
  const offline = form.metric === 'device_offline'
  return (
    <label>{offline ? 'Offline after (seconds)' : 'Threshold (%)'}
      <input
        type="number"
        min={offline ? 1 : 0}
        max={offline ? 86400 : 100}
        step={offline ? 1 : 0.1}
        required
        value={form.threshold}
        onChange={(event) => setForm({ ...form, threshold: event.target.value })}
      />
    </label>
  )
}

function IncidentCard({ incident }: { incident: AlertIncident }) {
  const delivery = incident.notifications.at(-1)
  return (
    <article className="incident-card">
      <span className={`severity-mark severity-${incident.severity}`} />
      <div className="incident-main">
        <div className="incident-title-row">
          <strong>{incident.rule_name ?? incident.metric_name}</strong>
          <i className={`severity-label severity-${incident.severity}`}>{incident.severity}</i>
          <span className={`incident-state incident-${incident.status}`}>{incident.status === 'firing' ? 'FIRING' : 'RESOLVED'}</span>
        </div>
        <p>{incident.message}</p>
        <div className="incident-meta"><span>{incident.device_name}</span><span><Clock3 size={12} /> {new Date(incident.triggered_at).toLocaleString()}</span>{incident.resolved_at && <span>Resolved {new Date(incident.resolved_at).toLocaleString()}</span>}</div>
      </div>
      {delivery && <span className={`delivery-state delivery-${delivery.status}`} title={delivery.last_error ?? undefined}>{delivery.status === 'delivered' ? <Check size={13} /> : <Clock3 size={13} />}{delivery.status}</span>}
    </article>
  )
}
