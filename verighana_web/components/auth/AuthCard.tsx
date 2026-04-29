import Link from 'next/link'

interface AuthCardProps {
  title: string
  subtitle: string
  children: React.ReactNode
  footer: React.ReactNode
}

export function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div className="noise-overlay min-h-screen flex flex-col items-center justify-center px-4 py-12 bg-white">
      <div className="relative z-10 w-full max-w-md">
        {/* Logo */}
        <Link href="/" className="block text-center mb-8 font-display font-extrabold text-2xl text-[#0f2240] tracking-tight">
          Veri<span className="text-blue-600">Ghana</span>
        </Link>

        {/* Card */}
        <div className="bg-white border border-slate-200 shadow-sm rounded-2xl p-8">
          <h1 className="font-display font-extrabold text-xl text-[#0f2240] mb-1">{title}</h1>
          <p className="text-sm text-slate-500 mb-6">{subtitle}</p>
          {children}
        </div>

        {/* Footer link */}
        <div className="text-center mt-5 text-sm text-slate-500">
          {footer}
        </div>
      </div>
    </div>
  )
}
