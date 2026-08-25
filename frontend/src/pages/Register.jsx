import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/auth'
import { useAuth } from '../auth/AuthContext'
import PageShell from '../components/PageShell'
import { validateRegistration } from '../utils/authValidation'

export default function Register() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(event) {
    event.preventDefault()
    const nextErrors = validateRegistration({ name, email, password })
    setErrors(nextErrors)
    setApiError('')
    if (Object.keys(nextErrors).length) return

    setIsSubmitting(true)
    try {
      await register({ name: name.trim(), email: email.trim(), password })
      setPassword('')
      navigate('/login', { replace: true, state: { message: 'Account created. Please sign in.' } })
    } catch (error) {
      setApiError(getApiErrorMessage(error, 'Unable to create your account. Please try again.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return <PageShell title="Create an account">
    {apiError && <p role="alert" className="mb-4 text-sm text-red-700">{apiError}</p>}
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <label className="block text-sm font-medium">Name
        <input value={name} onChange={(event) => setName(event.target.value)} aria-invalid={Boolean(errors.name)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        {errors.name && <span className="mt-1 block text-sm text-red-700">{errors.name}</span>}
      </label>
      <label className="block text-sm font-medium">Email
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(errors.email)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        {errors.email && <span className="mt-1 block text-sm text-red-700">{errors.email}</span>}
      </label>
      <label className="block text-sm font-medium">Password
        <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} aria-invalid={Boolean(errors.password)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        {errors.password && <span className="mt-1 block text-sm text-red-700">{errors.password}</span>}
      </label>
      <button disabled={isSubmitting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60">{isSubmitting ? 'Creating account…' : 'Create account'}</button>
    </form>
    <p className="mt-4 text-sm text-slate-600">Already have an account? <Link className="text-slate-900 underline" to="/login">Sign in</Link>.</p>
  </PageShell>
}
