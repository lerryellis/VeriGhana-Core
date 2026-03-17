'use client'

import { useEffect, useRef } from 'react'

const flagged = [
  { claim: '"EC postpones elections"',       score: '5%' },
  { claim: '"Free SHS officially ended"',     score: '8%' },
  { claim: '"President arrested"',           score: '2%' },
  { claim: '"Ghana joins European Union"',   score: '1%' },
  { claim: '"Cedi collapses to 30/dollar"', score: '12%' },
  { claim: '"COVID-19 lockdown returns"',    score: '6%' },
  { claim: '"New 40% mobile money tax"',     score: '9%' },
  { claim: '"BECE cancelled nationwide"',    score: '3%' },
  { claim: '"Petrol prices drop 50%"',       score: '7%' },
  { claim: '"Government bans WhatsApp"',     score: '1%' },
]

export function Ticker() {
  const innerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // CSS animation handles the scroll — just ensure double items for seamless loop
  }, [])

  const items = [...flagged, ...flagged]

  return (
    <div className="bg-[#0a1629] border-y border-white/[0.06] py-3 overflow-hidden flex items-center gap-4">
      <span className="shrink-0 pl-5 text-[0.68rem] font-mono-vg text-red-400 uppercase tracking-widest">Live Flagged</span>
      <div className="overflow-hidden flex-1">
        <div
          ref={innerRef}
          className="flex gap-8 whitespace-nowrap"
          style={{ animation: 'ticker 35s linear infinite' }}
        >
          {items.map((f, i) => (
            <span key={i} className="text-xs text-slate-400 shrink-0">
              <span className="text-slate-300">{f.claim}</span>
              {' — Score: '}
              <span className="text-red-400 font-semibold">{f.score}</span>
              <span className="mx-4 text-slate-700">|</span>
            </span>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes ticker {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  )
}
