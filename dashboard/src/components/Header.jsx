export default function Header({ connected, onOpenAudit }) {
  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[var(--color-accent)]" />
          <span className="text-lg font-bold tracking-wide text-white">
            TrapNet-CRS
          </span>
        </div>
        <span className="text-xs text-[var(--color-muted)] font-mono">
          Autonomous Cyber Response
        </span>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? 'bg-[var(--color-accent)] pulse-dot' : 'bg-[var(--color-danger)]'
            }`}
          />
          <span className="text-xs font-mono text-[var(--color-muted)]">
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
        <button
          onClick={onOpenAudit}
          className="px-3 py-1.5 text-xs font-mono border border-[var(--color-border)] rounded
                     hover:bg-[var(--color-surface-alt)] transition-colors text-[var(--color-muted)]
                     hover:text-white cursor-pointer"
        >
          Audit Log
        </button>
      </div>
    </header>
  )
}
