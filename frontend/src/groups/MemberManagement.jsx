import { useState } from 'react'
import { getApiErrorMessage } from '../api/auth'
import { groupsApi } from './groupsApi'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function MemberManagement({ group, onGroupChanged }) {
  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState('')
  const [apiError, setApiError] = useState('')
  const [isAdding, setIsAdding] = useState(false)
  const [removingUserId, setRemovingUserId] = useState(null)

  async function addMember(event) {
    event.preventDefault()
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail) {
      setEmailError('Email is required.')
      return
    }
    if (!emailPattern.test(normalizedEmail)) {
      setEmailError('Enter a valid email address.')
      return
    }

    setEmailError('')
    setApiError('')
    setIsAdding(true)
    try {
      await groupsApi.addMember(group.id, normalizedEmail)
      setEmail('')
      await onGroupChanged()
    } catch (error) {
      setApiError(getApiErrorMessage(error, 'Unable to add this member. Please try again.'))
    } finally {
      setIsAdding(false)
    }
  }

  async function removeMember(member) {
    if (!window.confirm(`Remove ${member.name} from ${group.name}?`)) return

    setApiError('')
    setRemovingUserId(member.id)
    try {
      await groupsApi.removeMember(group.id, member.id)
      await onGroupChanged()
    } catch (error) {
      setApiError(getApiErrorMessage(error, 'Unable to remove this member. Please try again.'))
    } finally {
      setRemovingUserId(null)
    }
  }

  return <section className="mt-6 border-t border-slate-200 pt-6">
    <h2 className="text-lg font-semibold">Manage members</h2>
    {apiError && <p role="alert" className="mt-3 text-sm text-red-700">{apiError}</p>}
    <form onSubmit={addMember} className="mt-4 flex flex-col gap-3 sm:flex-row" noValidate>
      <label className="flex-1 text-sm font-medium">Registered user email
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(emailError)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        {emailError && <span className="mt-1 block text-sm text-red-700">{emailError}</span>}
      </label>
      <button disabled={isAdding} className="self-start rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60 sm:mt-6">{isAdding ? 'Adding…' : 'Add member'}</button>
    </form>

    <ul className="mt-5 divide-y divide-slate-200">
      {group.members.map((member) => <li key={member.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
        <div><p className="text-sm font-medium text-slate-900">{member.name}{member.id === group.owner_id && <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">Owner</span>}</p><p className="text-sm text-slate-600">{member.email}</p></div>
        {member.id !== group.owner_id && <button onClick={() => removeMember(member)} disabled={removingUserId === member.id} className="rounded-md border border-rose-200 px-3 py-1.5 text-sm text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60">{removingUserId === member.id ? 'Removing…' : 'Remove'}</button>}
      </li>)}
    </ul>
  </section>
}
