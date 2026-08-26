import { useCallback, useEffect, useState } from 'react'
import { getApiErrorMessage } from '../api/auth'
import { activitiesApi } from './activitiesApi'

const pageSize = 10

function formatActivityTime(value) {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function GroupActivityFeed({ groupId, refreshKey }) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)

  const loadActivity = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const response = await activitiesApi.list(groupId, { page, page_size: pageSize })
      setData(response.data)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to load activity. Please try again.'))
    } finally {
      setIsLoading(false)
    }
  }, [groupId, page])

  useEffect(() => {
    loadActivity()
  }, [loadActivity, refreshKey])

  return <section className="mt-8 border-t border-slate-200 pt-6">
    <h2 className="text-lg font-semibold">Activity</h2>
    <p className="mt-1 text-sm text-slate-600">Latest group updates, newest first.</p>
    {isLoading && <p className="mt-4 text-sm text-slate-600">Loading activity…</p>}
    {!isLoading && error && <div className="mt-4"><p role="alert" className="text-sm text-red-700">{error}</p><button onClick={loadActivity} className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Retry</button></div>}
    {!isLoading && !error && data?.items.length === 0 && <p className="mt-4 text-sm text-slate-600">No activity yet.</p>}
    {!isLoading && !error && data?.items.length > 0 && <>
      <ul className="mt-4 divide-y divide-slate-200 rounded-lg border border-slate-200">{data.items.map((item) => <li key={item.id} className="px-4 py-3"><p className="text-sm font-medium text-slate-900">{item.message}</p><p className="mt-1 text-xs text-slate-500">{formatActivityTime(item.created_at)}</p></li>)}</ul>
      <div className="mt-4 flex items-center justify-between text-sm"><span>Page {data.page} of {data.total_pages} · {data.total} total</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage((current) => current - 1)} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Previous</button><button disabled={page >= data.total_pages} onClick={() => setPage((current) => current + 1)} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Next</button></div></div>
    </>}
  </section>
}
