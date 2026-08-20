export default function DiffViewer({ diff }) {
  if (!diff) {
    return (
      <div className="flex flex-col gap-2 h-full">
        <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
          Diff View
        </h2>
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--color-muted)] font-mono">
          No patch diff available yet
        </div>
      </div>
    )
  }

  const lines = diff.split('\n')

  return (
    <div className="flex flex-col gap-2 h-full">
      <h2 className="text-xs font-mono font-bold tracking-widest text-[var(--color-muted)] uppercase">
        Diff View
      </h2>
      <div className="flex-1 overflow-auto rounded border border-[var(--color-border)] bg-[var(--color-surface)]">
        <pre className="p-3 text-[11px] leading-relaxed font-mono">
          {lines.map((line, i) => {
            if (line.startsWith('+') && !line.startsWith('+++')) {
              return (
                <div key={i} className="bg-[var(--color-accent)]/5 text-[var(--color-accent)]">
                  <span className="inline-block w-8 text-right pr-2 text-[var(--color-muted)] select-none">
                    {i + 1}
                  </span>
                  <span>{line}</span>
                </div>
              )
            }
            if (line.startsWith('-') && !line.startsWith('---')) {
              return (
                <div key={i} className="bg-[var(--color-danger)]/5 text-[var(--color-danger)]">
                  <span className="inline-block w-8 text-right pr-2 text-[var(--color-muted)] select-none">
                    {i + 1}
                  </span>
                  <span>{line}</span>
                </div>
              )
            }
            if (line.startsWith('@@')) {
              return (
                <div key={i} className="text-[var(--color-warning)]">
                  <span className="inline-block w-8 text-right pr-2 text-[var(--color-muted)] select-none">
                    {i + 1}
                  </span>
                  <span>{line}</span>
                </div>
              )
            }
            return (
              <div key={i} className="text-[var(--color-muted)]">
                <span className="inline-block w-8 text-right pr-2 select-none opacity-50">
                  {i + 1}
                </span>
                <span>{line}</span>
              </div>
            )
          })}
        </pre>
      </div>
    </div>
  )
}
