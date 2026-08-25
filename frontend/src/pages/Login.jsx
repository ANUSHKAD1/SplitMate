import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import PageShell from '../components/PageShell'

export default function Login() {
  const [email, setEmail] = useState('')
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  function handleSubmit(event) { event.preventDefault(); signIn({ email }); navigate(location.state?.from?.pathname || '/dashboard', { replace: true }) }
  return <PageShell title="Welcome back"><p className="mb-6 text-sm text-slate-600">Authentication wiring will be added next. This placeholder unlocks protected routes.</p><form onSubmit={handleSubmit} className="space-y-4"><label className="block text-sm font-medium">Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" /></label><button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">Sign in</button></form><p className="mt-4 text-sm text-slate-600">New here? <Link className="text-slate-900 underline" to="/register">Create an account</Link>.</p></PageShell>
}
