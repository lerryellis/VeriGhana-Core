import Link from 'next/link'

interface AuthCardProps {
  title: string
  subtitle: string
  children: React.ReactNode
  footer: React.ReactNode
}

export function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-12"
      style={{ background: 'linear-gradient(160deg,#0f2240 0%,#0c1e3f 55%,#112244 100%)' }}
    >
      {/* Grid overlay */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(rgba(37,99,235,0.06) 1px,transparent 1px),linear-gradient(90deg,rgba(37,99,235,0.06) 1px,transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(ellipse at 50% 0%,black 40%,transparent 75%)',
        }}
      />

      <div className="relative z-10 w-full max-w-md">
        {/* Logo */}
        <Link href="/" className="block text-center mb-8 font-display font-extrabold text-2xl text-white tracking-tight">
          Veri<span className="text-blue-400">Ghana</span>
        </Link>

        {/* Card */}
        <div className="glass-card p-8">
          <h1 className="font-display font-extrabold text-xl text-white mb-1">{title}</h1>
          <p className="text-sm text-slate-400 mb-6">{subtitle}</p>
          {children}
        </div>

        {/* Footer link */}
        <div className="text-center mt-5 text-sm text-slate-400">
          {footer}
        </div>
      </div>
    </div>
  )
}
