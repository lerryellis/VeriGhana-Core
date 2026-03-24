const sources = [
  { name: 'Ministry of Finance',  type: 'gov' },
  { name: 'Citi Newsroom',        type: 'media' },
  { name: 'Joy Online',           type: 'media' },
  { name: 'Graphic Online',       type: 'media' },
  { name: 'Ghana News Agency',    type: 'gov' },
  { name: 'Bank of Ghana',        type: 'gov' },
  { name: 'Dubawa Ghana',         type: 'fact' },
  { name: '3News',                type: 'media' },
  { name: 'Ghana Health Service', type: 'gov' },
]

const dotColor: Record<string, string> = {
  gov:   'bg-blue-400',
  fact:  'bg-green-400',
  media: 'bg-slate-400',
}

export function SourcesStrip() {
  return (
    <div className="bg-[#0a1a35] border-b border-white/[0.06] px-[5%] py-3 flex flex-wrap items-center gap-2">
      <span className="text-[0.68rem] text-slate-500 font-mono-vg uppercase tracking-widest mr-2">Trusted Sources</span>
      {sources.map(s => (
        <span key={s.name} className="inline-flex items-center gap-1.5 bg-white/[0.05] border border-white/[0.08] text-slate-300 text-xs px-3 py-1 rounded-full">
          <span className={`w-1.5 h-1.5 rounded-full ${dotColor[s.type]}`} />
          {s.name}
        </span>
      ))}
    </div>
  )
}
