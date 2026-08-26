import { useEffect, useRef, useState } from 'react'

const GROUP_INVALIDATING_EVENTS = new Set([
  'expense_added',
  'expense_edited',
  'expense_deleted',
  'settlement_recorded',
  'activity_added',
  'balances_updated',
])
const INITIAL_RETRY_DELAY_MS = 1000
const MAX_RETRY_DELAY_MS = 30000

function getGroupWebSocketUrl(groupId, accessToken) {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const url = new URL(`/ws/groups/${groupId}`, apiBaseUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.searchParams.set('token', accessToken)
  return url.toString()
}

export default function useGroupLiveUpdates({
  groupId,
  accessToken,
  onGroupDataInvalidated,
  onOverallBalanceInvalidated,
}) {
  const [connectionStatus, setConnectionStatus] = useState('reconnecting')
  const groupInvalidationRef = useRef(onGroupDataInvalidated)
  const overallBalanceInvalidationRef = useRef(onOverallBalanceInvalidated)
  const connectedGroupRef = useRef(null)

  useEffect(() => {
    groupInvalidationRef.current = onGroupDataInvalidated
  }, [onGroupDataInvalidated])

  useEffect(() => {
    overallBalanceInvalidationRef.current = onOverallBalanceInvalidated
  }, [onOverallBalanceInvalidated])

  useEffect(() => {
    if (!groupId || !accessToken) return undefined

    let socket = null
    let retryTimer = null
    let invalidationTimer = null
    let groupInvalidationQueued = false
    let overallBalanceInvalidationQueued = false
    let retryAttempt = 0
    let isDisposed = false

    const queueInvalidation = (kind) => {
      if (kind === 'group') groupInvalidationQueued = true
      else overallBalanceInvalidationQueued = true

      if (invalidationTimer) return
      invalidationTimer = window.setTimeout(() => {
        invalidationTimer = null
        if (groupInvalidationQueued) {
          groupInvalidationQueued = false
          groupInvalidationRef.current()
        }
        if (overallBalanceInvalidationQueued) {
          overallBalanceInvalidationQueued = false
          overallBalanceInvalidationRef.current()
        }
      }, 100)
    }

    const scheduleReconnect = () => {
      if (isDisposed || retryTimer) return
      setConnectionStatus('reconnecting')
      const delay = Math.min(INITIAL_RETRY_DELAY_MS * (2 ** retryAttempt), MAX_RETRY_DELAY_MS)
      retryAttempt += 1
      retryTimer = window.setTimeout(() => {
        retryTimer = null
        connect()
      }, delay)
    }

    const connect = () => {
      if (isDisposed || socket) return

      try {
        socket = new WebSocket(getGroupWebSocketUrl(groupId, accessToken))
      } catch {
        socket = null
        scheduleReconnect()
        return
      }

      const activeSocket = socket
      activeSocket.onopen = () => {
        if (isDisposed || socket !== activeSocket) return
        const isReconnect = connectedGroupRef.current === String(groupId)
        connectedGroupRef.current = String(groupId)
        retryAttempt = 0
        setConnectionStatus('live')
        queueInvalidation('group')
        if (isReconnect) {
          queueInvalidation('overall')
        }
      }

      activeSocket.onmessage = (message) => {
        let event
        try {
          event = JSON.parse(message.data)
        } catch {
          return
        }

        if (String(event?.group_id) !== String(groupId)) return
        if (GROUP_INVALIDATING_EVENTS.has(event?.type)) queueInvalidation('group')
        if (event?.type === 'overall_balance_updated') queueInvalidation('overall')
      }

      activeSocket.onclose = () => {
        if (socket === activeSocket) socket = null
        if (!isDisposed) scheduleReconnect()
      }
    }

    connect()

    return () => {
      isDisposed = true
      if (retryTimer) window.clearTimeout(retryTimer)
      if (invalidationTimer) window.clearTimeout(invalidationTimer)
      if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
        socket.close(1000, 'Leaving group')
      }
      socket = null
    }
  }, [accessToken, groupId])

  return connectionStatus
}
