import { useCallback, useEffect, useMemo, useState } from 'react'
import { getApiErrorMessage } from '../api/auth'
import { formatIndianRupees } from '../utils/currency'
import { expensesApi } from './expensesApi'

const pageSize = 10

export default function ExpenseList({ groupId, group, currentUserId, onEdit, onDataChanged }) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [sortOrder, setSortOrder] = useState('desc')
  const [page, setPage] = useState(1)
  const [deletingId, setDeletingId] = useState(null)
  const [deleteError, setDeleteError] = useState('')
  const memberNames = useMemo(() => new Map(group.members.map((member) => [member.id, member.name])), [group.members])

  const loadExpenses = useCallback(async () => {
    setIsLoading(true); setError('')
    try {
      const response = await expensesApi.list(groupId, { page, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder })
      setData(response.data)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to load expenses. Please try again.'))
    } finally { setIsLoading(false) }
  }, [groupId, page, sortBy, sortOrder])
  useEffect(() => { loadExpenses() }, [loadExpenses])

  function changeSort(field) {
    if (field === sortBy) setSortOrder((current) => current === 'asc' ? 'desc' : 'asc')
    else { setSortBy(field); setSortOrder('desc') }
    setPage(1)
  }
  async function deleteExpense(expense) {
    if (!window.confirm(`Delete “${expense.description}”? This cannot be undone.`)) return
    setDeleteError(''); setDeletingId(expense.id)
    try {
      await expensesApi.remove(expense.id)
      if (data.items.length === 1 && page > 1) setPage((current) => current - 1)
      else await loadExpenses()
      onDataChanged()
    } catch (requestError) {
      setDeleteError(getApiErrorMessage(requestError, 'Unable to delete this expense. Please try again.'))
    } finally { setDeletingId(null) }
  }
  const sortIndicator = (field) => sortBy === field ? (sortOrder === 'asc' ? ' ↑' : ' ↓') : ''

  return <section className="mt-8 border-t border-slate-200 pt-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Expenses</h2><div className="flex gap-2"><button onClick={() => changeSort('date')} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Date{sortIndicator('date')}</button><button onClick={() => changeSort('amount')} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Amount{sortIndicator('amount')}</button></div></div>
    {deleteError && <p role="alert" className="mt-3 text-sm text-red-700">{deleteError}</p>}
    {isLoading && <p className="mt-4 text-sm text-slate-600">Loading expenses…</p>}
    {!isLoading && error && <div className="mt-4"><p role="alert" className="text-sm text-red-700">{error}</p><button onClick={loadExpenses} className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Retry</button></div>}
    {!isLoading && !error && data?.items.length === 0 && <p className="mt-4 text-sm text-slate-600">No expenses yet. Add the first one for this group.</p>}
    {!isLoading && !error && data?.items.length > 0 && <>
      <ul className="mt-4 divide-y divide-slate-200 rounded-lg border border-slate-200">{data.items.map((expense) => {
        const canMutate = currentUserId === group.owner_id || currentUserId === expense.created_by
        return <li key={expense.id} className="flex flex-wrap items-center justify-between gap-4 p-4"><div><p className="font-medium text-slate-900">{expense.description}</p><p className="mt-1 text-sm text-slate-600">Paid by {memberNames.get(expense.paid_by) || `Member #${expense.paid_by}`} · {new Date(`${expense.expense_date}T00:00:00`).toLocaleDateString('en-IN')} · {expense.split_type === 'equal' ? 'Equal split' : 'Custom split'}</p></div><div className="flex items-center gap-3"><p className="font-medium">{formatIndianRupees(expense.amount)}</p>{canMutate && <><button onClick={() => onEdit(expense)} className="text-sm text-slate-700 underline">Edit</button><button onClick={() => deleteExpense(expense)} disabled={deletingId === expense.id} className="text-sm text-rose-700 underline disabled:cursor-not-allowed disabled:opacity-60">{deletingId === expense.id ? 'Deleting…' : 'Delete'}</button></>}</div></li>
      })}</ul>
      <div className="mt-4 flex items-center justify-between text-sm"><span>Page {data.page} of {data.total_pages} · {data.total} total</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage((current) => current - 1)} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Previous</button><button disabled={page >= data.total_pages} onClick={() => setPage((current) => current + 1)} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Next</button></div></div>
    </>}
  </section>
}
