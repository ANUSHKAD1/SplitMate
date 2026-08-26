import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/auth'
import PageShell from '../components/PageShell'
import { groupsApi } from '../groups/groupsApi'

export default function Groups() {
  const [groups, setGroups] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState('')
  const [createError, setCreateError] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const navigate = useNavigate()

  const loadGroups = useCallback(async () => {
    setIsLoading(true)
    setLoadError('')
    try {
      const response = await groupsApi.list()
      setGroups(response.data)
    } catch (error) {
      setLoadError(getApiErrorMessage(error, 'Unable to load your groups. Please try again.'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  async function createGroup(event) {
    event.preventDefault()
    const normalizedName = name.trim()
    if (!normalizedName) {
      setNameError('Group name is required.')
      return
    }

    setNameError('')
    setCreateError('')
    setIsCreating(true)
    try {
      const response = await groupsApi.create(normalizedName)
      navigate(`/groups/${response.data.id}`)
    } catch (error) {
      setCreateError(getApiErrorMessage(error, 'Unable to create this group. Please try again.'))
    } finally {
      setIsCreating(false)
    }
  }

  return <PageShell title="Your groups">
    <form onSubmit={createGroup} className="rounded-lg border border-slate-200 bg-slate-50 p-4" noValidate>
      <h2 className="text-base font-semibold">Create a group</h2>
      {createError && <p role="alert" className="mt-3 text-sm text-red-700">{createError}</p>}
      <div className="mt-3 flex flex-col gap-3 sm:flex-row">
        <label className="flex-1 text-sm font-medium">Group name
          <input value={name} onChange={(event) => setName(event.target.value)} aria-invalid={Boolean(nameError)} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2" />
          {nameError && <span className="mt-1 block text-sm text-red-700">{nameError}</span>}
        </label>
        <button disabled={isCreating} className="self-start rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60 sm:mt-6">{isCreating ? 'Creating…' : 'Create group'}</button>
      </div>
    </form>

    <section className="mt-6">
      <h2 className="mb-3 text-lg font-semibold">Groups</h2>
      {isLoading && <p className="text-sm text-slate-600">Loading your groups…</p>}
      {loadError && <div><p role="alert" className="text-sm text-red-700">{loadError}</p><button onClick={loadGroups} className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Try again</button></div>}
      {!isLoading && !loadError && (groups.length ? <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200">{groups.map((group) => <li key={group.id}><Link to={`/groups/${group.id}`} className="block px-4 py-3 font-medium text-slate-900 hover:bg-slate-50">{group.name}</Link></li>)}</ul> : <p className="text-sm text-slate-600">You are not in any groups yet.</p>)}
    </section>
  </PageShell>
}
