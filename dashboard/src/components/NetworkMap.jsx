const ASSETS = [
  { id: 'libpng-target', label: 'libpng-target', type: 'real' },
  { id: 'fake-ssh-honeypot', label: 'fake-ssh-honeypot', type: 'decoy' },
]

export default function NetworkMap({ incidents, selectedId, onSelect }) {
  const hitDecoys = new Set(
    incidents
      .filter((inc) => inc.state !== 'DETECTED')
      .map((inc) => inc.decoy_id)
  )

  return (
    <div className="flex flex-col gap-2 h-full">
      <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
        Network Map
      </h2>
      <div className="flex-1 flex flex-col gap-1.5">
        {ASSETS.map((asset) => {
          const isDecoy = asset.type === 'decoy'
          const isHit = hitDecoys.has(asset.id)
          const linkedIncident = incidents.find(
            (inc) => inc.decoy_id === asset.id && inc.state !== 'DEPLOYED' && inc.state !== 'REJECTED'
          )

          return (
            <button
              key={asset.id}
              onClick={() => linkedIncident && onSelect(linkedIncident.incident_id)}
              className={`
                flex items-center gap-2 px-3 py-2 rounded text-left text-sm font-mono transition-all
                border cursor-pointer
                ${isHit
                  ? 'border-[var(--color-danger)]/40 bg-[var(--color-danger)]/5 glow-red'
                  : 'border-[var(--color-border)] bg-[var(--color-surface-alt)]'
                }
                ${linkedIncident?.incident_id === selectedId
                  ? 'ring-1 ring-[var(--color-accent)]/50'
                  : ''
                }
              `}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                  isHit
                    ? 'bg-[var(--color-danger)] pulse-dot'
                    : isDecoy
                      ? 'bg-[var(--color-muted)]'
                      : 'bg-[var(--color-accent)]'
                }`}
              />
              <div className="flex flex-col min-w-0">
                <span className="truncate text-xs">{asset.label}</span>
                <span className="text-[10px] text-[var(--color-muted)]">
                  {isDecoy ? 'honeypot' : 'production'}
                </span>
              </div>
              {isHit && linkedIncident && (
                <span className="ml-auto text-[10px] font-mono text-[var(--color-danger)] shrink-0">
                  {linkedIncident.technique}
                </span>
              )}
            </button>
          )
        })}

        {incidents.length > 0 && (
          <div className="mt-auto pt-2 border-t border-[var(--color-border)]">
            <h3 className="text-[10px] font-mono text-[var(--color-muted)] uppercase mb-1">
              Active Incidents
            </h3>
            <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
              {incidents.map((inc) => (
                <button
                  key={inc.incident_id}
                  onClick={() => onSelect(inc.incident_id)}
                  className={`
                    flex items-center gap-2 px-2 py-1 rounded text-left text-[11px] font-mono
                    border transition-all cursor-pointer
                    ${inc.incident_id === selectedId
                      ? 'border-[var(--color-accent)]/40 bg-[var(--color-accent)]/5'
                      : 'border-transparent hover:bg-[var(--color-surface-alt)]'
                    }
                  `}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${stateColor(inc.state)}`}
                  />
                  <span className="truncate text-[var(--color-muted)]">
                    {inc.decoy_id}
                  </span>
                  <span className="ml-auto text-[10px] text-[var(--color-muted)]">
                    {inc.state}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function stateColor(state) {
  const colors = {
    DETECTED: 'bg-[var(--color-warning)]',
    MATCHED: 'bg-[var(--color-accent)]',
    FUZZING: 'bg-[var(--color-accent)] pulse-dot',
    PATCH_GENERATED: 'bg-[var(--color-accent)]',
    VERIFYING: 'bg-[var(--color-accent)] pulse-dot',
    AWAITING_APPROVAL: 'bg-[var(--color-warning)] pulse-dot',
    APPROVED: 'bg-[var(--color-accent)]',
    DEPLOYED: 'bg-[var(--color-accent)]',
    REJECTED: 'bg-[var(--color-danger)]',
  }
  return colors[state] || 'bg-[var(--color-muted)]'
}
