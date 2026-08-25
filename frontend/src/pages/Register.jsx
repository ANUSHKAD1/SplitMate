import { Link } from 'react-router-dom'
import PageShell from '../components/PageShell'

export default function Register() { return <PageShell title="Create an account"><p className="text-slate-600">Registration UI will be connected to the API in a later step.</p><Link className="mt-5 inline-block text-sm text-slate-900 underline" to="/login">Back to sign in</Link></PageShell> }
