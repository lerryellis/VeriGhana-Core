import Link from 'next/link'
import { Nav } from './Nav'
import { Footer } from './Footer'

interface Section {
  heading: string
  body: React.ReactNode
}

interface LegalLayoutProps {
  title: string
  subtitle: string
  lastUpdated: string
  sections: Section[]
}

export function LegalLayout({ title, subtitle, lastUpdated, sections }: LegalLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#f0f4f8' }}>
      <Nav />

      {/* Hero strip */}
      <div style={{ background: 'linear-gradient(135deg,#0f2240 0%,#1a3a6e 100%)' }} className="px-[5%] py-14">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs font-mono-vg text-blue-400 uppercase tracking-widest mb-3">Legal</p>
          <h1 className="font-display font-extrabold text-3xl md:text-4xl text-white mb-3">{title}</h1>
          <p className="text-slate-400 text-sm">{subtitle}</p>
          <p className="text-slate-600 text-xs mt-2">Last updated: {lastUpdated}</p>
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 px-[5%] py-12">
        <div className="max-w-3xl mx-auto">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 divide-y divide-slate-100">
            {sections.map((s, i) => (
              <div key={i} className="px-8 py-7">
                <h2 className="font-display font-bold text-lg text-[#0f2240] mb-3">{s.heading}</h2>
                <div className="text-sm text-slate-600 leading-relaxed space-y-3">{s.body}</div>
              </div>
            ))}
          </div>

          <div className="mt-8 text-center">
            <Link href="/" className="text-sm text-blue-600 hover:text-blue-500 transition-colors">
              ← Back to VeriGhana
            </Link>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}
