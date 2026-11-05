import { useEffect, useRef, useState } from 'react'
import {
  createWebSocketTicket,
  getDashboard,
  getDashboardSocketUrl,
} from '../api/client'
import { currentAccessToken } from '../auth/session'
import type { DashboardSnapshot } from '../types'

export function useDashboardStream() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [connected, setConnected] = useState(false)
  const [missingToken] = useState(() => currentAccessToken() === null)
  const socketRef = useRef<WebSocket | null>(null)
  const retryTimerRef = useRef(0)
  const retryDelayRef = useRef(1000)
  const activeRef = useRef(true)

  useEffect(() => {
    activeRef.current = true
    const token = currentAccessToken()
    if (!token) return

    void getDashboard(token)
      .then((data) => {
        if (!activeRef.current) return
        setSnapshot(data)
        setError('')
      })
      .catch((cause: unknown) => {
        if (activeRef.current) {
          setError(cause instanceof Error ? cause.message : 'Unable to load dashboard data')
        }
      })
      .finally(() => {
        if (activeRef.current) setLoading(false)
      })

    async function connect() {
      if (!activeRef.current) return
      try {
        const freshToken = currentAccessToken()
        if (!freshToken) return
        const ticket = await createWebSocketTicket(freshToken)
        if (!activeRef.current) return
        const connection = new WebSocket(getDashboardSocketUrl(ticket))
        socketRef.current = connection
        connection.onopen = () => {
          if (!activeRef.current) return
          retryDelayRef.current = 1000
          setConnected(true)
        }
        connection.onmessage = (event) => {
          if (!activeRef.current) return
          try {
            const data = JSON.parse(event.data) as DashboardSnapshot
            setSnapshot(data)
            setError('')
          } catch {
            setError('Received an unreadable dashboard update')
          }
        }
        connection.onerror = () => connection.close()
        connection.onclose = () => {
          if (!activeRef.current) return
          setConnected(false)
          retryTimerRef.current = window.setTimeout(() => {
            retryDelayRef.current = Math.min(retryDelayRef.current * 2, 30_000)
            void connect()
          }, retryDelayRef.current)
        }
      } catch {
        if (!activeRef.current) return
        setConnected(false)
        retryTimerRef.current = window.setTimeout(() => {
          retryDelayRef.current = Math.min(retryDelayRef.current * 2, 30_000)
          void connect()
        }, retryDelayRef.current)
      }
    }

    void connect()
    return () => {
      activeRef.current = false
      window.clearTimeout(retryTimerRef.current)
      socketRef.current?.close()
    }
  }, [])

  return {
    snapshot,
    loading: loading && !missingToken,
    error: missingToken ? 'Your session has expired. Please sign in again.' : error,
    connected,
    setError,
  }
}
