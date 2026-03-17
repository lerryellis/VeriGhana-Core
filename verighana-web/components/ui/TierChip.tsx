type Tier = 'free' | 'pro' | 'institutional'

const config: Record<Tier, { label: string; classes: string }> = {
  free:          { label: 'Free',          classes: 'bg-slate-500/20 text-slate-300 border-slate-500/30' },
  pro:           { label: 'Pro',           classes: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
  institutional: { label: 'Institutional', classes: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
}

export function TierChip({ tier }: { tier: Tier }) {
  const { label, classes } = config[tier] ?? config.free
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full border text-xs font-semibold tracking-wide ${classes}`}>
      {label}
    </span>
  )
}
