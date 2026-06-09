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
    <nav className="bg-brand-900 text-white px-6 py-3 flex items-center gap-8 shadow-lg">
      <div className="flex items-center gap-2 font-bold text-lg tracking-tight">
        <Brain size={22} className="text-blue-300" />
        EnterpriseCertIQ
      </div>
      <div className="flex gap-4 ml-4">
        {links.map((l) => (
          <Link
            key={l.to}
            to={l.to}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition',
              loc.pathname === l.to
                ? 'bg-blue-700 text-white'
                : 'text-blue-200 hover:bg-blue-800'
            )}
          >
            {l.icon}
            {l.label}
          </Link>
        ))}
      </div>
      <div className="ml-auto text-xs text-blue-300 italic">
        Synthetic data only · Microsoft Agents League 2026
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
