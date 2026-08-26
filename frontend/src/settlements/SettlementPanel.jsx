import { useCallback, useEffect, useMemo, useState } from 'react'
import { getApiErrorMessage } from '../api/auth'
import { formatIndianRupees } from '../utils/currency'
import { settlementsApi } from './settlementsApi'

function formatDate(dateTime) {
  return new Date(dateTime).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

export default function SettlementPanel({ groupId, currentUserId, onSettlementRecorded }) {
  const [balances, setBalances] = useState(null)
  const [settlements, setSettlements] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [selectedToUserId, setSelectedToUserId] = useState('')
  const [amount, setAmount] = useState('')
  const [formError, setFormError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const loadSettlementData = useCallback(async () => {
    setIsLoading(true)
    setLoadError('')
    try {
      const [balanceResponse, settlementResponse] = await Promise.all([
        settlementsApi.balances(groupId),
        settlementsApi.list(groupId),
      ])
      setBalances(balanceResponse.data)
      setSettlements(settlementResponse.data)
    } catch (requestError) {
      setLoadError(getApiErrorMessage(requestError, 'Unable to load settlement details. Please try again.'))
    } finally {
      setIsLoading(false)
    }
  }, [groupId])

  useEffect(() => { loadSettlementData() }, [loadSettlementData])

  const actionableDebts = useMemo(
    () => balances?.debts.filter((debt) => debt.from_user_id === currentUserId) || [],
    [balances, currentUserId],
  )
  const selectedDebt = actionableDebts.find((debt) => String(debt.to_user_id) === selectedToUserId)

  useEffect(() => {
    setSelectedToUserId((current) => actionableDebts.some((debt) => String(debt.to_user_id) === current) ? current : String(actionableDebts[0]?.to_user_id || ''))
  }, [actionableDebts])

  function openForm() {
    setFormError('')
    setSubmitError('')
    setSuccessMessage('')
    setIsFormOpen(true)
  }

  function closeForm() {
    if (isSubmitting) return
    setIsFormOpen(false)
    setFormError('')
    setSubmitError('')
  }

  function validateAmount() {
    if (!selectedDebt) return 'Select a member you currently owe.'
    if (!/^[1-9]\d*$/.test(amount)) return 'Enter a positive whole-number amount in paise.'
    const amountInPaise = Number(amount)
    if (!Number.isSafeInteger(amountInPaise) || amountInPaise <= 0) return 'Enter a positive whole-number amount in paise.'
    if (amountInPaise > selectedDebt.amount) return `Amount cannot exceed ${formatIndianRupees(selectedDebt.amount)}.`
    return ''
  }

  async function submitSettlement(event) {
    event.preventDefault()
    const validationError = validateAmount()
    if (validationError) { setFormError(validationError); return }
    setFormError('')
    setSubmitError('')
    setSuccessMessage('')
    setIsSubmitting(true)
    try {
      await settlementsApi.create(groupId, { to_user_id: Number(selectedToUserId), amount: Number(amount) })
      setAmount('')
      setIsFormOpen(false)
      setSuccessMessage('Settlement recorded successfully.')
      await loadSettlementData()
      onSettlementRecorded()
    } catch (requestError) {
      setSubmitError(getApiErrorMessage(requestError, 'Unable to record this settlement. Please try again.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return <section className="mt-8 border-t border-slate-200 pt-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Settle up</h2><p className="mt-1 text-sm text-slate-600">Record a payment against a balance suggested by the backend.</p></div><button onClick={openForm} disabled={!actionableDebts.length || isLoading} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60">Settle up</button></div>
    {successMessage && <p role="status" className="mt-3 text-sm text-emerald-700">{successMessage}</p>}
    {isLoading && <p className="mt-4 text-sm text-slate-600">Loading settlement details…</p>}
    {!isLoading && loadError && <div className="mt-4"><p role="alert" className="text-sm text-red-700">{loadError}</p><button onClick={loadSettlementData} className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">Retry</button></div>}
    {!isLoading && !loadError && <><div className="mt-4"><h3 className="text-sm font-semibold">You currently owe</h3>{actionableDebts.length ? <ul className="mt-2 space-y-2 text-sm text-slate-700">{actionableDebts.map((debt) => <li key={`${debt.from_user_id}-${debt.to_user_id}`} className="rounded-md border border-slate-200 px-3 py-2">{debt.to_user_name}: up to {formatIndianRupees(debt.amount)}</li>)}</ul> : <p className="mt-2 text-sm text-slate-600">You do not currently have a settleable amount.</p>}</div>
      {isFormOpen && <form onSubmit={submitSettlement} noValidate className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4"><h3 className="text-base font-semibold">Record settlement</h3>{(formError || submitError) && <p role="alert" className="mt-3 text-sm text-red-700">{formError || submitError}</p>}<label className="mt-4 block text-sm font-medium">Pay to<select value={selectedToUserId} onChange={(event) => { setSelectedToUserId(event.target.value); setFormError('') }} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">{actionableDebts.map((debt) => <option key={debt.to_user_id} value={debt.to_user_id}>{debt.to_user_name} — up to {formatIndianRupees(debt.amount)}</option>)}</select></label>{selectedDebt && <p className="mt-2 text-sm text-slate-600">Maximum settlement: {formatIndianRupees(selectedDebt.amount)}</p>}<label className="mt-4 block text-sm font-medium">Amount (paise)<input type="number" min="1" step="1" max={selectedDebt?.amount} value={amount} onChange={(event) => { setAmount(event.target.value); setFormError('') }} inputMode="numeric" className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2" /><span className="mt-1 block text-xs font-normal text-slate-500">Use whole paise; the maximum above is based on current backend balance data.</span></label><div className="mt-5 flex gap-3"><button disabled={isSubmitting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60">{isSubmitting ? 'Recording…' : 'Record settlement'}</button><button type="button" disabled={isSubmitting} onClick={closeForm} className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-60">Cancel</button></div></form>}
      <div className="mt-6"><h3 className="text-sm font-semibold">Settlement history</h3>{settlements.length ? <ul className="mt-2 divide-y divide-slate-200 rounded-lg border border-slate-200">{settlements.map((settlement) => <li key={settlement.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"><div><p className="font-medium">{settlement.from_user.name} paid {settlement.to_user.name}</p><p className="mt-1 text-slate-600">{formatDate(settlement.created_at)}</p></div><p className="font-medium">{formatIndianRupees(settlement.amount)}</p></li>)}</ul> : <p className="mt-2 text-sm text-slate-600">No settlements recorded yet.</p>}</div>
    </>}
  </section>
}
