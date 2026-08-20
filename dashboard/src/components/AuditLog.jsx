import { useEffect, useState } from 'react'

const API_BASE = ''

export default function AuditLog({ open, onClose }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    fetch(`${API_BASE}/audit-log`)
      .then((r) => r.json())
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-xl max-h-[80vh] flex flex-col rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-mono font-bold text-white">Audit Log</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-white transition-colors text-lg cursor-pointer"
          >
            &times;
          </button>
        </div>
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="text-center text-[var(--color-muted)] font-mono text-xs">
              Loading...
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center text-[var(--color-muted)] font-mono text-xs">
              No audit entries yet
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {entries.map((entry, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 px-3 py-2 rounded border border-[var(--color-border)] bg-[var(--color-surface-alt)]"
                >
                  <span
                    className={`text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded ${
                      entry.action === 'approve'
                        ? 'bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
                        : 'bg-[var(--color-danger)]/10 text-[var(--color-danger)]'
                    }`}
                  >
                    {entry.action}
                  </span>
                  <span className="text-xs font-mono text-white">{entry.approver}</span>
                  <span className="text-[10px] font-mono text-[var(--color-muted)]">
                    {entry.incident_id.slice(0, 8)}...
                  </span>
                  {entry.reason && (
                    <span className="text-[10px] font-mono text-[var(--color-muted)] ml-auto truncate">
                      {entry.reason}
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-[var(--color-muted)] ml-auto shrink-0">
                    {new Date(entry.ts).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
