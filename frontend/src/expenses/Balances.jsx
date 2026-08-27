// import { useCallback, useEffect, useState } from 'react'
// import { getApiErrorMessage } from '../api/auth'
// import { formatIndianRupees } from '../utils/currency'
// import { expensesApi } from './expensesApi'

// export default function Balances({ groupId, refreshKey }) {
//   const [balances, setBalances] = useState(null)
//   const [isLoading, setIsLoading] = useState(true)
//   const [error, setError] = useState('')
//   const loadBalances = useCallback(async () => {
//     setIsLoading(true); setError('')
//     try {
//       const response = await expensesApi.balances(groupId)
//       setBalances(response.data)
//     } catch (requestError) {
//       setError(getApiErrorMessage(requestError, 'Unable to load balances. Please try again.'))
//     } finally { setIsLoading(false) }
//   }, [groupId])
//   useEffect(() => { loadBalances() }, [loadBalances, refreshKey])

//   return <section className="mt-8 border-t border-slate-200 pt-6"><h2 className="text-lg font-semibold">Balances</h2><p className="mt-1 text-sm text-slate-600">Balances and suggestions come directly from SplitMate.</p>
//     {isLoading && <p className="mt-4 text-sm text-slate-600">Loading balances…</p>}
//     {!isLoading && error && <div className="mt-4"><p role="alert" className="text-sm text-red-700">{error}</p><button onClick={loadBalances} className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Retry</button></div>}
//     {!isLoading && !error && balances && <><ul className="mt-4 divide-y divide-slate-200 rounded-lg border border-slate-200">{balances.balances.map((balance) => <li key={balance.user_id} className="flex justify-between gap-4 px-4 py-3 text-sm"><span>{balance.name}</span><span className={{Number(balance.net_balance) > 0 ? '+' : ''}
// {formatIndianRupees(balance.net_balance)}</span></li>)}</ul><h3 className="mt-5 text-sm font-semibold">Who owes whom</h3>{balances.debts.length ? <ul className="mt-2 space-y-2 text-sm text-slate-700">{balances.debts.map((debt, index) => <li key={`${debt.from_user_id}-${debt.to_user_id}-${index}`}>{debt.from_user_name} owes {debt.to_user_name} {formatIndianRupees(debt.amount)}</li>)}</ul> : <p className="mt-2 text-sm text-slate-600">Everyone is settled up.</p>}</>}
//   </section>
// }
import { useCallback, useEffect, useState } from 'react'

import { getApiErrorMessage } from '../api/auth'
import { formatIndianRupees } from '../utils/currency'
import { expensesApi } from './expensesApi'

export default function Balances({ groupId, refreshKey }) {
  const [balances, setBalances] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const loadBalances = useCallback(async () => {
    setIsLoading(true)
    setError('')

    try {
      const response = await expensesApi.balances(groupId)
      setBalances(response.data)
    } catch (requestError) {
      setError(
        getApiErrorMessage(
          requestError,
          'Unable to load balances. Please try again.',
        ),
      )
    } finally {
      setIsLoading(false)
    }
  }, [groupId])

  useEffect(() => {
    loadBalances()
  }, [loadBalances, refreshKey])

  return (
    <section className="mt-8 border-t border-slate-200 pt-6">
      <h2 className="text-lg font-semibold">Balances</h2>

      <p className="mt-1 text-sm text-slate-600">
        Balances and suggestions come directly from SplitMate.
      </p>

      {isLoading && (
        <p className="mt-4 text-sm text-slate-600">
          Loading balances…
        </p>
      )}

      {!isLoading && error && (
        <div className="mt-4">
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>

          <button
            onClick={loadBalances}
            className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !error && balances && (
        <>
          <ul className="mt-4 divide-y divide-slate-200 rounded-lg border border-slate-200">
            {balances.balances.map((balance) => {
              const numericBalance = Number(balance.net_balance)

              return (
                <li
                  key={balance.user_id}
                  className="flex justify-between gap-4 px-4 py-3 text-sm"
                >
                  <span>{balance.name}</span>

                  <span
                    className={
                      numericBalance > 0
                        ? 'font-medium text-emerald-700'
                        : numericBalance < 0
                          ? 'font-medium text-rose-700'
                          : 'text-slate-600'
                    }
                  >
                    {numericBalance > 0 ? '+' : ''}
                    {formatIndianRupees(balance.net_balance)}
                  </span>
                </li>
              )
            })}
          </ul>

          <h3 className="mt-5 text-sm font-semibold">
            Who owes whom
          </h3>

          {balances.debts.length ? (
            <ul className="mt-2 space-y-2 text-sm text-slate-700">
              {balances.debts.map((debt, index) => (
                <li
                  key={`${debt.from_user_id}-${debt.to_user_id}-${index}`}
                >
                  {debt.from_user_name} owes {debt.to_user_name}{' '}
                  {formatIndianRupees(debt.amount)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-600">
              Everyone is settled up.
            </p>
          )}
        </>
      )}
    </section>
  )
}