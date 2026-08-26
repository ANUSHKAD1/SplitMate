import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getApiErrorMessage } from '../api/auth'
import PageShell from '../components/PageShell'
import DashboardStat from '../dashboard/DashboardStat'
import { getDashboard } from '../dashboard/dashboardApi'
import RecentActivityList from '../dashboard/RecentActivityList'
import { formatIndianRupees } from '../utils/currency'

function netBalanceTone(amount) {
  if (amount > 0) return 'positive'
  if (amount < 0) return 'negative'
  return 'default'
}

export default function Dashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    setError('')

    try {
      const response = await getDashboard()
      setDashboard(response.data)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to load your dashboard. Please try again.'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  if (isLoading) {
    return <PageShell title="Dashboard"><p className="text-sm text-slate-600">Loading your dashboard…</p></PageShell>
  }

  if (error) {
    return <PageShell title="Dashboard">
      <p role="alert" className="text-sm text-red-700">{error}</p>
      <button onClick={loadDashboard} className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">Try again</button>
    </PageShell>
  }

  const largestDebt = dashboard.group_where_user_owes_most

  return <PageShell title="Dashboard">
    <Link to="/groups" className="mb-5 inline-block text-sm font-medium text-slate-900 underline">View your groups</Link>
    <div className="grid gap-4 sm:grid-cols-2">
      <DashboardStat label="You owe" value={formatIndianRupees(dashboard.total_user_owes)} tone="negative" />
      <DashboardStat label="Owed to you" value={formatIndianRupees(dashboard.total_owed_to_user)} tone="positive" />
      <DashboardStat label="Net balance" value={formatIndianRupees(dashboard.net_balance)} tone={netBalanceTone(dashboard.net_balance)} />
      <DashboardStat label="Your groups" value={dashboard.group_count} />
    </div>

    <section className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h2 className="text-base font-semibold">Where you owe the most</h2>
      {largestDebt ? <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-medium text-slate-900">{largestDebt.group_name}</p>
        <p className="font-semibold text-rose-700">{formatIndianRupees(largestDebt.amount_owed)}</p>
      </div> : <p className="mt-2 text-sm text-slate-600">You don't owe anyone.</p>}
    </section>

    <section className="mt-6">
      <h2 className="mb-4 text-lg font-semibold">Recent activity</h2>
      <RecentActivityList activity={dashboard.recent_activity} />
    </section>
  </PageShell>
}
