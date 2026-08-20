export default function RawTerminal({ events }) {
  const terminalEvents = events.slice(-50)

  return (
    <div className="flex flex-col gap-2 h-full">
      <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
        Raw Terminal
      </h2>
      <div className="flex-1 overflow-auto rounded border border-[var(--color-border)] bg-black p-2">
        <div className="flex flex-col gap-px font-mono text-[10px]">
          {terminalEvents.length === 0 ? (
            <span className="text-[var(--color-muted)]">$ waiting for output...</span>
          ) : (
            terminalEvents.map((ev, i) => {
              const time = ev.timestamp
                ? new Date(ev.timestamp).toLocaleTimeString()
                : ev.ts
                  ? new Date(ev.ts).toLocaleTimeString()
                  : '--:--:--'

              if (ev.event === 'decoy_event') {
                return (
                  <div key={i}>
                    <span className="text-[var(--color-muted)]">{time}</span>
                    <span className="text-[var(--color-accent)]">$ </span>
                    <span className="text-white">
                      ssh root@{ev.data.decoy_id}
                    </span>
                    {ev.data.raw_payload && (
                      <div className="pl-4 text-[var(--color-muted)]">
                        {ev.data.raw_payload}
                      </div>
                    )}
                  </div>
                )
              }

              if (ev.event === 'incident_updated') {
                return (
                  <div key={i}>
                    <span className="text-[var(--color-muted)]">{time}</span>
                    <span className="text-[var(--color-warning)]">[{ev.data.state}]</span>
                    <span className="text-[var(--color-muted)]">
                      {' '}{ev.data.decoy_id} → {ev.data.real_asset_id || '...'}
                    </span>
                  </div>
                )
              }

              return (
                <div key={i}>
                  <span className="text-[var(--color-muted)]">{time}</span>
                  <span className="text-[var(--color-muted)]"> {ev.event}: </span>
                  <span className="text-white">{JSON.stringify(ev.data).slice(0, 80)}</span>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
