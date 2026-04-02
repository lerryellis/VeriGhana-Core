import Link from 'next/link'

export function Footer() {
  return (
    <footer className="bg-[#0f2240] border-t border-white/[0.08] px-[5%] py-10">
      <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="font-display font-extrabold text-xl text-white">
          Veri<span className="text-blue-400">Ghana</span>
        </div>

        <ul className="flex flex-wrap justify-center gap-6 list-none">
          <li><Link href="/privacy" className="text-sm text-slate-400 hover:text-white transition-colors">Privacy Policy</Link></li>
          <li><Link href="/terms"   className="text-sm text-slate-400 hover:text-white transition-colors">Terms of Service</Link></li>
          <li><Link href="/cookies" className="text-sm text-slate-400 hover:text-white transition-colors">Cookie Policy</Link></li>
          <li>
            <a href={`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/docs`} target="_blank" rel="noopener noreferrer" className="text-sm text-slate-400 hover:text-white transition-colors">
              API Docs
            </a>
          </li>
          <li><Link href="/app/verify" className="text-sm text-slate-400 hover:text-white transition-colors">Dashboard</Link></li>
        </ul>

        <p className="text-xs text-slate-600 text-center">
          VeriGhana © 2026 — GIMPA Computer Science Research<br />
          Combating information disorder in Ghana with AI.
        </p>
      </div>
    </footer>
  )
}
