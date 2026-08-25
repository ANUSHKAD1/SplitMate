import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/auth'
import { useAuth } from '../auth/AuthContext'
import PageShell from '../components/PageShell'
import { validateLogin } from '../utils/authValidation'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  async function handleSubmit(event) {
    event.preventDefault()
    const nextErrors = validateLogin({ email, password })
    setErrors(nextErrors)
    setApiError('')
    if (Object.keys(nextErrors).length) return

    setIsSubmitting(true)
    try {
      await login({ email: email.trim(), password })
      setPassword('')
      navigate(location.state?.from?.pathname || '/dashboard', { replace: true })
    } catch (error) {
      setApiError(getApiErrorMessage(error, 'Unable to sign in. Please try again.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return <PageShell title="Welcome back">
    {location.state?.message && <p role="status" className="mb-4 text-sm text-emerald-700">{location.state.message}</p>}
    {apiError && <p role="alert" className="mb-4 text-sm text-red-700">{apiError}</p>}
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <label className="block text-sm font-medium">Email
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(errors.email)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        {errors.email && <span className="mt-1 block text-sm text-red-700">{errors.email}</span>}
      </label>
      <label className="block text-sm font-medium">Password
        <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} aria-invalid={Boolean(errors.password)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        {errors.password && <span className="mt-1 block text-sm text-red-700">{errors.password}</span>}
      </label>
      <button disabled={isSubmitting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60">{isSubmitting ? 'Signing in…' : 'Sign in'}</button>
    </form>
    <p className="mt-4 text-sm text-slate-600">New here? <Link className="text-slate-900 underline" to="/register">Create an account</Link>.</p>
  </PageShell>
}
