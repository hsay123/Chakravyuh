const PIPELINE_STATES = [
  'DETECTED',
  'MATCHED',
  'FUZZING',
  'PATCH_GENERATED',
  'VERIFYING',
  'AWAITING_APPROVAL',
  'APPROVED',
  'DEPLOYED',
]

const STATE_INDEX = Object.fromEntries(PIPELINE_STATES.map((s, i) => [s, i]))

const LABELS = {
  DETECTED: 'DETECTED',
  MATCHED: 'MATCHED',
  FUZZING: 'FUZZING',
  PATCH_GENERATED: 'PATCH GEN',
  VERIFYING: 'VERIFYING',
  AWAITING_APPROVAL: 'AWAITING APPROVAL',
  APPROVED: 'APPROVED',
  DEPLOYED: 'DEPLOYED',
  REJECTED: 'REJECTED',
}

export default function PipelineStatus({ incident }) {
  if (!incident) {
    return (
      <div className="flex flex-col gap-2 h-full">
        <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
          Pipeline Status
        </h2>
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--color-muted)] font-mono">
          Select an incident to view pipeline
        </div>
      </div>
    )
  }

  const currentIdx = STATE_INDEX[incident.state] ?? -1
  const isTerminal = incident.state === 'DEPLOYED'
  const isRejected = incident.state === 'REJECTED'
  const isWaiting = incident.state === 'AWAITING_APPROVAL'

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
          Pipeline Status
        </h2>
        <div className="flex items-center gap-2 text-[11px] font-mono text-[var(--color-muted)]">
          <span>{incident.decoy_id}</span>
          <span className="text-[var(--color-border)]">→</span>
          <span>{incident.real_asset_id || '...'}</span>
        </div>
      </div>

      <div className="flex-1 flex flex-col justify-center">
        <div className="flex items-center gap-1 flex-wrap">
          {PIPELINE_STATES.map((state, idx) => {
            const done = idx <= currentIdx && !isRejected
            const isCurrent = idx === currentIdx && !isTerminal && !isRejected

            return (
              <div key={state} className="flex items-center">
                <div
                  className={`
                    flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-mono
                    border transition-all
                    ${isCurrent
                      ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] glow-green'
                      : done
                        ? 'border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5 text-[var(--color-accent)]'
                        : 'border-[var(--color-border)] bg-transparent text-[var(--color-muted)]'
                    }
                  `}
                >
                  {done && !isCurrent && (
                    <span className="text-[var(--color-accent)]">&#10003;</span>
                  )}
                  {isCurrent && (
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)] pulse-dot" />
                  )}
                  <span>{LABELS[state]}</span>
                </div>
                {idx < PIPELINE_STATES.length - 1 && (
                  <span className="text-[var(--color-border)] mx-0.5 text-[10px]">&rarr;</span>
                )}
              </div>
            )
          })}
        </div>

        {isRejected && (
          <div className="mt-3 px-3 py-2 rounded border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5">
            <span className="text-[var(--color-danger)] font-mono text-xs font-bold">
              REJECTED
            </span>
            {incident.approver && (
              <span className="text-[var(--color-muted)] text-[11px] ml-2">
                by {incident.approver}
              </span>
            )}
          </div>
        )}

        {isWaiting && (
          <div className="mt-3 px-3 py-2 rounded border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/5">
            <span className="text-[var(--color-warning)] font-mono text-xs font-bold">
              AWAITING OPERATOR APPROVAL
            </span>
          </div>
        )}

        {isTerminal && !isRejected && (
          <div className="mt-3 px-3 py-2 rounded border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5">
            <span className="text-[var(--color-accent)] font-mono text-xs font-bold">
              {incident.state === 'DEPLOYED' ? 'DEPLOYED' : 'APPROVED'}
            </span>
            {incident.approver && (
              <span className="text-[var(--color-muted)] text-[11px] ml-2">
                by {incident.approver}
              </span>
            )}
          </div>
        )}

        <div className="mt-3 text-[10px] font-mono text-[var(--color-muted)]">
          <span className="text-white">{incident.technique}</span>
          <span className="mx-2">|</span>
          <span>ID: {incident.incident_id.slice(0, 8)}...</span>
        </div>
      </div>
    </div>
  )
}
