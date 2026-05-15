import Link from 'next/link'

export function Nav() {
  return (
    <nav className="sticky top-0 z-50 flex items-center h-16 px-[5%] bg-[rgba(15,34,64,0.97)] backdrop-blur-xl border-b border-white/[0.08] animate-fade-down">
      <Link href="/" className="font-display font-extrabold text-[1.35rem] text-white tracking-tight mr-auto no-underline">
        Veri<span className="text-blue-400">Ghana</span>
      </Link>

      <ul className="hidden md:flex gap-8 list-none mr-10">
        <li><a href="#how" className="text-sm text-blue-300 hover:text-white transition-colors">How It Works</a></li>
        <li><a href="#pricing" className="text-sm text-blue-300 hover:text-white transition-colors">Pricing</a></li>
        <li>
          <Link href="/research" className="text-sm text-blue-300 hover:text-white transition-colors">
            Research
          </Link>
        </li>
        <li>
          <Link href="/app/verify" className="text-sm text-blue-300 hover:text-white transition-colors">
            Dashboard
          </Link>
        </li>
      </ul>

      <Link
        href="/app/verify"
        className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-5 py-2 rounded-md transition-all hover:-translate-y-px"
      >
        Open App →
      </Link>
    </nav>
  )
}
