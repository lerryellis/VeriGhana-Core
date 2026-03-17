interface StatPillProps {
  label: string
  value: string | number
  sub?: string
}

export function StatPill({ label, value, sub }: StatPillProps) {
  return (
    <div className="glass-card px-5 py-4 text-center">
      <div className="font-display text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-slate-400 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </div>
  )
}
