import { useState, type FormEvent } from 'react'
import { Check, Copy, Monitor, X } from 'lucide-react'
import { ApiError, createDevice } from '../api/client'
import { currentAccessToken } from '../auth/session'
import type { AgentCredential } from '../types'

interface AddDeviceDialogProps {
  onClose: () => void
  onCreated: () => void
}

export function AddDeviceDialog({ onClose, onCreated }: AddDeviceDialogProps) {
  const [name, setName] = useState('')
  const [hostname, setHostname] = useState('')
  const [os, setOs] = useState('')
  const [credential, setCredential] = useState<AgentCredential | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const token = currentAccessToken()
    if (!token) {
      setError('Your session has expired. Please sign in again.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const result = await createDevice(token, {
        name,
        ...(hostname.trim() ? { hostname: hostname.trim() } : {}),
        ...(os.trim() ? { os: os.trim() } : {}),
      })
      setCredential(result)
      onCreated()
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to register this device')
    } finally {
      setBusy(false)
    }
  }

  async function copyCredential() {
    if (!credential) return
    try {
      await navigator.clipboard.writeText(credential.agent_key)
      setCopied(true)
    } catch {
      setError('Clipboard access is unavailable. Select and copy the key manually.')
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="device-modal-title">
        <button className="modal-close icon-button" type="button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button>
        {credential ? (
          <>
            <div className="modal-icon modal-icon-success"><Check size={21} /></div>
            <p className="eyebrow">DEVICE REGISTERED</p>
            <h2 id="device-modal-title">{credential.device.name} is ready</h2>
            <p className="modal-description">Copy this agent key now. For security, it won’t be shown again.</p>
            <div className="credential-box"><code>{credential.agent_key}</code><button className="button button-secondary copy-button" type="button" onClick={() => void copyCredential()}>{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? 'Copied' : 'Copy'}</button></div>
            <p className="credential-hint">Set it as <code>DEVPULSE_AGENT_KEY</code> on the monitored host.</p>
            <button className="button button-primary button-full" type="button" onClick={onClose}>Done</button>
          </>
        ) : (
          <>
            <div className="modal-icon"><Monitor size={21} /></div>
            <p className="eyebrow">NEW MONITORED HOST</p>
            <h2 id="device-modal-title">Add a device</h2>
            <p className="modal-description">Register a host, then install its monitoring agent.</p>
            <form className="device-form" onSubmit={(event) => void submit(event)}>
              {error && <div className="form-alert" role="alert">{error}</div>}
              <label htmlFor="device-name">Device name</label>
              <input id="device-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Production API" minLength={1} maxLength={100} required />
              <label htmlFor="device-hostname">Hostname <span className="optional-label">OPTIONAL</span></label>
              <input id="device-hostname" value={hostname} onChange={(event) => setHostname(event.target.value)} placeholder="api-01.example.com" maxLength={255} />
              <label htmlFor="device-os">Operating system <span className="optional-label">OPTIONAL</span></label>
              <input id="device-os" value={os} onChange={(event) => setOs(event.target.value)} placeholder="Ubuntu 24.04" maxLength={100} />
              <div className="modal-actions"><button className="button button-secondary" type="button" onClick={onClose}>Cancel</button><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Registering…' : 'Register device'}</button></div>
            </form>
          </>
        )}
      </section>
    </div>
  )
}
