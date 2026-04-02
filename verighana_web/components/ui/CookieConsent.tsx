'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

type Consent = 'all' | 'essential' | null

export function CookieConsent() {
  const [consent, setConsent] = useState<Consent>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem('vg_cookie_consent')
    if (!stored) {
      setVisible(true)
    } else {
      setConsent(stored as Consent)
    }
  }, [])

  function accept(level: 'all' | 'essential') {
    localStorage.setItem('vg_cookie_consent', level)
    setConsent(level)
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="fixed bottom-0 inset-x-0 z-[60] p-4 pointer-events-none">
      <div className="max-w-2xl mx-auto bg-[#0f2240] border border-white/[0.1] rounded-2xl shadow-2xl p-6 pointer-events-auto">
        <div className="flex items-start gap-4">
          <span className="text-2xl shrink-0 mt-0.5">🍪</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white mb-1">We value your privacy</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              VeriGhana uses cookies to keep you signed in and remember your preferences.
              We do not use cookies for advertising or cross-site tracking.
              Read our{' '}
              <Link href="/cookies" className="text-blue-400 hover:underline">Cookie Policy</Link>
              {' '}for details.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 mt-4 ml-10">
          <button
            type="button"
            onClick={() => accept('all')}
            className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
          >
            Accept All
          </button>
          <button
            type="button"
            onClick={() => accept('essential')}
            className="bg-white/[0.08] hover:bg-white/[0.12] text-slate-300 text-sm font-medium px-5 py-2.5 rounded-lg border border-white/[0.1] transition-colors"
          >
            Essential Only
          </button>
        </div>
      </div>
    </div>
  )
}
