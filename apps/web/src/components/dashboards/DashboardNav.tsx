import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/', label: 'Chat' },
  { to: '/dashboard/routing', label: 'Routing' },
  { to: '/dashboard/eval', label: 'Evaluation' },
]

export function DashboardNav({ title }: { title: string }) {
  const { pathname } = useLocation()
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-surface-700">
      <h1 className="text-lg font-bold text-white">{title}</h1>
      <nav className="flex gap-1" aria-label="Dashboard navigation">
        {LINKS.map((l) => (
          <Link
            key={l.to}
            to={l.to}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              pathname === l.to
                ? 'bg-brand-600 text-white'
                : 'text-slate-300 hover:bg-surface-700 hover:text-white'
            }`}
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  )
}
