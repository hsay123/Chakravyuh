import { useState } from 'react'

const API_BASE = ''

export default function ApproveReject({ incident, onAction }) {
  const [approver, setApprover] = useState('')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)

  if (!incident || incident.state !== 'AWAITING_APPROVAL') return null

  const handleApprove = async () => {
    if (!approver.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/incidents/${incident.incident_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approver: approver.trim() }),
      })
      if (res.ok) {
        onAction()
        setApprover('')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    if (!approver.trim() || !reason.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/incidents/${incident.incident_id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approver: approver.trim(), reason: reason.trim() }),
      })
      if (res.ok) {
        onAction()
        setApprover('')
        setReason('')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2 h-2 rounded-full bg-[var(--color-warning)] pulse-dot" />
        <span className="text-xs font-mono font-bold text-[var(--color-warning)] uppercase">
          Operator Approval Required
        </span>
      </div>

      <div className="flex flex-col gap-2 mb-3">
        <input
          type="text"
          placeholder="Approver name / ID"
          value={approver}
          onChange={(e) => setApprover(e.target.value)}
          className="px-3 py-1.5 text-xs font-mono bg-[var(--color-surface)] border border-[var(--color-border)]
                     rounded text-white placeholder-[var(--color-muted)] focus:outline-none
                     focus:border-[var(--color-accent)]/50"
        />
        <input
          type="text"
          placeholder="Rejection reason (required for reject)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="px-3 py-1.5 text-xs font-mono bg-[var(--color-surface)] border border-[var(--color-border)]
                     rounded text-white placeholder-[var(--color-muted)] focus:outline-none
                     focus:border-[var(--color-accent)]/50"
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleApprove}
          disabled={loading || !approver.trim()}
          className="flex-1 px-3 py-2 text-xs font-mono font-bold rounded
                     bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/40
                     text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20
                     disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          {loading ? '...' : 'Approve'}
        </button>
        <button
          onClick={handleReject}
          disabled={loading || !approver.trim() || !reason.trim()}
          className="flex-1 px-3 py-2 text-xs font-mono font-bold rounded
                     bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/40
                     text-[var(--color-danger)] hover:bg-[var(--color-danger)]/20
                     disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          {loading ? '...' : 'Reject'}
        </button>
      </div>
    </div>
  )
}
