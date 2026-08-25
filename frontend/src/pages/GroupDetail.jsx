import { useParams } from 'react-router-dom'
import PageShell from '../components/PageShell'

export default function GroupDetail() { const { groupId } = useParams(); return <PageShell title="Group details"><p className="text-slate-600">Group <span className="font-medium text-slate-900">{groupId}</span> will load here.</p></PageShell> }
