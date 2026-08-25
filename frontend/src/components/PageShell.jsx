import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function PageShell({ title, children }) {
  const { isAuthenticated, logout } = useAuth()
  return <main className="mx-auto min-h-screen max-w-3xl px-6 py-12"><header className="mb-10 flex items-center justify-between"><Link to={isAuthenticated ? '/dashboard' : '/login'} className="text-xl font-semibold text-slate-900">SplitMate</Link>{isAuthenticated && <button onClick={() => logout()} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Sign out</button>}</header><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h1 className="mb-4 text-2xl font-semibold">{title}</h1>{children}</section></main>
}
