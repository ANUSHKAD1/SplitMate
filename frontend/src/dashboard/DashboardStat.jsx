export default function DashboardStat({ label, value, tone = 'default' }) {
  const toneClasses = {
    default: 'text-slate-900',
    positive: 'text-emerald-700',
    negative: 'text-rose-700',
  }

  return <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
    <p className="text-sm text-slate-600">{label}</p>
    <p className={`mt-2 text-2xl font-semibold ${toneClasses[tone]}`}>{value}</p>
  </article>
}
