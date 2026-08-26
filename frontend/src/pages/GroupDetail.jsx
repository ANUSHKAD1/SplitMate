import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import GroupActivityFeed from '../activities/GroupActivityFeed'
import { getApiErrorMessage } from '../api/auth'
import { useAuth } from '../auth/AuthContext'
import PageShell from '../components/PageShell'
import { refreshDashboard } from '../dashboard/dashboardApi'
import Balances from '../expenses/Balances'
import ExpenseForm from '../expenses/ExpenseForm'
import ExpenseList from '../expenses/ExpenseList'
import { expensesApi } from '../expenses/expensesApi'
import MemberManagement from '../groups/MemberManagement'
import { groupsApi } from '../groups/groupsApi'
import SettlementPanel from '../settlements/SettlementPanel'
import useGroupLiveUpdates from '../realtime/useGroupLiveUpdates'
import { getTokenSubject } from '../utils/token'

export default function GroupDetail() {
  const { groupId } = useParams()
  const { accessToken } = useAuth()
  const [group, setGroup] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [isExpenseFormOpen, setIsExpenseFormOpen] = useState(false)
  const [editingExpense, setEditingExpense] = useState(null)
  const [expenseError, setExpenseError] = useState('')
  const [isSavingExpense, setIsSavingExpense] = useState(false)
  const [restDataRefreshKey, setRestDataRefreshKey] = useState(0)
  const currentUserId = useMemo(() => getTokenSubject(accessToken), [accessToken])

  const loadGroup = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const response = await groupsApi.get(groupId)
      setGroup(response.data)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to load this group. Please try again.'))
    } finally {
      setIsLoading(false)
    }
  }, [groupId])

  useEffect(() => {
    loadGroup()
  }, [loadGroup])

  const refreshGroupRestData = useCallback(() => {
    setRestDataRefreshKey((current) => current + 1)
  }, [])

  const refreshDashboardData = useCallback(() => {
    refreshDashboard().catch(() => {
      // Socket delivery must never turn a group page into a dashboard error state.
    })
  }, [])

  const liveConnectionStatus = useGroupLiveUpdates({
    groupId,
    accessToken,
    onGroupDataInvalidated: refreshGroupRestData,
    onOverallBalanceInvalidated: refreshDashboardData,
  })

  if (isLoading) return <PageShell title="Group"><p className="text-sm text-slate-600">Loading group…</p></PageShell>
  if (error) return <PageShell title="Group"><p role="alert" className="text-sm text-red-700">{error}</p><Link to="/groups" className="mt-4 inline-block text-sm text-slate-900 underline">Back to groups</Link><button onClick={loadGroup} className="ml-4 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Try again</button></PageShell>

  const owner = group.members.find((member) => member.id === group.owner_id)
  const isOwner = currentUserId === group.owner_id

  function openAddExpense() { setEditingExpense(null); setExpenseError(''); setIsExpenseFormOpen(true) }
  function openEditExpense(expense) { setEditingExpense(expense); setExpenseError(''); setIsExpenseFormOpen(true) }
  async function saveExpense(payload) {
    setExpenseError(''); setIsSavingExpense(true)
    try {
      if (editingExpense) await expensesApi.update(editingExpense.id, payload)
      else await expensesApi.create(group.id, payload)
      setIsExpenseFormOpen(false); setEditingExpense(null); refreshGroupRestData()
    } catch (requestError) {
      setExpenseError(getApiErrorMessage(requestError, 'Unable to save this expense. Please try again.'))
    } finally { setIsSavingExpense(false) }
  }
  function closeExpenseForm() {
    if (isSavingExpense) return
    setIsExpenseFormOpen(false); setEditingExpense(null); setExpenseError('')
  }

  return <PageShell title={group.name}>
    <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><Link to="/groups" className="text-sm text-slate-700 underline">Back to groups</Link><p aria-live="polite" className={liveConnectionStatus === 'live' ? 'text-xs font-medium text-emerald-700' : 'text-xs font-medium text-amber-700'}>{liveConnectionStatus === 'live' ? '● Live' : '● Reconnecting'}</p></div><button onClick={openAddExpense} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">Add expense</button></div>
    {isExpenseFormOpen && <ExpenseForm members={group.members} expense={editingExpense} onSubmit={saveExpense} onCancel={closeExpenseForm} isSubmitting={isSavingExpense} submitError={expenseError} />}
    <section className="mt-5">
      <h2 className="text-lg font-semibold">Members</h2>
      <p className="mt-1 text-sm text-slate-600">Owner: {owner ? `${owner.name} (${owner.email})` : `User #${group.owner_id}`}</p>
      {!isOwner && <p className="mt-4 text-sm text-slate-600">Only the group owner can manage members.</p>}
      {isOwner ? <MemberManagement group={group} onGroupChanged={loadGroup} /> : <ul className="mt-4 divide-y divide-slate-200">{group.members.map((member) => <li key={member.id} className="py-3"><p className="text-sm font-medium">{member.name}{member.id === group.owner_id && <span className="ml-2 text-xs text-slate-500">Owner</span>}</p><p className="text-sm text-slate-600">{member.email}</p></li>)}</ul>}
    </section>
    <ExpenseList groupId={group.id} group={group} currentUserId={currentUserId} onEdit={openEditExpense} onDataChanged={refreshGroupRestData} refreshKey={restDataRefreshKey} />
    <Balances groupId={group.id} refreshKey={restDataRefreshKey} />
    <SettlementPanel groupId={group.id} currentUserId={currentUserId} onSettlementRecorded={refreshGroupRestData} refreshKey={restDataRefreshKey} />
    <GroupActivityFeed groupId={group.id} refreshKey={restDataRefreshKey} />
  </PageShell>
}
