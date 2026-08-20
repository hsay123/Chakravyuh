import { useState, useEffect, useCallback } from 'react'
import useWebSocket from './hooks/useWebSocket'
import Header from './components/Header'
import NetworkMap from './components/NetworkMap'
import PipelineStatus from './components/PipelineStatus'
import DiffViewer from './components/DiffViewer'
import EventFeed from './components/EventFeed'
import ApproveReject from './components/ApproveReject'
import AuditLog from './components/AuditLog'
import RawTerminal from './components/RawTerminal'

const WS_URL = `ws://${window.location.host}/stream`
const API_BASE = ''

export default function App() {
  const { connected, subscribe } = useWebSocket(WS_URL)

  const [incidents, setIncidents] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [events, setEvents] = useState([])
  const [auditOpen, setAuditOpen] = useState(false)

  const fetchIncidents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/incidents`)
      if (res.ok) setIncidents(await res.json())
    } catch {
      // backend not reachable yet
    }
  }, [])

  const fetchIncidentDetail = useCallback(async (id) => {
    if (!id) return null
    try {
      const res = await fetch(`${API_BASE}/incidents/${id}`)
      if (res.ok) return await res.json()
    } catch {
      // ignore
    }
    return null
  }, [])

  useEffect(() => {
    fetchIncidents()
  }, [fetchIncidents])

  useEffect(() => {
    const unsub = subscribe((msg) => {
      setEvents((prev) => [...prev.slice(-200), msg])

      if (msg.event === 'incident_created') {
        setIncidents((prev) => [msg.data, ...prev])
        if (!selectedId) setSelectedId(msg.data.incident_id)
      }

      if (msg.event === 'incident_updated') {
        setIncidents((prev) =>
          prev.map((inc) =>
            inc.incident_id === msg.data.incident_id ? { ...inc, ...msg.data } : inc
          )
        )
      }

      if (msg.event === 'audit_entry') {
        // handled in real-time via the event feed
      }
    })
    return unsub
  }, [subscribe, selectedId])

  const selectedIncident = incidents.find((inc) => inc.incident_id === selectedId) || null
  const [selectedDetail, setSelectedDetail] = useState(null)

  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null)
      return
    }
    fetchIncidentDetail(selectedId).then(setSelectedDetail)
  }, [selectedId, fetchIncidentDetail, incidents])

  const activeIncident = selectedDetail || selectedIncident

  const handleSelect = (id) => setSelectedId(id)

  const handleAction = () => {
    fetchIncidents()
    if (selectedId) {
      fetchIncidentDetail(selectedId).then(setSelectedDetail)
    }
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header connected={connected} onOpenAudit={() => setAuditOpen(true)} />

      <div className="flex-1 grid grid-cols-[260px_1fr] grid-rows-[1fr_auto_1fr] gap-px bg-[var(--color-border)] min-h-0">
        {/* Network Map */}
        <div className="bg-[var(--color-surface)] p-3 row-span-2 overflow-auto">
          <NetworkMap
            incidents={incidents}
            selectedId={selectedId}
            onSelect={handleSelect}
          />
        </div>

        {/* Pipeline Status */}
        <div className="bg-[var(--color-surface)] p-3 overflow-auto">
          <PipelineStatus incident={activeIncident} />
        </div>

        {/* Diff + Approve/Reject */}
        <div className="bg-[var(--color-surface)] p-3 overflow-auto">
          <div className="flex flex-col gap-3 h-full">
            <DiffViewer diff={activeIncident?.patch_diff} />
            <ApproveReject incident={activeIncident} onAction={handleAction} />
          </div>
        </div>

        {/* Bottom: Event Feed + Raw Terminal */}
        <div className="col-span-2 grid grid-cols-[1fr_320px] gap-px bg-[var(--color-border)]">
          <div className="bg-[var(--color-surface)] p-3 overflow-hidden">
            <EventFeed events={events} />
          </div>
          <div className="bg-[var(--color-surface)] p-3 overflow-hidden">
            <RawTerminal events={events} />
          </div>
        </div>
      </div>

      <AuditLog open={auditOpen} onClose={() => setAuditOpen(false)} />
    </div>
  )
}
