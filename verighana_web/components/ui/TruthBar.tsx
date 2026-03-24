interface TruthBarProps {
  score: number // 0–100
  showLabel?: boolean
}

function scoreColor(score: number) {
  if (score >= 75) return 'bg-green-500'
  if (score >= 45) return 'bg-amber-500'
  return 'bg-red-500'
}

export function TruthBar({ score, showLabel = true }: TruthBarProps) {
  const clamped = Math.max(0, Math.min(100, score))
  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex justify-between mb-1">
          <span className="text-xs text-slate-400 font-mono-vg">Truth Score</span>
          <span className="text-xs font-semibold text-white font-mono-vg">{clamped}/100</span>
        </div>
      )}
      <div className="h-2 w-full rounded-full bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${scoreColor(clamped)}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
