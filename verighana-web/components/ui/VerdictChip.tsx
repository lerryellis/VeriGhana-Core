type Verdict = 'VERIFIED' | 'PARTIAL' | 'FALSE' | 'UNCORROBORATED'

const config: Record<Verdict, { label: string; classes: string }> = {
  VERIFIED:       { label: '✓ Verified',       classes: 'bg-green-500/15 text-green-400 border-green-500/30' },
  PARTIAL:        { label: '⚡ Partial',         classes: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
  FALSE:          { label: '✗ False',            classes: 'bg-red-500/15 text-red-400 border-red-500/30' },
  UNCORROBORATED: { label: '? Uncorroborated',   classes: 'bg-slate-500/15 text-slate-400 border-slate-500/30' },
}

export function VerdictChip({ verdict }: { verdict: Verdict }) {
  const { label, classes } = config[verdict] ?? config.UNCORROBORATED
  return (
    <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full border text-xs font-semibold font-mono tracking-wide ${classes}`}>
      {label}
    </span>
  )
}
