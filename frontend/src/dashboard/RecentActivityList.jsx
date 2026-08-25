function formatActivityTime(value) {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function RecentActivityList({ activity }) {
  if (!activity.length) {
    return <p className="text-sm text-slate-600">No recent activity yet.</p>
  }

  return <ul className="divide-y divide-slate-200">
    {activity.map((item) => <li key={item.id} className="py-3 first:pt-0 last:pb-0">
      <p className="text-sm font-medium text-slate-900">{item.message}</p>
      <p className="mt-1 text-xs text-slate-500">{item.group_name} · {formatActivityTime(item.created_at)}</p>
    </li>)}
  </ul>
}
