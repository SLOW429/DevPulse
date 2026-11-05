import {
  Activity,
  Bell,
  ChevronDown,
  CircleHelp,
  Command,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  Radio,
  Settings2,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { useDashboardStream } from '../hooks/useDashboardStream'

export interface DashboardOutlet {
  snapshot: ReturnType<typeof useDashboardStream>['snapshot']
  loading: boolean
  error: string
  connected: boolean
  setError: (message: string) => void
}

export function DashboardLayout() {
  const { user, signOut } = useAuth()
  const live = useDashboardStream()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isDevicePage = location.pathname.startsWith('/devices/')
  const isAlertsPage = location.pathname === '/alerts'
  const pageTitle = isDevicePage ? 'Device details' : isAlertsPage ? 'Alerts' : 'Overview'

  return (
    <div className="app-shell">
      {mobileMenuOpen && (
        <button
          className="mobile-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileMenuOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <span className="brand-mark"><Activity size={20} strokeWidth={2.5} /></span>
          <span>devpulse</span>
          <button className="mobile-close" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)}><X size={18} /></button>
        </div>
        <div className="workspace-switcher">
          <span className="workspace-avatar">{user?.email.slice(0, 1).toUpperCase() ?? 'D'}</span>
          <span className="workspace-copy"><strong>My workspace</strong><small>Personal plan</small></span>
          <ChevronDown size={15} />
        </div>
        <div className="nav-section-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`} onClick={() => setMobileMenuOpen(false)}>
            <LayoutDashboard size={18} /> Overview
          </NavLink>
          <a className="nav-link" href="#devices" onClick={() => setMobileMenuOpen(false)}>
            <Monitor size={18} /> Devices
            <span className="nav-count">{live.snapshot?.devices.length ?? '—'}</span>
          </a>
        </nav>
        <div className="nav-section-label nav-section-spaced">PREFERENCES</div>
        <nav className="main-nav">
          <NavLink to="/alerts" className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`} onClick={() => setMobileMenuOpen(false)}>
            <Bell size={18} /> Alerts
          </NavLink>
          <button className="nav-link nav-placeholder" type="button" title="Workspace settings are not available yet">
            <Settings2 size={18} /> Settings <span className="coming-soon">SOON</span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card"><span className="help-icon"><CircleHelp size={17} /></span><span><strong>Need a hand?</strong><small>Read the getting started guide</small></span></div>
          <div className="sidebar-user">
            <span className="user-avatar">{user?.email.slice(0, 1).toUpperCase() ?? 'U'}</span>
            <span className="user-copy"><strong>{user?.email.split('@')[0]}</strong><small>{user?.email}</small></span>
            <button type="button" className="icon-button user-logout" onClick={signOut} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" aria-label="Open navigation" onClick={() => setMobileMenuOpen(true)}><Menu size={20} /></button>
            <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{pageTitle}</strong></div>
          </div>
          <div className="topbar-right">
            <div className={`connection-pill ${live.connected ? 'connection-live' : ''}`}>
              <span className="connection-dot" />
              {live.connected ? 'Live updates' : 'Connecting'}
            </div>
            <div className="topbar-divider" />
            <button className="topbar-help" type="button" title="Keyboard shortcuts are not available yet"><Command size={16} /><span>Help</span></button>
            <div className="topbar-avatar">{user?.email.slice(0, 1).toUpperCase()}</div>
          </div>
        </header>
        <main className="page-content">
          <Outlet context={live satisfies DashboardOutlet} />
        </main>
        <footer className="page-footer"><span>DevPulse Monitoring</span><span><Radio size={13} /> Data updates every 5 seconds</span></footer>
      </div>
    </div>
  )
}
