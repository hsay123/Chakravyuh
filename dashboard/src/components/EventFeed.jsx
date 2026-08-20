import { useEffect, useRef } from 'react'

const TECHNIQUE_COLORS = {
  buffer_overflow_probe: 'text-[var(--color-danger)]',
  credential_bruteforce: 'text-[var(--color-warning)]',
  command_injection: 'text-[var(--color-danger)]',
  default: 'text-[var(--color-muted)]',
}

export default function EventFeed({ events }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  if (events.length === 0) {
    return (
      <div className="flex flex-col gap-2 h-full">
        <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
          Live Event Feed
        </h2>
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--color-muted)] font-mono">
          Waiting for events...
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
          Live Event Feed
        </h2>
        <span className="text-[10px] font-mono text-[var(--color-muted)]">
          {events.length} events
        </span>
      </div>
      <div className="flex-1 overflow-auto rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-2">
        <div className="flex flex-col gap-0.5">
          {events.map((ev, i) => {
            const time = ev.timestamp
              ? new Date(ev.timestamp).toLocaleTimeString()
              : ev.ts
                ? new Date(ev.ts).toLocaleTimeString()
                : '--:--:--'

            if (ev.event === 'decoy_event') {
              const d = ev.data
              const techColor = TECHNIQUE_COLORS[d.technique] || TECHNIQUE_COLORS.default
              return (
                <div key={i} className="text-[11px] font-mono flex gap-2 items-start">
                  <span className="text-[var(--color-muted)] shrink-0">{time}</span>
                  <span className="text-[var(--color-accent)]">ATTACK</span>
                  <span className="text-[var(--color-muted)]">{d.source_ip}</span>
                  <span className="text-[var(--color-danger)]">&rarr;</span>
                  <span className="text-white">{d.decoy_id}</span>
                  <span className={techColor}>[{d.technique}]</span>
                </div>
              )
            }

            if (ev.event === 'incident_created') {
              return (
                <div key={i} className="text-[11px] font-mono flex gap-2 items-start">
                  <span className="text-[var(--color-muted)] shrink-0">{time}</span>
                  <span className="text-[var(--color-warning)]">NEW</span>
                  <span className="text-white">{ev.data.decoy_id}</span>
                  <span className="text-[var(--color-muted)]">
                    &rarr; {ev.data.real_asset_id || 'pending match'}
                  </span>
                </div>
              )
            }

            if (ev.event === 'incident_updated') {
              const d = ev.data
              return (
                <div key={i} className="text-[11px] font-mono flex gap-2 items-start">
                  <span className="text-[var(--color-muted)] shrink-0">{time}</span>
                  <span className="text-[var(--color-accent)]">{d.state}</span>
                  <span className="text-white">{d.decoy_id}</span>
                  {d.patch_diff && (
                    <span className="text-[var(--color-accent)]">[patch ready]</span>
                  )}
                </div>
              )
            }

            if (ev.event === 'audit_entry') {
              const d = ev.data
              return (
                <div key={i} className="text-[11px] font-mono flex gap-2 items-start">
                  <span className="text-[var(--color-muted)] shrink-0">{time}</span>
                  <span
                    className={
                      d.action === 'approve'
                        ? 'text-[var(--color-accent)]'
                        : 'text-[var(--color-danger)]'
                    }
                  >
                    {d.action.toUpperCase()}
                  </span>
                  <span className="text-white">{d.approver}</span>
                  <span className="text-[var(--color-muted)]">
                    {d.incident_id.slice(0, 8)}...
                  </span>
                </div>
              )
            }

            return (
              <div key={i} className="text-[11px] font-mono flex gap-2 items-start">
                <span className="text-[var(--color-muted)] shrink-0">{time}</span>
                <span className="text-[var(--color-muted)]">{ev.event || 'unknown'}</span>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
