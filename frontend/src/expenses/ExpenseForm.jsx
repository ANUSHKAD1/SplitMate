import { useEffect, useMemo, useState } from 'react'
import { formatIndianRupees } from '../utils/currency'

function today() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

function paiseToInput(amount) { return (amount / 100).toFixed(2) }

function inputToPaise(value) {
  const normalized = value.trim()
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null
  const [rupees, decimal = ''] = normalized.split('.')
  return Number(rupees) * 100 + Number(`${decimal}00`.slice(0, 2))
}

function buildInitialState(members, expense) {
  const splitUserIds = expense ? expense.splits.map((split) => split.user_id) : members.map((member) => member.id)
  return {
    description: expense?.description || '', amount: expense ? paiseToInput(expense.amount) : '', paidBy: String(expense?.paid_by || members[0]?.id || ''),
    expenseDate: expense?.expense_date || today(), splitType: expense?.split_type || 'equal', splitUserIds,
    customAmounts: Object.fromEntries(splitUserIds.map((userId) => {
      const split = expense?.splits.find((item) => item.user_id === userId)
      return [userId, split ? paiseToInput(split.amount) : '0.00']
    })),
  }
}

export default function ExpenseForm({ members, expense, onSubmit, onCancel, isSubmitting, submitError }) {
  const [form, setForm] = useState(() => buildInitialState(members, expense))
  const [formError, setFormError] = useState('')
  useEffect(() => { setForm(buildInitialState(members, expense)); setFormError('') }, [expense, members])

  const amountInPaise = inputToPaise(form.amount)
  const selectedMembers = members.filter((member) => form.splitUserIds.includes(member.id))
  const customTotal = useMemo(() => selectedMembers.reduce((total, member) => total + (inputToPaise(form.customAmounts[member.id] || '') ?? 0), 0), [form.customAmounts, selectedMembers])
  const customHasInvalidAmount = selectedMembers.some((member) => inputToPaise(form.customAmounts[member.id] || '') === null)
  const isCustomMismatch = form.splitType === 'custom' && (customHasInvalidAmount || customTotal !== amountInPaise)
  const equalShares = useMemo(() => {
    if (!amountInPaise || !selectedMembers.length) return []
    const base = Math.floor(amountInPaise / selectedMembers.length), remainder = amountInPaise % selectedMembers.length
    return selectedMembers.map((member, index) => ({ ...member, amount: base + (index < remainder ? 1 : 0) }))
  }, [amountInPaise, selectedMembers])

  function updateForm(field, value) { setForm((current) => ({ ...current, [field]: value })) }
  function toggleMember(userId) {
    setForm((current) => {
      const isSelected = current.splitUserIds.includes(userId)
      const splitUserIds = isSelected ? current.splitUserIds.filter((id) => id !== userId) : [...current.splitUserIds, userId]
      const customAmounts = { ...current.customAmounts }
      if (!isSelected && customAmounts[userId] === undefined) customAmounts[userId] = '0.00'
      return { ...current, splitUserIds, customAmounts }
    })
  }
  function changeSplitType(splitType) { setForm((current) => ({ ...current, splitType, customAmounts: Object.fromEntries(current.splitUserIds.map((userId) => [userId, current.customAmounts[userId] ?? '0.00'])) })) }

  async function handleSubmit(event) {
    event.preventDefault()
    const description = form.description.trim()
    if (!description) return setFormError('Description is required.')
    if (!amountInPaise || amountInPaise <= 0) return setFormError('Enter an amount greater than ₹0.00.')
    if (!form.paidBy) return setFormError('Choose the member who paid.')
    if (!form.expenseDate) return setFormError('Choose the expense date.')
    if (!selectedMembers.length) return setFormError('Select at least one member to split with.')
    if (isCustomMismatch) return setFormError('Custom shares must be valid amounts and add up to the expense total.')
    setFormError('')
    await onSubmit({ description, amount: amountInPaise, paid_by: Number(form.paidBy), expense_date: form.expenseDate, split_type: form.splitType, split_user_ids: form.splitType === 'equal' ? form.splitUserIds : [], splits: form.splitType === 'custom' ? form.splitUserIds.map((userId) => ({ user_id: userId, amount: inputToPaise(form.customAmounts[userId]) })) : [] })
  }

  return <form onSubmit={handleSubmit} noValidate className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
    <h3 className="text-base font-semibold">{expense ? 'Edit expense' : 'New expense'}</h3>
    {(formError || submitError) && <p role="alert" className="mt-3 text-sm text-red-700">{formError || submitError}</p>}
    <div className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium sm:col-span-2">Description<input value={form.description} onChange={(event) => updateForm('description', event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2" maxLength="500" /></label>
      <label className="text-sm font-medium">Amount (INR)<input value={form.amount} onChange={(event) => updateForm('amount', event.target.value)} inputMode="decimal" placeholder="0.00" className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2" /></label>
      <label className="text-sm font-medium">Date<input type="date" value={form.expenseDate} onChange={(event) => updateForm('expenseDate', event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2" /></label>
      <label className="text-sm font-medium sm:col-span-2">Paid by<select value={form.paidBy} onChange={(event) => updateForm('paidBy', event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2">{members.map((member) => <option key={member.id} value={member.id}>{member.name}</option>)}</select></label>
    </div>
    <fieldset className="mt-5"><legend className="text-sm font-medium">Split type</legend><div className="mt-2 flex gap-4 text-sm">{['equal', 'custom'].map((type) => <label key={type} className="flex items-center gap-2 capitalize"><input type="radio" name="splitType" checked={form.splitType === type} onChange={() => changeSplitType(type)} />{type}</label>)}</div></fieldset>
    <fieldset className="mt-5"><legend className="text-sm font-medium">Split with</legend><div className="mt-2 divide-y divide-slate-200 rounded-md border border-slate-200 bg-white">{members.map((member) => {
      const checked = form.splitUserIds.includes(member.id)
      return <div key={member.id} className="flex items-center justify-between gap-3 px-3 py-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={checked} onChange={() => toggleMember(member.id)} />{member.name}</label>{form.splitType === 'custom' && checked && <label className="flex items-center gap-1 text-sm text-slate-600">₹<input value={form.customAmounts[member.id] ?? '0.00'} onChange={(event) => setForm((current) => ({ ...current, customAmounts: { ...current.customAmounts, [member.id]: event.target.value } }))} inputMode="decimal" className="w-24 rounded border border-slate-300 px-2 py-1" aria-label={`${member.name}'s share in INR`} /></label>}</div>
    })}</div></fieldset>
    {form.splitType === 'equal' && selectedMembers.length > 0 && <div className="mt-4 rounded-md bg-white p-3 text-sm"><p className="font-medium">Calculated shares</p><ul className="mt-2 space-y-1 text-slate-600">{equalShares.map((share) => <li key={share.id}>{share.name}: {formatIndianRupees(share.amount)}</li>)}</ul><p className="mt-2 text-xs text-slate-500">This is a preview; the backend validates and assigns the final split.</p></div>}
    {form.splitType === 'custom' && <div className="mt-4 text-sm"><p className="font-medium">Running total: {formatIndianRupees(customTotal)}</p>{isCustomMismatch && <p role="alert" className="mt-1 text-red-700">Shares must equal {amountInPaise === null ? 'a valid expense amount' : formatIndianRupees(amountInPaise)}.</p>}</div>}
    <div className="mt-5 flex gap-3"><button disabled={isSubmitting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60">{isSubmitting ? 'Saving…' : expense ? 'Save changes' : 'Add expense'}</button><button type="button" disabled={isSubmitting} onClick={onCancel} className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-60">Cancel</button></div>
  </form>
}
