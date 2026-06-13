import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import { Brain, LayoutDashboard, Users } from 'lucide-react'
import LearnerView from './pages/LearnerView'
import ManagerView from './pages/ManagerView'
import ErrorBoundary from './components/ErrorBoundary'
import clsx from 'clsx'

function Nav() {
  const loc = useLocation()
  const links = [
    { to: '/', label: 'Learner', icon: <LayoutDashboard size={16} /> },
    { to: '/manager', label: 'Manager', icon: <Users size={16} /> },
  ]
  return (
    <nav className="sticky top-0 z-30 flex items-center gap-8 border-b border-line bg-[var(--canvas-2)]/80 px-6 py-3 backdrop-blur-xl">
      <div className="flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-accent to-brand-600 shadow-glow">
          <Brain size={20} className="text-white" />
        </span>
        <div className="leading-tight">
          <div className="text-[15px] font-bold tracking-tight text-ink">EnterpriseCertIQ</div>
          <div className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-subtle">Certification Intelligence</div>
        </div>
      </div>
      <div className="ml-2 flex gap-1.5">
        {links.map((l) => (
          <Link
            key={l.to}
            to={l.to}
            className={clsx(
              'flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition',
              loc.pathname === l.to
                ? 'subtab-active'
                : 'text-ink-muted hover:bg-white/[0.03] hover:text-ink',
            )}
          >
            {l.icon}
            {l.label}
          </Link>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-2 text-[11px] font-medium text-ink-subtle">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          Synthetic data only
        </span>
        <span className="hidden sm:inline">Microsoft Agents League 2026</span>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <Nav />
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<ErrorBoundary><LearnerView /></ErrorBoundary>} />
            <Route path="/manager" element={<ErrorBoundary><ManagerView /></ErrorBoundary>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
